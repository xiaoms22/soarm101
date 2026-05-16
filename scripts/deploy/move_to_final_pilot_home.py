#!/usr/bin/env python
"""Move the SO-ARM101 follower to the median final-pilot start pose."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.robots.utils import make_robot_from_config
from lerobot.utils.robot_utils import precise_sleep


JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def final_pilot_home(dataset_root: Path) -> dict[str, float]:
    df = pd.read_parquet(dataset_root / "data" / "chunk-000" / "file-000.parquet")
    starts = []
    for _, episode in df.groupby("episode_index"):
        starts.append(np.asarray(episode.iloc[0]["observation.state"], dtype=np.float64))
    median = np.median(np.stack(starts), axis=0)
    return {f"{name}.pos": float(value) for name, value in zip(JOINTS, median)}


def add_motor_retries(robot: Any, num_retry: int) -> None:
    if num_retry <= 0 or not hasattr(robot, "bus"):
        return
    bus = robot.bus
    for method_name in ("write", "sync_read", "sync_write", "enable_torque", "disable_torque"):
        original = getattr(bus, method_name, None)
        if original is None:
            continue

        def with_retry(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
            kwargs.setdefault("num_retry", num_retry)
            return _original(*args, **kwargs)

        setattr(bus, method_name, with_retry)


def make_robot_config(config_path: Path, max_relative_target: float) -> SOFollowerRobotConfig:
    raw = load_yaml(config_path)["robot"]
    return SOFollowerRobotConfig(
        port=raw["port"],
        id=raw.get("id"),
        calibration_dir=Path(raw["calibration_dir"]) if raw.get("calibration_dir") else None,
        max_relative_target=max_relative_target,
        disable_torque_on_disconnect=False,
        cameras={},
        use_degrees=raw.get("use_degrees", True),
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", type=Path, default=repo_root / "record_config.yaml")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=repo_root / "data" / "so101-left-final-pilot",
    )
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--per-step-deg", type=float, default=3.0)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--timeout-s", type=float, default=25.0)
    parser.add_argument("--motor-retries", type=int, default=5)
    args = parser.parse_args()

    target = final_pilot_home(args.dataset_root)
    robot_cfg = make_robot_config(args.config_path, args.per_step_deg)
    robot = make_robot_from_config(robot_cfg)
    add_motor_retries(robot, args.motor_retries)

    print("Move SO-ARM101 follower to final-pilot home")
    print(f"  target: {target}")
    print(f"  per_step_deg: {args.per_step_deg}")
    print(f"  tolerance: {args.tolerance}")
    print(f"  timeout_s: {args.timeout_s}")

    try:
        robot.connect()
        period_s = 1.0 / args.fps
        deadline = time.perf_counter() + args.timeout_s
        step = 0
        while time.perf_counter() < deadline:
            loop_t = time.perf_counter()
            obs = robot.get_observation()
            errors = {key: target[key] - float(obs[key]) for key in target}
            max_error = max(abs(value) for value in errors.values())
            print(
                "step={step:03d} max_error={max_error:6.2f} current={current}".format(
                    step=step,
                    max_error=max_error,
                    current={key: round(float(obs[key]), 2) for key in target},
                )
            )
            if max_error <= args.tolerance:
                print("HOME_REACHED")
                return
            robot.send_action(target)
            step += 1
            precise_sleep(max(0.0, period_s - (time.perf_counter() - loop_t)))

        obs = robot.get_observation()
        final_errors = {key: target[key] - float(obs[key]) for key in target}
        max_error = max(abs(value) for value in final_errors.values())
        raise SystemExit(f"HOME_TIMEOUT max_error={max_error:.2f} final_errors={final_errors}")
    finally:
        if robot.is_connected:
            robot.disconnect()


if __name__ == "__main__":
    main()
