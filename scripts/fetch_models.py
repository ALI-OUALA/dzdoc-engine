"""Fetch reviewed OCR weights at immutable revisions; never runs at install time."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

from dzdoc.model_registry import OCR_ASSETS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for asset in OCR_ASSETS:
        snapshot_download(
            repo_id=asset.repo_id,
            revision=asset.revision,
            local_dir=args.output / asset.name,
        )
        print(f"{asset.name}@{asset.revision}")


if __name__ == "__main__":
    main()
