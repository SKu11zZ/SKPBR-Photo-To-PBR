#!/usr/bin/env python3
"""Audit the public SKPBR tree for accidental private-data disclosure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import torch
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "src" / "skpbr" / "weights" / "skpbr_v0_1_state_dict.pt"
RELEASE_OUTPUT_DIR = ROOT / "docs" / "release"
TEXT_SUFFIXES = {
    ".cff",
    ".gitignore",
    ".json",
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
EXCLUDED_OUTPUTS = {"release_audit.json", "release_manifest.json"}
PUBLIC_EXAMPLE_PROMPTS = {
    "dark-rubber": "dark rubber, rough matte finish",
    "rough-steel": "rough coarse steel",
    "white-marble": "white marble with subtle gray veins, polished finish",
    "cyan-automotive-clearcoat": "cyan blue automotive clearcoat, glossy metallic finish",
}
PUBLIC_EXAMPLE_MAPS = ("basecolor", "roughness", "metallic", "normal", "height", "ao")
COVERAGE_EXAMPLES = {
    "brushed-aluminum": (
        "拉丝铝 / Brushed Aluminum",
        "brushed aluminum with fine directional scratches, satin metallic finish",
    ),
    "oxidized-copper": (
        "氧化铜 / Oxidized Copper",
        "oxidized copper with irregular green patina and exposed warm copper",
    ),
    "red-powder-coated-steel": (
        "红色粉末涂层钢 / Red Powder-Coated Steel",
        "deep red powder-coated steel with fine orange-peel texture, semi-matte finish",
    ),
    "black-abs-plastic": (
        "黑色 ABS 塑料 / Black ABS Plastic",
        "black ABS plastic with subtle molded grain, matte finish",
    ),
    "speckled-granite": (
        "斑点花岗岩 / Speckled Granite",
        "gray speckled granite with black and pale mineral grains, honed finish",
    ),
    "weathered-concrete": (
        "风化混凝土 / Weathered Concrete",
        "weathered gray concrete with pores, aggregate marks and a rough dry surface",
    ),
    "red-brick": (
        "红砖 / Red Brick",
        "fired red brick with warm color variation, fine pits and a dry rough finish",
    ),
    "blue-glazed-ceramic": (
        "蓝色釉面陶瓷 / Blue Glazed Ceramic",
        "cobalt blue glazed ceramic with subtle cloudy variation and glossy finish",
    ),
    "carbon-fiber": (
        "碳纤维复合材料 / Carbon Fiber Composite",
        "dark carbon fiber composite with a fine two-by-two twill weave and satin clear coat",
    ),
    "natural-cork": (
        "天然软木 / Natural Cork",
        "natural tan cork with irregular dark pores and a dry matte surface",
    ),
    "brown-grain-leather": (
        "棕色粒面皮革 / Brown Grain Leather",
        "medium brown grain leather with natural creases and a soft semi-matte finish",
    ),
    "blue-denim": (
        "蓝色牛仔布 / Blue Denim Fabric",
        "indigo blue denim fabric with visible diagonal twill weave and a dry soft finish",
    ),
}
PUBLIC_SHEET_DIMENSIONS = {
    "examples/public/contact_sheet.png": (1900, 1725),
    "examples/coverage-12/contact_sheet_long.png": (2160, 5040),
    "examples/coverage-12/contact_sheet_part_01.png": (2160, 1770),
    "examples/coverage-12/contact_sheet_part_02.png": (2160, 1620),
    "examples/coverage-12/contact_sheet_part_03.png": (2160, 1650),
}
ALLOWED_PUBLIC_PNGS = set(PUBLIC_SHEET_DIMENSIONS)
for _slug in PUBLIC_EXAMPLE_PROMPTS:
    ALLOWED_PUBLIC_PNGS.update(
        {
            f"examples/public/{_slug}/input.png",
            f"examples/public/{_slug}/output_render.png",
            *(f"examples/public/{_slug}/maps/{name}.png" for name in PUBLIC_EXAMPLE_MAPS),
        }
    )
for _slug in COVERAGE_EXAMPLES:
    ALLOWED_PUBLIC_PNGS.update(
        {
            f"examples/coverage-12/materials/{_slug}/input.png",
            f"examples/coverage-12/materials/{_slug}/output_render.png",
            *(
                f"examples/coverage-12/materials/{_slug}/maps/{name}.png"
                for name in PUBLIC_EXAMPLE_MAPS
            ),
        }
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.name not in EXCLUDED_OUTPUTS
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
            and relative not in ALLOWED_PUBLIC_PNGS
        ):
            forbidden_assets.append(relative)
        if relative in ALLOWED_PUBLIC_PNGS:
            expected_dimensions = PUBLIC_SHEET_DIMENSIONS.get(relative, (1024, 1024))
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
        ALLOWED_PUBLIC_PNGS.difference(relative_files)
    )
    prompt_mismatches = []
    for slug, expected in PUBLIC_EXAMPLE_PROMPTS.items():
        relative = f"examples/public/{slug}/prompt.txt"
        path = relative_files.get(relative)
        actual = path.read_text(encoding="utf-8").strip() if path else None
        if actual != expected:
            prompt_mismatches.append(
                {"file": relative, "expected": expected, "actual": actual}
            )
    for slug, (expected_name, expected_prompt) in COVERAGE_EXAMPLES.items():
        root = f"examples/coverage-12/materials/{slug}"
        checks = {
            f"{root}/material_name.txt": expected_name,
            f"{root}/prompt_en.txt": expected_prompt,
        }
        for relative, expected in checks.items():
            path = relative_files.get(relative)
            actual = path.read_text(encoding="utf-8").strip() if path else None
            if actual != expected:
                prompt_mismatches.append(
                    {"file": relative, "expected": expected, "actual": actual}
                )
        relative = f"{root}/prompt_zh-CN.txt"
        path = relative_files.get(relative)
        actual = path.read_text(encoding="utf-8").strip() if path else None
        if not actual or not actual.endswith("中文译文仅用于展示，未输入模型。"):
            prompt_mismatches.append(
                {
                    "file": relative,
                    "expected": "Chinese display translation ending with the non-input disclosure",
                    "actual": actual,
                }
            )
    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)
    state = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    checkpoint_tensor_only = (
        isinstance(state, dict)
        and len(state) == 104
        and all(isinstance(key, str) for key in state)
        and all(torch.is_tensor(value) for value in state.values())
    )
    parameter_count = sum(int(value.numel()) for value in state.values())
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
        and not prompt_mismatches
        and checkpoint_tensor_only
        and parameter_count == 266_241
        and not checkpoint_private_hits
    )
    manifest = {
        "schema": "skpbr-public-release-manifest-v1",
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
        "schema": "skpbr-public-release-audit-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "checks": {
            "local_absolute_paths": absolute_path_hits,
            "private_workspace_tokens": private_token_hits,
            "forbidden_image_or_scene_assets": forbidden_assets,
            "missing_public_example_files": missing_public_example_files,
            "invalid_public_example_dimensions": invalid_example_dimensions,
            "public_example_prompt_mismatches": prompt_mismatches,
            "approved_public_example_png_count": len(ALLOWED_PUBLIC_PNGS),
            "checkpoint_tensor_only": checkpoint_tensor_only,
            "checkpoint_state_tensors": len(state) if isinstance(state, dict) else 0,
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
    parser.add_argument("--check-only", action="store_true")
    options = parser.parse_args()
    report, manifest = audit()
    if not options.check_only:
        RELEASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (RELEASE_OUTPUT_DIR / "release_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (RELEASE_OUTPUT_DIR / "release_audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
