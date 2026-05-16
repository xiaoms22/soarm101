# SO-ARM101 final pilot data collection

This guide is for collecting the first final-object/final-tray pilot dataset.

## Defaults

- Dataset repo id: `xiaoms22/so101-left-final-pilot`
- Local root: `data/so101-left-final-pilot`
- Episodes: `10`
- Task string: `Pick up object and Put down in box`
- Region: left only
- Validation: AI full check, no physical replay by default

## Pre-check

```powershell
cd D:\lerobot\soarm101
conda activate lerobot-so101
python .\scripts\collect\check_cameras.py
```

Expected cameras:

```text
Camera 0: available
Camera 2: available
```

Current mapping:

- `fixed`: Camera 0, top/global view.
- `handeye`: Camera 2, wrist/gripper view.
- Camera 1 currently shows no useful scene view and is not used for collection.

Scene checklist:

- Final tray is fixed.
- Final object starts in the left zone.
- Fixed and handeye cameras are fixed and unobstructed.
- Follower is at the shared home pose.
- COM3 follower and COM4 leader are powered.
- If calibration prompt appears, press Enter to use existing calibration.

## Start collection

```powershell
cd D:\lerobot\soarm101
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_final_pilot_collection.ps1
```

The script runs with `display_data=false` on this laptop because the current
Python environment has `rerun-sdk` but no Rerun Viewer executable in `PATH`.
This avoids the `Failed to find Rerun Viewer executable in PATH` startup error.

Episode controls:

- Right Arrow: finish and save current episode.
- Left Arrow: discard and rerecord current episode.
- Esc: stop collection.
- If keyboard input does not work, let the episode end at the 30 second limit.

## Episode semantics

Each episode should contain exactly one clean pickup-and-putdown attempt:

1. Start from the shared home pose.
2. Approach the object.
3. Fully close the gripper to grasp.
4. Lift and move above the tray.
5. Stop the end effector above the tray.
6. Slowly open the gripper.
7. Hold still for `0.5-1.0s`.
8. End the episode immediately after the object is stable in the tray.

Do not include:

- Recovery motions after a failed grasp.
- Opening the gripper while still moving.
- Returning home after release.
- Moving the tray or cameras during the run.
- Repeated exploratory gripper open/close before ending.

## Validate after collection

```powershell
cd D:\lerobot\soarm101
powershell -ExecutionPolicy Bypass -File .\scripts\collect\validate_final_pilot.ps1
```

The validator checks metadata, episode count, feature shapes, task string,
NaNs, action movement, gripper movement, video existence/decoding, and writes
release-tail review frames to:

```text
data/so101-left-final-pilot/validation_review
```

Result meanings:

- `PASS`: ready for cloud quick fine-tuning.
- `FIX BEFORE TRAINING`: format is usable, but inspect/recollect suspect episodes.
- `BLOCKED`: format or required data is wrong; do not train.

## Log template

After validation, add this to `docs/collect-log.md`:

```markdown
## 采集记录 2026-05-14

- 数据集名称：so101-left-final-pilot
- 采集对象：最终物块 + 最终托盘
- 采集条数：10 episodes
- 任务字符串：Pick up object and Put down in box
- 区域：left
- FPS：10
- 验证结果：PASS / FIX BEFORE TRAINING / BLOCKED
- 主要问题：
- 下一步计划：上传云端并快速微调 diffusion-left-sota
```
