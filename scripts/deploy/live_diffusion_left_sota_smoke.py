#!/usr/bin/env python
"""Run a live SO-ARM101 diffusion-policy smoke test without saving a dataset.

This is a deployment-oriented benchmark. It avoids LeRobotDataset creation,
video encoding, and parquet writes so we can measure the real control loop:

robot observation -> policy preprocessing -> policy inference -> robot action.
"""

from __future__ import annotations

import argparse
import csv
import logging
import statistics
import time
from pathlib import Path
from typing import Any

import torch
import yaml

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.configs.policies import PreTrainedConfig
from lerobot.datasets.feature_utils import build_dataset_frame, combine_feature_dicts, hw_to_dataset_features
from lerobot.policies.factory import get_policy_class, make_pre_post_processors
from lerobot.policies.utils import make_robot_action, prepare_observation_for_inference
from lerobot.processor import make_default_processors
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.robots.utils import make_robot_from_config
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.device_utils import get_safe_torch_device
from lerobot.utils.robot_utils import precise_sleep


TASK = "Pick up object and Put down in box"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _camera_config(raw: dict[str, Any]) -> OpenCVCameraConfig:
    if raw["type"] != "opencv":
        raise ValueError(f"Only opencv cameras are supported by this smoke test. Got {raw['type']!r}.")
    return OpenCVCameraConfig(
        index_or_path=raw["index_or_path"],
        width=raw["width"],
        height=raw["height"],
        fps=raw["fps"],
        fourcc=raw.get("fourcc"),
    )


def make_robot_config(config_path: Path, max_relative_target: float) -> SOFollowerRobotConfig:
    raw = _load_yaml(config_path)["robot"]
    cameras = {name: _camera_config(cam) for name, cam in raw.get("cameras", {}).items()}
    return SOFollowerRobotConfig(
        port=raw["port"],
        id=raw.get("id"),
        calibration_dir=Path(raw["calibration_dir"]) if raw.get("calibration_dir") else None,
        max_relative_target=max_relative_target,
        disable_torque_on_disconnect=raw.get("disable_torque_on_disconnect", False),
        cameras=cameras,
        use_degrees=raw.get("use_degrees", True),
    )


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


def warmup_motor_reads(robot: Any, count: int, num_retry: int) -> None:
    if count <= 0 or not hasattr(robot, "bus"):
        return
    for _ in range(count):
        robot.bus.sync_read("Present_Position", num_retry=num_retry)
        time.sleep(0.05)


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


def summarize_ms(name: str, values: list[float]) -> str:
    if not values:
        return f"{name:>12}: n/a"
    return (
        f"{name:>12}: avg={statistics.mean(values):7.1f} ms | "
        f"p50={statistics.median(values):7.1f} | p90={pct(values, 0.90):7.1f} | "
        f"max={max(values):7.1f}"
    )


def smooth_robot_action(
    robot_action: dict[str, float],
    previous_action: dict[str, float] | None,
    alpha: float,
    smooth_gripper: bool,
) -> dict[str, float]:
    if previous_action is None or alpha >= 1.0:
        return dict(robot_action)
    if alpha <= 0.0:
        return dict(previous_action)

    smoothed: dict[str, float] = {}
    for key, value in robot_action.items():
        if key == "gripper.pos" and not smooth_gripper:
            smoothed[key] = value
            continue
        prev = previous_action.get(key, value)
        smoothed[key] = alpha * value + (1.0 - alpha) * prev
    return smoothed


def parse_joint_bias(values: list[str]) -> dict[str, float]:
    biases: dict[str, float] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Joint bias must be formatted as name=value, got {value!r}")
        name, raw = value.split("=", 1)
        name = name.strip()
        if not name.endswith(".pos"):
            name = f"{name}.pos"
        biases[name] = float(raw)
    return biases


def apply_joint_bias(
    robot_action: dict[str, float],
    biases: dict[str, float],
    step: int,
    start_step: int,
    end_step: int,
    ramp_steps: int,
) -> tuple[dict[str, float], float]:
    if not biases or step < start_step or step >= end_step:
        return dict(robot_action), 0.0

    if ramp_steps <= 1:
        factor = 1.0
    else:
        factor = min(1.0, max(0.0, (step - start_step + 1) / ramp_steps))

    biased = dict(robot_action)
    for key, value in biases.items():
        if key in biased:
            biased[key] += factor * value
    return biased, factor


def max_abs_delta(current: dict[str, float], previous: dict[str, float] | None, keys: list[str]) -> float:
    if previous is None:
        return 0.0
    return max(abs(current[key] - previous[key]) for key in keys)


def make_log_row(
    step: int,
    timestamp_s: float,
    action_keys: list[str],
    obs: dict[str, Any],
    raw_action: dict[str, float],
    command_action: dict[str, float],
    sent_action: dict[str, float],
    prev_raw_action: dict[str, float] | None,
    prev_command_action: dict[str, float] | None,
    prev_sent_action: dict[str, float] | None,
    loop_total_ms: float,
    gripper_gated: bool,
    bias_factor: float,
) -> dict[str, float | int]:
    row: dict[str, float | int] = {
        "step": step,
        "timestamp_s": timestamp_s,
        "loop_total_ms": loop_total_ms,
        "raw_max_delta": max_abs_delta(raw_action, prev_raw_action, action_keys),
        "command_max_delta": max_abs_delta(command_action, prev_command_action, action_keys),
        "sent_max_delta": max_abs_delta(sent_action, prev_sent_action, action_keys),
        "clamped": int(any(abs(sent_action[k] - command_action[k]) > 1e-4 for k in action_keys)),
        "gripper_gated": int(gripper_gated),
        "bias_factor": bias_factor,
    }
    for key in action_keys:
        stem = key.removesuffix(".pos").replace(".", "_")
        row[f"obs_{stem}"] = float(obs[key])
        row[f"raw_{stem}"] = float(raw_action[key])
        row[f"command_{stem}"] = float(command_action[key])
        row[f"sent_{stem}"] = float(sent_action[key])
        row[f"clamp_abs_{stem}"] = abs(float(sent_action[key]) - float(command_action[key]))
    return row


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", type=Path, default=repo_root / "record_config.yaml")
    parser.add_argument("--policy-path", type=Path, default=repo_root / "models" / "diffusion-left-sota")
    parser.add_argument("--duration-s", type=float, default=10.0)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--num-inference-steps", type=int, default=2)
    parser.add_argument("--max-relative-target", type=float, default=5.0)
    parser.add_argument("--motor-retries", type=int, default=5)
    parser.add_argument("--warmup-reads", type=int, default=3)
    parser.add_argument("--action-ema-alpha", type=float, default=1.0)
    parser.add_argument("--smooth-gripper", action="store_true")
    parser.add_argument("--gripper-open-until-step", type=int, default=0)
    parser.add_argument("--gripper-open-value", type=float, default=0.725)
    parser.add_argument("--joint-bias", action="append", default=[])
    parser.add_argument("--bias-start-step", type=int, default=0)
    parser.add_argument("--bias-end-step", type=int, default=1_000_000)
    parser.add_argument("--bias-ramp-steps", type=int, default=10)
    parser.add_argument("--action-log", type=Path)
    parser.add_argument("--torch-threads", type=int, default=8)
    parser.add_argument("--log-level", default="ERROR", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(asctime)s %(message)s")

    if args.torch_threads > 0:
        torch.set_num_threads(args.torch_threads)

    policy_cfg = PreTrainedConfig.from_pretrained(args.policy_path)
    policy_cfg.device = "cpu"
    policy_cfg.use_amp = False
    if hasattr(policy_cfg, "num_inference_steps"):
        policy_cfg.num_inference_steps = args.num_inference_steps

    policy_cls = get_policy_class(policy_cfg.type)
    policy = policy_cls.from_pretrained(args.policy_path, config=policy_cfg)
    policy.eval()
    policy.reset()

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy_cfg,
        pretrained_path=str(args.policy_path),
        preprocessor_overrides={"device_processor": {"device": policy_cfg.device}},
    )
    preprocessor.reset()
    postprocessor.reset()

    robot_cfg = make_robot_config(args.config_path, args.max_relative_target)
    robot = make_robot_from_config(robot_cfg)
    add_motor_retries(robot, args.motor_retries)
    _, robot_action_processor, robot_observation_processor = make_default_processors()
    device = get_safe_torch_device(policy_cfg.device)
    joint_bias = parse_joint_bias(args.joint_bias)

    stats: dict[str, list[float]] = {
        "observe": [],
        "build": [],
        "prepare": [],
        "preproc": [],
        "policy": [],
        "postproc": [],
        "action_map": [],
        "send": [],
        "total": [],
    }
    clamp_count = 0
    steps = 0
    action_keys: list[str] = []
    prev_raw_action: dict[str, float] | None = None
    prev_command_action: dict[str, float] | None = None
    prev_sent_action: dict[str, float] | None = None
    log_fh: Any = None
    log_writer: csv.DictWriter | None = None

    print("Live diffusion smoke test")
    print(f"  policy: {args.policy_path}")
    print(f"  duration: {args.duration_s}s @ target {args.fps}Hz")
    print(f"  num_inference_steps: {args.num_inference_steps}")
    print(f"  max_relative_target: {args.max_relative_target}")
    print(f"  motor_retries: {args.motor_retries}")
    print(f"  warmup_reads: {args.warmup_reads}")
    print(f"  action_ema_alpha: {args.action_ema_alpha}")
    print(f"  smooth_gripper: {args.smooth_gripper}")
    print(f"  gripper_open_until_step: {args.gripper_open_until_step}")
    print(f"  gripper_open_value: {args.gripper_open_value}")
    print(f"  joint_bias: {joint_bias}")
    print(f"  bias_start_step: {args.bias_start_step}")
    print(f"  bias_end_step: {args.bias_end_step}")
    print(f"  bias_ramp_steps: {args.bias_ramp_steps}")
    if args.action_log:
        print(f"  action_log: {args.action_log}")
    print(f"  torch_threads: {torch.get_num_threads()}")
    print()

    try:
        robot.connect()
        warmup_motor_reads(robot, args.warmup_reads, args.motor_retries)
        features = combine_feature_dicts(
            hw_to_dataset_features(robot.action_features, ACTION, use_video=True),
            hw_to_dataset_features(robot.observation_features, OBS_STR, use_video=True),
        )
        action_keys = features[ACTION]["names"]

        if args.action_log:
            args.action_log.parent.mkdir(parents=True, exist_ok=True)
            log_fh = args.action_log.open("w", newline="", encoding="utf-8")
            base_fields = [
                "step",
                "timestamp_s",
                "loop_total_ms",
                "raw_max_delta",
                "command_max_delta",
                "sent_max_delta",
                "clamped",
                "gripper_gated",
                "bias_factor",
            ]
            joint_fields = []
            for key in action_keys:
                stem = key.removesuffix(".pos").replace(".", "_")
                joint_fields.extend(
                    [
                        f"obs_{stem}",
                        f"raw_{stem}",
                        f"command_{stem}",
                        f"sent_{stem}",
                        f"clamp_abs_{stem}",
                    ]
                )
            log_writer = csv.DictWriter(log_fh, fieldnames=base_fields + joint_fields)
            log_writer.writeheader()

        deadline = time.perf_counter() + args.duration_s
        period_s = 1.0 / args.fps
        start_s = time.perf_counter()

        while time.perf_counter() < deadline:
            loop_t = time.perf_counter()

            t = time.perf_counter()
            obs = robot.get_observation()
            obs = robot_observation_processor(obs)
            stats["observe"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            obs_frame = build_dataset_frame(features, obs, prefix=OBS_STR)
            stats["build"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            model_obs = prepare_observation_for_inference(
                dict(obs_frame),
                device=device,
                task=TASK,
                robot_type=robot.robot_type,
            )
            stats["prepare"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            model_obs = preprocessor(model_obs)
            stats["preproc"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            with torch.inference_mode():
                action = policy.select_action(model_obs)
            stats["policy"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            action = postprocessor(action)
            stats["postproc"].append((time.perf_counter() - t) * 1000)

            t = time.perf_counter()
            robot_action = make_robot_action(action, features)
            robot_action = robot_action_processor((robot_action, obs))
            stats["action_map"].append((time.perf_counter() - t) * 1000)
            raw_action = dict(robot_action)
            command_action = smooth_robot_action(
                raw_action,
                prev_command_action,
                args.action_ema_alpha,
                args.smooth_gripper,
            )
            command_action, bias_factor = apply_joint_bias(
                command_action,
                joint_bias,
                steps,
                args.bias_start_step,
                args.bias_end_step,
                args.bias_ramp_steps,
            )
            gripper_gated = steps < args.gripper_open_until_step
            if gripper_gated and "gripper.pos" in command_action:
                command_action["gripper.pos"] = args.gripper_open_value

            t = time.perf_counter()
            sent_action = robot.send_action(command_action)
            stats["send"].append((time.perf_counter() - t) * 1000)

            if any(abs(sent_action[k] - command_action[k]) > 1e-4 for k in action_keys):
                clamp_count += 1

            elapsed = time.perf_counter() - loop_t
            stats["total"].append(elapsed * 1000)
            if log_writer is not None:
                log_writer.writerow(
                    make_log_row(
                        step=steps,
                        timestamp_s=loop_t - start_s,
                        action_keys=action_keys,
                        obs=obs,
                        raw_action=raw_action,
                        command_action=command_action,
                        sent_action=sent_action,
                        prev_raw_action=prev_raw_action,
                        prev_command_action=prev_command_action,
                        prev_sent_action=prev_sent_action,
                        loop_total_ms=elapsed * 1000,
                        gripper_gated=gripper_gated,
                        bias_factor=bias_factor,
                    )
                )
            prev_raw_action = raw_action
            prev_command_action = command_action
            prev_sent_action = dict(sent_action)
            steps += 1
            precise_sleep(max(0.0, period_s - elapsed))
    finally:
        if log_fh is not None:
            log_fh.close()
        if robot.is_connected:
            robot.disconnect()

    total_s = sum(stats["total"]) / 1000
    wall_est_s = args.duration_s
    slow = [v for v in stats["total"] if v > (1000 / args.fps)]
    chunk_frames = [v for v in stats["policy"] if v > 10.0]

    print()
    print("Result")
    print(f"  steps: {steps}")
    print(f"  target Hz: {args.fps:.2f}")
    print(f"  loop-work Hz, excluding sleeps: {steps / max(total_s, 1e-9):.2f}")
    print(f"  wall Hz, including sleeps: {steps / max(wall_est_s, 1e-9):.2f}")
    print(f"  slow frames > target period: {len(slow)} / {steps}")
    print(f"  clamped actions: {clamp_count} / {steps}")
    print(f"  policy chunk frames (>10ms policy time): {len(chunk_frames)} / {steps}")
    print()
    for key in ["observe", "build", "prepare", "preproc", "policy", "postproc", "action_map", "send", "total"]:
        print(summarize_ms(key, stats[key]))


if __name__ == "__main__":
    main()
