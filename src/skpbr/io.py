"""Image and tensor I/O for the source-free SKPBR runtime."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image
import torch


NON_BASECOLOR_MAPS = ("roughness", "metallic", "normal", "height", "ao")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rgb(path: Path, size: int) -> np.ndarray:
    with Image.open(path) as image:
        value = np.asarray(
            image.convert("RGB").resize(
                (size, size), Image.Resampling.LANCZOS
            ),
            dtype=np.float32,
        ).copy()
    return value / 255.0


def read_scalar(path: Path, size: int) -> np.ndarray:
    with Image.open(path) as image:
        value = np.asarray(
            image.convert("F").resize(
                (size, size), Image.Resampling.LANCZOS
            ),
            dtype=np.float32,
        ).copy()
    maximum = float(value.max())
    if maximum > 1.5:
        value /= 65535.0 if maximum > 255.0 else 255.0
    return np.clip(value, 0.0, 1.0)


def screen_tensor(path: Path, device: torch.device) -> torch.Tensor:
    value = read_rgb(path, 128)
    return torch.from_numpy(value.transpose(2, 0, 1))[None].to(device)


def parent_tensor(
    parent_dir: Path,
    confidence_path: Path,
    device: torch.device,
    *,
    size: int,
) -> torch.Tensor:
    packed = np.concatenate(
        (
            read_rgb(parent_dir / "basecolor.png", size).transpose(2, 0, 1),
            read_scalar(parent_dir / "roughness.png", size)[None],
            read_scalar(parent_dir / "metallic.png", size)[None],
            read_rgb(parent_dir / "normal.png", size).transpose(2, 0, 1),
            read_scalar(parent_dir / "height.png", size)[None],
            read_scalar(parent_dir / "ao.png", size)[None],
            read_scalar(confidence_path, size)[None],
        ),
        axis=0,
    )
    if packed.shape != (11, size, size):
        raise RuntimeError(f"Invalid parent tensor shape: {packed.shape}")
    return torch.from_numpy(packed)[None].to(device)


def original_map_size(parent_dir: Path) -> int:
    with Image.open(parent_dir / "basecolor.png") as image:
        width, height = image.size
    if width != height:
        raise ValueError("SKPBR expects square parent maps")
    if width < 512:
        raise ValueError("SKPBR expects parent maps of at least 512px")
    return int(width)


def save_rgb(path: Path, value: torch.Tensor) -> None:
    array = (
        value[0]
        .detach()
        .float()
        .clamp(0.0, 1.0)
        .cpu()
        .permute(1, 2, 0)
        .numpy()
    )
    Image.fromarray(
        np.clip(np.rint(array * 255.0), 0, 255).astype(np.uint8),
        mode="RGB",
    ).save(path)
