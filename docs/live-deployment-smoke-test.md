# Live deployment smoke test

This test runs the policy-control loop without creating a LeRobot dataset and
without video encoding. It is the closest current check for real deployment
latency on the laptop.

## Command

```powershell
cd D:\lerobot\soarm101
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\run_live_diffusion_left_sota_smoke.ps1
```

The script runs:

```powershell
python .\scripts\deploy\live_diffusion_left_sota_smoke.py `
  --config-path .\record_config.yaml `
  --policy-path .\models\diffusion-left-sota `
  --duration-s 10 `
  --fps 10 `
  --num-inference-steps 2 `
  --max-relative-target 5 `
  --torch-threads 8 `
  --log-level ERROR
```

## Why this differs from lerobot_record

`lerobot_record` is useful for dataset-style smoke tests, but it also saves
parquet files and encodes videos. Those costs mix with control-loop latency.

The live script only does:

```text
robot observation -> policy preprocessing -> policy inference -> robot action
```

It prints timing for observation, preprocessing, policy, postprocessing, send,
and total loop time.

## Current local results

On the laptop, with `num_inference_steps=4`:

```text
steps: 91 / 10s
wall Hz: 9.10
policy p90: 174.3 ms
policy max: 184.2 ms
```

With `num_inference_steps=2`:

```text
steps: 98 / 10s
wall Hz: 9.80
policy p90: 111.5 ms
policy max: 125.6 ms
```

This shows the main bottleneck is the diffusion action-chunk generation frame,
not camera capture or serial send.

## Interpretation

Diffusion Policy generates an action chunk, then serves several actions from
cache. The slow frames are the chunk-generation frames. Lowering
`num_inference_steps` reduces the reverse diffusion work per chunk.

`num_inference_steps=2` is a flow-test setting. It is good for checking the
local deployment pipeline, but it can reduce policy quality. After fine-tuning,
compare 2, 4, 6, and 8 steps for task behavior.
