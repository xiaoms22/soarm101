#!/usr/bin/env python
"""Download the SO-ARM101 diffusion-left-sota policy from Hugging Face.

The upstream package is a Hugging Face *dataset* repository whose trained
policies live under models/. LeRobot expects a local policy directory
containing config.json, model.safetensors, and processor files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download


REPO_ID = "Full-Stack-Entity/so101-left-sota-pack"
REPO_TYPE = "dataset"
MODEL_SUBDIR = "models/diffusion-left-sota"
FILES = [
    "config.json",
    "model.safetensors",
    "policy_preprocessor.json",
    "policy_preprocessor_step_3_normalizer_processor.safetensors",
    "policy_postprocessor.json",
    "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    "train_config.json",
]


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "models" / "diffusion-left-sota"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {REPO_ID}/{MODEL_SUBDIR}")
    print(f"Target: {output_dir}")

    for name in FILES:
        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            filename=f"{MODEL_SUBDIR}/{name}",
        )
        target = output_dir / name
        shutil.copy2(downloaded, target)
        print(f"ok  {target.name}")

    print("\nDone. Use this policy path:")
    print(output_dir)


if __name__ == "__main__":
    main()
