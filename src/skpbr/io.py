"""Image, map, preview, and deterministic seed utilities."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F


MAP_FILES = ("basecolor", "roughness", "metallic", "normal", "height", "ao")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".writing")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def load_rgb(path: Path, size: int = 512) -> torch.Tensor:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as opened:
        image = opened.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(np.moveaxis(array, -1, 0).copy())


def save_map_set(root: Path, maps: torch.Tensor) -> None:
    root.mkdir(parents=True, exist_ok=True)
    value = maps.detach().float().cpu().clamp(0.0, 1.0).numpy()
    Image.fromarray(
        np.moveaxis(np.rint(value[:3] * 255.0).astype(np.uint8), 0, -1), "RGB"
    ).save(root / "basecolor.png")
    Image.fromarray(np.rint(value[3] * 255.0).astype(np.uint8), "L").save(root / "roughness.png")
    Image.fromarray(np.rint(value[4] * 255.0).astype(np.uint8), "L").save(root / "metallic.png")
    Image.fromarray(
        np.moveaxis(np.rint(value[5:8] * 255.0).astype(np.uint8), 0, -1), "RGB"
    ).save(root / "normal.png")
    Image.fromarray(np.rint(value[8] * 255.0).astype(np.uint8), "L").save(root / "height.png")
    Image.fromarray(np.rint(value[9] * 255.0).astype(np.uint8), "L").save(root / "ao.png")


def periodic_seed_field(
    seeds: torch.Tensor,
    height: int,
    width: int,
    *,
    channels: int = 6,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    seeds_i = seeds.to(dtype=torch.long).reshape(-1)
    yy = torch.arange(height, device=seeds.device, dtype=torch.float32) / max(height, 1)
    xx = torch.arange(width, device=seeds.device, dtype=torch.float32) / max(width, 1)
    grid_y, grid_x = torch.meshgrid(yy, xx, indexing="ij")
    fields = []
    for channel in range(channels):
        code = seeds_i + 104729 * (channel + 1)
        fx = (code.remainder(13) + 1).float()[:, None, None]
        fy = ((code // 17).remainder(13) + 1).float()[:, None, None]
        gx = ((code // 31).remainder(29) + 2).float()[:, None, None]
        gy = ((code // 47).remainder(29) + 2).float()[:, None, None]
        phase = ((code // 61).remainder(1009)).float()[:, None, None]
        phase = phase / 1009.0 * (2.0 * math.pi)
        field = 0.62 * torch.sin(2.0 * math.pi * (fx * grid_x + fy * grid_y) + phase)
        field += 0.38 * torch.cos(
            2.0 * math.pi * (gx * grid_x - gy * grid_y) + phase * 1.73
        )
        fields.append(field)
    return torch.stack(fields, dim=1).to(dtype=dtype)


def _srgb_to_linear(value: torch.Tensor) -> torch.Tensor:
    return torch.where(
        value <= 0.04045,
        value / 12.92,
        ((value + 0.055) / 1.055).clamp_min(0.0).pow(2.4),
    )


def _linear_to_srgb(value: torch.Tensor) -> torch.Tensor:
    value = value.clamp_min(0.0)
    return torch.where(
        value <= 0.0031308,
        value * 12.92,
        1.055 * value.pow(1.0 / 2.4) - 0.055,
    )


def render_plane(maps: torch.Tensor, *, variant: int = 0) -> torch.Tensor:
    """Compact GGX-like preview renderer for an aligned material plane."""
    value = maps.float()
    base = _srgb_to_linear(value[:, :3].clamp(0.0, 1.0))
    roughness = value[:, 3:4].clamp(0.045, 0.98)
    metallic = value[:, 4:5].clamp(0.0, 1.0)
    normal = F.normalize(value[:, 5:8] * 2.0 - 1.0, dim=1, eps=1.0e-6)
    ao = value[:, 9:10].clamp(0.0, 1.0)
    batch, _, height, width = value.shape
    settings = (
        (-35.0, 46.0, 1.55, 0.085),
        (42.0, 38.0, 1.45, 0.075),
        (-12.0, 62.0, 1.30, 0.105),
        (58.0, 30.0, 1.62, 0.060),
    )
    az, el, strength, fill = settings[int(variant) % len(settings)]
    azimuth = torch.full((batch,), az * math.pi / 180.0, device=value.device)
    elevation = torch.full((batch,), el * math.pi / 180.0, device=value.device)
    intensity = torch.full((batch,), strength, device=value.device)
    ambient = torch.full((batch,), fill, device=value.device)
    light = torch.stack(
        [
            torch.cos(elevation) * torch.sin(azimuth),
            torch.cos(elevation) * torch.cos(azimuth),
            torch.sin(elevation),
        ],
        dim=1,
    )[:, :, None, None]
    view = value.new_tensor([0.0, 0.0, 1.0])[None, :, None, None]
    half_vector = F.normalize(light + view, dim=1, eps=1.0e-6)
    ndotl = (normal * light).sum(dim=1, keepdim=True).clamp(0.0, 1.0)
    ndotv = normal[:, 2:3].clamp(0.05, 1.0)
    ndoth = (normal * half_vector).sum(dim=1, keepdim=True).clamp(0.0, 1.0)
    vdoth = (view * half_vector).sum(dim=1, keepdim=True).clamp(0.0, 1.0)
    alpha = roughness.square().clamp_min(0.0025)
    alpha2 = alpha.square()
    denominator = (ndoth.square() * (alpha2 - 1.0) + 1.0).square()
    distribution = alpha2 / (math.pi * denominator.clamp_min(1.0e-5))
    k = (roughness + 1.0).square() / 8.0
    g_v = ndotv / (ndotv * (1.0 - k) + k).clamp_min(1.0e-5)
    g_l = ndotl / (ndotl * (1.0 - k) + k).clamp_min(1.0e-5)
    f0 = 0.04 * (1.0 - metallic) + base * metallic
    fresnel = f0 + (1.0 - f0) * (1.0 - vdoth).pow(5.0)
    specular = distribution * g_v * g_l * fresnel / (4.0 * ndotv * ndotl + 1.0e-4)
    diffuse = base * (1.0 - metallic) / math.pi
    yy = torch.linspace(-1.0, 1.0, height, device=value.device)[None, None, :, None]
    xx = torch.linspace(-1.0, 1.0, width, device=value.device)[None, None, None, :]
    gradient = 1.0 + 0.11 * (
        xx * torch.sin(azimuth)[:, None, None, None]
        + yy * torch.cos(azimuth)[:, None, None, None]
    )
    direct = (diffuse + specular) * ndotl * intensity[:, None, None, None]
    color = (direct * gradient + base * ambient[:, None, None, None]) * (0.45 + 0.55 * ao)
    return _linear_to_srgb(color).clamp(0.0, 1.0).to(dtype=maps.dtype)


def save_preview(path: Path, preview: torch.Tensor) -> None:
    array = np.moveaxis(
        np.rint(preview.detach().float().cpu().clamp(0.0, 1.0).numpy() * 255.0).astype(np.uint8),
        0,
        -1,
    )
    Image.fromarray(array, "RGB").save(path)
