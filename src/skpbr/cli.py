"""Command-line interface for planar image+text reconstruction and text-only generation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import torch

from .io import (
    load_rgb,
    render_plane,
    save_json,
    save_map_set,
    save_preview,
    sha256,
)
from .model import (
    StructuredReliefSpatialPBRNet,
    isotropic_multiscale_seed_field,
    parameter_manifest,
)
from .prompt import parse_prompt


DEFAULT_CHECKPOINT_SHA256 = "cd8611c0e721c0c917e9edba07a74256ed6ba68f047a681bdf11327924d4e970"


def default_checkpoint() -> str:
    return str(Path(__file__).resolve().parent / "weights" / "skpbr_v0_3_structured_relief.pt")


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable; use --device cpu")
    return torch.device(requested)


def load_model(checkpoint: Path, device: torch.device) -> tuple[StructuredReliefSpatialPBRNet, dict[str, object]]:
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    digest = sha256(checkpoint)
    if checkpoint.resolve() == Path(default_checkpoint()).resolve() and digest != DEFAULT_CHECKPOINT_SHA256:
        raise RuntimeError("Bundled checkpoint SHA-256 mismatch")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
        raise RuntimeError("Expected a tensor-only SKPBR v0.3 checkpoint payload")
    model = StructuredReliefSpatialPBRNet()
    model.load_state_dict(payload["model"], strict=True)
    model.requires_grad_(False)
    return model.to(device).eval(), payload


@torch.inference_mode()
def run(options: argparse.Namespace) -> dict[str, object]:
    output = Path(options.output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {output}")
    resolution = int(getattr(options, "resolution", 512))
    if resolution < 128 or resolution > 1024 or resolution % 16:
        raise ValueError("Resolution must be a multiple of 16 between 128 and 1024")
    device = resolve_device(str(options.device))
    checkpoint = Path(options.checkpoint)
    model, payload = load_model(checkpoint, device)
    parsed = parse_prompt(str(options.prompt))
    condition = torch.from_numpy(parsed["condition"]).unsqueeze(0).to(device)
    attributes = torch.from_numpy(parsed["attributes"]).unsqueeze(0).to(device)
    seed = torch.tensor([int(options.seed)], dtype=torch.long, device=device)
    image_path = Path(options.image) if getattr(options, "image", None) else None

    if image_path is not None:
        mode = "image_prompt_reconstruction"
        image = load_rgb(image_path, resolution).unsqueeze(0).to(device)
        presence = image.new_ones((1, 1, resolution, resolution))
        seed_field = image.new_zeros((1, 6, resolution, resolution))
        rich_seed = image.new_zeros((1, 12, resolution, resolution))
    else:
        mode = "prompt_seed_generation"
        image = torch.zeros((1, 3, resolution, resolution), device=device)
        presence = torch.zeros((1, 1, resolution, resolution), device=device)
        rich_seed = isotropic_multiscale_seed_field(seed, resolution, resolution)
        seed_field = rich_seed[:, :6]

    with torch.autocast(
        device_type=device.type,
        dtype=torch.float16,
        enabled=device.type == "cuda",
    ):
        maps = model(image, presence, condition, seed_field, rich_seed, attributes)["maps"][0]

    output.mkdir(parents=True, exist_ok=True)
    save_map_set(output / "maps", maps)
    save_preview(output / "preview.png", render_plane(maps.unsqueeze(0), variant=0)[0])
    metadata: dict[str, object] = {
        "schema": "skpbr-v0.3-structured-relief-inference",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "mode_semantics": (
            "visible aligned planar material reconstruction"
            if image_path is not None
            else "plausible deterministic material candidate; not source reconstruction"
        ),
        "prompt": str(options.prompt),
        "parsed_prompt": {
            "material_class": parsed["material_class"],
            "physical_regime": parsed["physical_regime"],
            "base_color": parsed["base_color"],
            "secondary_color": parsed["secondary_color"],
            "finish": parsed["finish"],
            "relief": parsed["relief"],
        },
        "seed": int(options.seed) if image_path is None else None,
        "resolution": [resolution, resolution],
        "maps": ["BaseColor", "Roughness", "Metallic", "Normal OpenGL +Y", "Height", "AO"],
        "model": parameter_manifest(model),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoch": payload.get("selected_epoch", payload.get("epoch")),
        "target_or_library_asset_reads": 0,
        "known_status": {
            "image_prompt_mode": "research preview; Blind-F failed BaseColor, micro-normal and color-to-geometry leakage gates",
            "prompt_only_mode": "experimental; Blind-F material identity passed 2/12",
            "resolution": "512 px is the evaluated release resolution",
        },
    }
    save_json(output / "inference_manifest.json", metadata)
    return metadata


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct PBR maps from an aligned flat image plus text, or generate an experimental text-only candidate."
    )
    parser.add_argument("--image", type=Path, help="Optional aligned planar RGB material image")
    parser.add_argument("--prompt", required=True, help="English or Chinese material description")
    parser.add_argument("--seed", type=int, default=41, help="Deterministic text-only variation seed")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=Path(default_checkpoint()))
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--resolution", type=int, default=512, help="Evaluated at 512; multiples of 16 from 128 to 1024 are accepted")
    return parser.parse_args()


def main() -> None:
    metadata = run(arguments())
    if metadata["mode"] == "prompt_seed_generation":
        print("WARNING: text-only generation is experimental and passed only 2/12 Blind-F material identities.")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
