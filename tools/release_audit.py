#!/usr/bin/env python3
"""Audit the public SKPBR tree for accidental private-data disclosure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

import torch
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "src" / "skpbr" / "weights" / "skpbr_v0_5_fixed_data_optimized.pt"
TEXT_SUFFIXES = {
    ".cff",
    ".gitignore",
    ".json",
    ".html",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
FORBIDDEN_ASSET_SUFFIXES = {
    ".blend",
    ".exr",
    ".hdr",
    ".jpeg",
    ".jpg",
    ".npz",
    ".png",
    ".tif",
    ".tiff",
}
INTERNAL_TOKENS = (
    "LightStage" + "Build",
    "jishu" + "yuan",
    "r1_" + "mvp",
    "d37s12" + "shadow",
    "source_" + "identity",
    "map_" + "root",
    "basecolor_" + "override",
    "training_" + "target",
)
PUBLIC_IMAGE_DIMENSIONS = {
    "docs/assets/skpbr_v05_bright_studio_2x3.png": (1920, 1280),
    "examples/plane-d41/fresh12b_contact_sheet.jpg": (1680, 4190),
    "examples/plane-d41/same_material_color_b_contact_sheet.jpg": (1680, 1470),
    "examples/blind-g/blind_g_best_01_02.png": (2800, 1620),
    "examples/blind-g/blind_g_best_03_04.png": (2800, 1620),
    "examples/blind-g/blind_g_representative_issues_01_02.png": (2800, 1620),
}
ALLOWED_PUBLIC_IMAGES = set(PUBLIC_IMAGE_DIMENSIONS)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        ROOT / relative.decode("utf-8")
        for relative in result.stdout.split(b"\0")
        if relative and (ROOT / relative.decode("utf-8")).is_file()
    )


def audit() -> tuple[dict[str, object], dict[str, object]]:
    files = repository_files()
    relative_files = {path.relative_to(ROOT).as_posix(): path for path in files}
    absolute_path_hits = []
    private_token_hits = []
    forbidden_assets = []
    invalid_example_dimensions = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if (
            path.suffix.casefold() in FORBIDDEN_ASSET_SUFFIXES
            and relative not in ALLOWED_PUBLIC_IMAGES
        ):
            forbidden_assets.append(relative)
        if relative in ALLOWED_PUBLIC_IMAGES:
            expected_dimensions = PUBLIC_IMAGE_DIMENSIONS[relative]
            with Image.open(path) as image:
                if image.size != expected_dimensions:
                    invalid_example_dimensions.append(
                        {
                            "file": relative,
                            "dimensions": list(image.size),
                            "expected": list(expected_dimensions),
                        }
                    )
        if path.suffix.casefold() in TEXT_SUFFIXES or path.name == ".gitignore":
            value = path.read_text(encoding="utf-8")
            if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", value):
                absolute_path_hits.append(relative)
            for token in INTERNAL_TOKENS:
                if token.casefold() in value.casefold():
                    private_token_hits.append({"file": relative, "token": token})
    missing_public_example_files = sorted(
        ALLOWED_PUBLIC_IMAGES.difference(relative_files)
    )
    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)
    payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    state = payload.get("model") if isinstance(payload, dict) else None
    checkpoint_tensor_only = (
        isinstance(state, dict)
        and len(state) == 406
        and all(isinstance(key, str) for key in state)
        and all(torch.is_tensor(value) for value in state.values())
    )
    state_tensor_elements = sum(int(value.numel()) for value in state.values())
    parameter_count = int(payload.get("parameter_count", -1))
    checkpoint_bytes = CHECKPOINT.read_bytes()
    checkpoint_private_hits = [
        token
        for token in INTERNAL_TOKENS
        if token.encode("utf-8") in checkpoint_bytes
    ]
    passed = (
        not absolute_path_hits
        and not private_token_hits
        and not forbidden_assets
        and not missing_public_example_files
        and not invalid_example_dimensions
        and checkpoint_tensor_only
        and state_tensor_elements == 4_586_980
        and parameter_count == 4_586_975
        and not checkpoint_private_hits
    )
    manifest = {
        "schema": "skpbr-public-release-manifest-v5",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    report = {
        "schema": "skpbr-public-release-audit-v5",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "checks": {
            "local_absolute_paths": absolute_path_hits,
            "private_workspace_tokens": private_token_hits,
            "forbidden_image_or_scene_assets": forbidden_assets,
            "missing_public_example_files": missing_public_example_files,
            "invalid_public_example_dimensions": invalid_example_dimensions,
            "approved_public_example_image_count": len(ALLOWED_PUBLIC_IMAGES),
            "checkpoint_tensor_only": checkpoint_tensor_only,
            "checkpoint_state_tensors": len(state) if isinstance(state, dict) else 0,
            "checkpoint_state_tensor_elements": state_tensor_elements,
            "checkpoint_parameter_count": parameter_count,
            "checkpoint_private_tokens": checkpoint_private_hits,
        },
        "excluded_private_artifact_classes": [
            "training images and PBR maps",
            "tensor and render caches",
            "resume and optimizer checkpoints",
            "sample identities and split manifests",
            "per-example shadow records",
            "third-party material assets",
        ],
    }
    return report, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optionally write the manifest and audit JSON outside the public tree.",
    )
    options = parser.parse_args()
    report, manifest = audit()
    if options.output_dir:
        options.output_dir.mkdir(parents=True, exist_ok=True)
        (options.output_dir / "release_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (options.output_dir / "release_audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
