#!/usr/bin/env python
"""Validate a SO-ARM101 final pilot LeRobot dataset.

This is a read-mostly validator. With --extract-review-frames it also writes
small JPG contact sheets under the dataset root for AI/manual release review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import av
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw


EXPECTED_TASK = "Pick up object and Put down in box"
EXPECTED_FEATURES = {
    "observation.state": [6],
    "action": [6],
    "observation.images.fixed": [480, 640, 3],
    "observation.images.handeye": [480, 640, 3],
}


def status_line(ok: bool, message: str) -> str:
    return f"{'PASS' if ok else 'FAIL'}  {message}"


def warn_line(message: str) -> str:
    return f"WARN  {message}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def stack_series(series: pd.Series) -> np.ndarray:
    return np.stack(series.to_numpy())


def feature_shape(info: dict[str, Any], name: str) -> list[int] | None:
    ft = info.get("features", {}).get(name)
    if not ft:
        return None
    return list(ft.get("shape", []))


def action_names(info: dict[str, Any]) -> list[str]:
    return list(info.get("features", {}).get("action", {}).get("names", []))


def video_path(root: Path, feature: str) -> Path:
    return root / "videos" / feature / "chunk-000" / "file-000.mp4"


def decode_video_metadata(path: Path) -> tuple[bool, str]:
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            frames = sum(1 for _ in container.decode(stream))
            return True, f"{stream.width}x{stream.height}, frames={frames}, avg_rate={stream.average_rate}"
    except Exception as exc:  # noqa: BLE001 - report validation failure without crashing.
        return False, f"{type(exc).__name__}: {exc}"


def frame_at_timestamp(container: av.container.InputContainer, stream: av.video.stream.VideoStream, ts_s: float):
    # Decode sequentially; datasets are small pilot clips, and this is robust.
    target = max(0.0, ts_s)
    best = None
    for frame in container.decode(stream):
        if frame.time is None:
            best = frame
            continue
        best = frame
        if frame.time >= target:
            break
    return best


def extract_review_frames(root: Path, episodes: pd.DataFrame) -> list[str]:
    output_dir = root / "validation_review"
    output_dir.mkdir(exist_ok=True)
    written = []
    for feature in ["observation.images.fixed", "observation.images.handeye"]:
        path = video_path(root, feature)
        if not path.exists():
            continue
        for _, ep in episodes.iterrows():
            ep_idx = int(ep["episode_index"])
            start = float(ep[f"videos/{feature}/from_timestamp"])
            end = float(ep[f"videos/{feature}/to_timestamp"])
            # Sample the release-heavy tail plus one earlier context frame.
            span = max(end - start, 1e-6)
            stamps = [
                start + span * 0.60,
                start + span * 0.78,
                start + span * 0.90,
                max(start, end - 0.15),
            ]
            images = []
            labels = []
            for ts in stamps:
                with av.open(str(path)) as container:
                    stream = container.streams.video[0]
                    frame = frame_at_timestamp(container, stream, ts)
                    if frame is None:
                        continue
                    img = frame.to_image().resize((320, 240))
                    images.append(img)
                    labels.append(f"{ts:.2f}s")
            if not images:
                continue
            sheet = Image.new("RGB", (320 * len(images), 270), "white")
            draw = ImageDraw.Draw(sheet)
            for i, img in enumerate(images):
                sheet.paste(img, (i * 320, 0))
                draw.text((i * 320 + 8, 246), labels[i], fill=(0, 0, 0))
            out = output_dir / f"episode_{ep_idx:03d}_{feature.replace('.', '_')}_release_tail.jpg"
            sheet.save(out, quality=90)
            written.append(str(out))
    return written


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=repo_root / "data" / "so101-left-final-pilot")
    parser.add_argument("--expected-episodes", type=int, default=10)
    parser.add_argument("--expected-fps", type=int, default=10)
    parser.add_argument("--min-episode-frames", type=int, default=60)
    parser.add_argument("--max-episode-frames", type=int, default=300)
    parser.add_argument("--extract-review-frames", action="store_true")
    args = parser.parse_args()

    root = args.root
    info_path = root / "meta" / "info.json"
    episodes_path = root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    data_path = root / "data" / "chunk-000" / "file-000.parquet"
    tasks_path = root / "meta" / "tasks.parquet"

    failures: list[str] = []
    warnings: list[str] = []
    report: list[str] = [f"Dataset root: {root}"]

    for path in [info_path, episodes_path, data_path, tasks_path]:
        ok = path.exists()
        report.append(status_line(ok, f"exists: {path.relative_to(root) if root in path.parents else path}"))
        if not ok:
            failures.append(f"missing {path}")

    if failures:
        print("\n".join(report))
        print("\nRESULT: BLOCKED")
        return 2

    info = load_json(info_path)
    episodes = pd.read_parquet(episodes_path)
    data = pd.read_parquet(data_path)
    tasks = pd.read_parquet(tasks_path)

    fps_ok = info.get("fps") == args.expected_fps
    report.append(status_line(fps_ok, f"fps == {args.expected_fps} (actual={info.get('fps')})"))
    if not fps_ok:
        failures.append("fps mismatch")

    ep_count_ok = len(episodes) == args.expected_episodes
    report.append(status_line(ep_count_ok, f"episode count == {args.expected_episodes} (actual={len(episodes)})"))
    if not ep_count_ok:
        failures.append("episode count mismatch")

    for name, expected in EXPECTED_FEATURES.items():
        actual = feature_shape(info, name)
        ok = actual == expected
        report.append(status_line(ok, f"{name} shape {expected} (actual={actual})"))
        if not ok:
            failures.append(f"feature mismatch {name}")

    task_values: list[str] = []
    if "task" in tasks.columns:
        task_values = [str(x) for x in tasks["task"].tolist()]
    elif "tasks" in episodes.columns:
        for value in episodes["tasks"].tolist():
            if isinstance(value, (list, tuple, np.ndarray)):
                task_values.extend(str(x) for x in value)
            else:
                task_values.append(str(value))
    task_ok = bool(task_values) and all(t == EXPECTED_TASK for t in task_values)
    report.append(status_line(task_ok, f"task string == {EXPECTED_TASK!r}"))
    if not task_ok:
        failures.append(f"task string mismatch: {task_values}")

    lengths = episodes["length"].astype(int).tolist()
    length_ok = all(args.min_episode_frames <= x <= args.max_episode_frames for x in lengths)
    report.append(
        status_line(
            length_ok,
            f"episode lengths in [{args.min_episode_frames}, {args.max_episode_frames}] (actual={lengths})",
        )
    )
    if not length_ok:
        warnings.append("episode length outside preferred range; inspect or rerecord short/long episodes")

    rows_ok = len(data) == int(sum(lengths))
    report.append(status_line(rows_ok, f"data rows match episode lengths (rows={len(data)}, sum={sum(lengths)})"))
    if not rows_ok:
        failures.append("row count mismatch")

    try:
        actions = stack_series(data["action"])
        states = stack_series(data["observation.state"])
        nan_action = bool(np.isnan(actions).any())
        nan_state = bool(np.isnan(states).any())
        report.append(status_line(not nan_action, "action has no NaN"))
        report.append(status_line(not nan_state, "observation.state has no NaN"))
        if nan_action:
            failures.append("action contains NaN")
        if nan_state:
            failures.append("observation.state contains NaN")

        action_range = np.ptp(actions, axis=0)
        names = action_names(info)
        rounded_ranges = [round(float(value), 3) for value in action_range]
        report.append(f"INFO  action ranges: {dict(zip(names or range(actions.shape[1]), rounded_ranges))}")
        action_var_ok = bool(np.nanmax(action_range) > 1.0)
        report.append(status_line(action_var_ok, "action varies meaningfully"))
        if not action_var_ok:
            failures.append("action barely changes")

        gripper_ok = True
        if "gripper.pos" in names:
            gripper_range = float(action_range[names.index("gripper.pos")])
            gripper_ok = gripper_range >= 5.0
            report.append(status_line(gripper_ok, f"gripper action range >= 5.0 (actual={gripper_range:.3f})"))
        else:
            gripper_ok = False
            report.append(status_line(False, f"gripper.pos present in action names (actual={names})"))
        if not gripper_ok:
            warnings.append("gripper change is small or missing; inspect grasp/release episodes")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"failed numeric validation: {type(exc).__name__}: {exc}")
        report.append(status_line(False, f"numeric validation failed: {exc}"))

    for feature in ["observation.images.fixed", "observation.images.handeye"]:
        path = video_path(root, feature)
        exists = path.exists()
        report.append(status_line(exists, f"video exists: {feature}"))
        if not exists:
            failures.append(f"missing video {feature}")
            continue
        ok, meta = decode_video_metadata(path)
        report.append(status_line(ok, f"video decodes: {feature} ({meta})"))
        if not ok:
            warnings.append(f"video decode failed for {feature}: {meta}")

    if args.extract_review_frames:
        try:
            written = extract_review_frames(root, episodes)
            report.append(f"INFO  review frames written: {len(written)}")
            for item in written[:8]:
                report.append(f"INFO    {item}")
            if len(written) > 8:
                report.append(f"INFO    ... {len(written) - 8} more")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"failed to extract review frames: {type(exc).__name__}: {exc}")

    for warning in warnings:
        report.append(warn_line(warning))

    print("\n".join(report))

    if failures:
        print("\nRESULT: BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 2
    if warnings:
        print("\nRESULT: FIX BEFORE TRAINING")
        return 1

    release_review = "review validation_review/*.jpg for release timing" if args.extract_review_frames else ""
    print(f"\nRESULT: PASS {release_review}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
