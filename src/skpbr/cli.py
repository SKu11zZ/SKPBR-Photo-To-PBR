"""Command-line entry point for the SKPBR v0.1 calibration head."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import time

import torch
import torch.nn.functional as F

from .io import (
    NON_BASECOLOR_MAPS,
    original_map_size,
    parent_tensor,
    save_rgb,
    screen_tensor,
    sha256,
)
from .model import SKPBRBaseColorCalibrator, parameter_count
from .prompt import CONDITION_DIM, parse_prompt


EXPECTED_PARAMETERS = 266_241
HARD_MAX_GIB = 8.0
ABORT_GUARD_GIB = 7.8


def default_checkpoint() -> Path:
    return Path(str(files("skpbr").joinpath("weights/skpbr_v0_1_state_dict.pt")))


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the SKPBR v0.1 BaseColor calibration head."
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--parent-dir", type=Path, required=True)
    parser.add_argument("--visible-confidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=default_checkpoint())
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default="auto"
    )
    return parser.parse_args()


def select_device(requested: str) -> torch.device:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    return torch.device(requested)


def validate_inputs(options: argparse.Namespace) -> None:
    required = [
        options.image,
        options.visible_confidence,
        options.checkpoint,
        options.parent_dir / "basecolor.png",
        *(options.parent_dir / f"{name}.png" for name in NON_BASECOLOR_MAPS),
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if options.output.exists():
        raise RuntimeError(f"Refusing to overwrite {options.output}")


def load_model(checkpoint: Path, device: torch.device) -> SKPBRBaseColorCalibrator:
    state = torch.load(checkpoint, map_location=device, weights_only=True)
    if not isinstance(state, dict) or not state:
        raise RuntimeError("SKPBR checkpoint is not a state dictionary")
    if not all(isinstance(key, str) and torch.is_tensor(value) for key, value in state.items()):
        raise RuntimeError("SKPBR checkpoint contains non-tensor metadata")
    model = SKPBRBaseColorCalibrator().to(device)
    model.load_state_dict(state, strict=True)
    model.screen_feature_scale = 0.0
    model.eval().requires_grad_(False)
    if parameter_count(model) != EXPECTED_PARAMETERS:
        raise RuntimeError("SKPBR parameter count changed")
    return model


def device_used_gib() -> float:
    free, total = torch.cuda.mem_get_info()
    return (total - free) / 1024**3


@torch.inference_mode()
def run(options: argparse.Namespace) -> dict[str, object]:
    validate_inputs(options)
    device = select_device(options.device)
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model = load_model(options.checkpoint, device)
    size = original_map_size(options.parent_dir)
    screen = screen_tensor(options.image, device)
    parent_512 = parent_tensor(
        options.parent_dir,
        options.visible_confidence,
        device,
        size=512,
    )
    parent_original = parent_tensor(
        options.parent_dir,
        options.visible_confidence,
        device,
        size=size,
    )
    parsed = parse_prompt(options.prompt)
    condition = torch.tensor(
        parsed["condition_vector"], dtype=torch.float32, device=device
    )[None]
    if condition.shape != (1, CONDITION_DIM):
        raise RuntimeError("Prompt condition contract changed")
    context = (
        torch.amp.autocast("cuda", dtype=torch.float16)
        if device.type == "cuda"
        else nullcontext()
    )
    with context:
        result = model(screen, parent_512, condition)
    residual = F.interpolate(
        result["residual"].float(),
        size=(size, size),
        mode="bicubic",
        align_corners=False,
    )
    basecolor = (
        parent_original[:, :3]
        * torch.exp(result["log_gain"].float()[:, :, None, None])
        + result["bias"].float()[:, :, None, None]
        + residual
    ).clamp(0.0, 1.0)
    peak_allocated = (
        torch.cuda.max_memory_allocated() / 1024**3
        if device.type == "cuda"
        else 0.0
    )
    whole_device = device_used_gib() if device.type == "cuda" else 0.0
    if peak_allocated >= ABORT_GUARD_GIB or whole_device >= ABORT_GUARD_GIB:
        raise RuntimeError(
            "SKPBR reached the 7.8 GiB abort guard: "
            f"allocated={peak_allocated:.3f}, whole_device={whole_device:.3f}"
        )

    temporary = options.output.with_name(options.output.name + ".writing")
    if temporary.exists():
        raise RuntimeError(f"Partial temporary output exists: {temporary}")
    temporary.mkdir(parents=True, exist_ok=False)
    save_rgb(temporary / "basecolor.png", basecolor)
    passthrough = []
    for name in NON_BASECOLOR_MAPS:
        source = options.parent_dir / f"{name}.png"
        destination = temporary / f"{name}.png"
        shutil.copy2(source, destination)
        source_hash = sha256(source)
        output_hash = sha256(destination)
        passthrough.append(
            {
                "map": name,
                "source_sha256": source_hash,
                "output_sha256": output_hash,
                "bit_exact": source_hash == output_hash,
            }
        )
    if not all(bool(row["bit_exact"]) for row in passthrough):
        raise RuntimeError("A non-BaseColor map changed")
    metadata = {
        "schema": "skpbr-v0.1-runtime-v1",
        "model": "SKPBR",
        "version": "0.1.0",
        "research_preview": True,
        "prompt": options.prompt,
        "parsed_prompt": {
            "archetype": parsed["archetype"],
            "color": parsed["color"],
            "finish": parsed["finish"],
            "spatial_family": parsed["spatial_family"],
            "spatial_effects": parsed["spatial_effects"],
        },
        "model_parameter_count": parameter_count(model),
        "screen_feature_scale": 0.0,
        "output_resolution": [size, size],
        "correction": {
            "log_gain": result["log_gain"][0].float().cpu().tolist(),
            "bias": result["bias"][0].float().cpu().tolist(),
            "residual_mean_abs": float(residual.abs().mean()),
            "residual_max_abs": float(residual.abs().amax()),
        },
        "non_basecolor_passthrough": passthrough,
        "runtime_asset_reads": {
            "input_image": 1,
            "parent_prediction": 1,
            "visible_confidence": 1,
            "checkpoint": 1,
            "training_images": 0,
            "target_maps": 0,
            "source_material_library": 0,
            "nearest_neighbors": 0,
        },
        "files": {
            "input_name": options.image.name,
            "checkpoint_sha256": sha256(options.checkpoint),
            "input_sha256": sha256(options.image),
            "basecolor_sha256": sha256(temporary / "basecolor.png"),
        },
        "device": str(device),
        "peak_allocated_vram_gib": peak_allocated,
        "peak_whole_device_vram_gib": whole_device,
        "peak_vram_gib_hard_max": HARD_MAX_GIB,
        "runtime_seconds": time.perf_counter() - started,
    }
    (temporary / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    options.output.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temporary, options.output)
    return metadata


def main() -> None:
    metadata = run(arguments())
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
