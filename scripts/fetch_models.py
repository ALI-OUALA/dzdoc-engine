"""Fetch reviewed OCR weights at immutable revisions; never runs at install time."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

from dzdoc.model_registry import OCR_ASSETS, VLM_ASSETS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-vlm",
        action="store_true",
        help="Also fetch the optional pinned PaddleOCR-VL fallback asset.",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = OCR_ASSETS + (VLM_ASSETS if args.include_vlm else ())
    for asset in assets:
        snapshot_download(
            repo_id=asset.repo_id,
            revision=asset.revision,
            local_dir=args.output / asset.name,
        )
        print(f"{asset.name}@{asset.revision}")


if __name__ == "__main__":
    main()
