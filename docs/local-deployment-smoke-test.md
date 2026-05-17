# Local deployment smoke test

This smoke test is for running the selected Hugging Face Diffusion Policy
through the complete local loop:

1. load policy weights,
2. connect the SO-ARM101 follower and cameras,
3. read observations,
4. run policy inference on CPU,
5. send actions to the follower arm,
6. save one short eval episode locally.

It is not expected to complete the task before fine-tuning.

This command targets LeRobot 0.5.x. Upstream main has moved policy-based
deployment out of `lerobot-record` and into `lerobot-rollout`; keep
`lerobot>=0.5.1,<0.6` until this smoke test is migrated.

## Model

- Hugging Face repo: `Full-Stack-Entity/so101-left-sota-pack`
- Repo type: dataset
- Policy directory inside the repo: `models/diffusion-left-sota`
- Local target: `models/diffusion-left-sota`

The downloaded model directory is ignored by Git through `models/`.

## Run

From PowerShell:

```powershell
cd D:\lerobot\soarm101
.\scripts\deploy\run_diffusion_left_sota_smoke.ps1
```

The script downloads the policy if needed, then runs:

```powershell
python -m lerobot.scripts.lerobot_record `
  --config_path=.\record_config.yaml `
  --policy.path=.\models\diffusion-left-sota `
  --policy.device=cpu `
  --policy.use_amp=false `
  --policy.num_inference_steps=4 `
  --robot.max_relative_target=10.0 `
  --dataset.repo_id=xiaoms22/eval_so101_local_smoke `
  --dataset.root=.\data\eval_so101_local_smoke_<timestamp> `
  --dataset.num_episodes=1 `
  --dataset.episode_time_s=10 `
  --dataset.reset_time_s=0 `
  --dataset.push_to_hub=false `
  --display_data=false `
  --play_sounds=false
```

## Safety notes

- Keep the workspace clear.
- Keep one hand near power/stop.
- Start with no object in the gripper path if you only want to test motion.
- The script clips per-step target changes with `robot.max_relative_target=10.0`.
- Press Right Arrow to end the episode early.
- Press Esc to stop recording.

## Expected result

The run is successful if the program loads the policy, connects to COM3 and both
cameras, performs policy inference, sends actions to the robot, and saves one
short local eval dataset under `data/`.

Task success is not required for this smoke test.

The original model config leaves `num_inference_steps` unset, which makes
LeRobot use the full training diffusion schedule. On this CPU-only laptop that
is too slow for an interactive smoke test, so the script uses 4 inference steps
while keeping the same model weights.
