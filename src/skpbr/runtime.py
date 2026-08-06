"""Small differentiable helpers shared by the public D72 inference stack."""

from __future__ import annotations

import torch
import torch.nn.functional as F

from .prompt import CONDITION_DIM, MATERIAL_CLASSES


def gradient(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    dx = torch.roll(value, -1, dims=-1) - value
    dy = torch.roll(value, -1, dims=-2) - value
    return dx, dy


def srgb_to_linear(value: torch.Tensor) -> torch.Tensor:
    return torch.where(
        value <= 0.04045,
        value / 12.92,
        ((value + 0.055) / 1.055).clamp_min(0.0).pow(2.4),
    )


def linear_to_srgb(value: torch.Tensor) -> torch.Tensor:
    value = value.clamp_min(0.0)
    return torch.where(
        value <= 0.0031308,
        value * 12.92,
        1.055 * value.pow(1.0 / 2.4) - 0.055,
    )


def derive_ao_torch(
    height: torch.Tensor,
    normal_01: torch.Tensor,
) -> torch.Tensor:
    """Derive AO primarily from reconstructed Height and Normal."""

    cavity = torch.zeros_like(height.float())
    for kernel, weight in ((7, 0.50), (17, 0.32), (33, 0.18)):
        horizontal = F.max_pool2d(
            height.float(), (1, kernel), stride=1, padding=(0, kernel // 2)
        )
        local_max = F.max_pool2d(
            horizontal, (kernel, 1), stride=1, padding=(kernel // 2, 0)
        )
        cavity = cavity + (local_max - height.float()).clamp_min(0.0) * weight
    normal_z = normal_01[:, 2:3].float() * 2.0 - 1.0
    return (
        torch.exp(-cavity * 7.5)
        * (0.94 + 0.06 * normal_z.clamp(0.0, 1.0))
    ).clamp(0.30, 1.0)
