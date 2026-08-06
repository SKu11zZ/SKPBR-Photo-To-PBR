#!/usr/bin/env python3
"""D69 warm-start intrinsic decomposition on top of the frozen D57 model.

The D57 parent remains the source of all physical maps.  This stage replaces
only BaseColor through an explicit illumination estimate and a physically
gated residual path.  Zero-initialized residuals make epoch zero reproduce the
D57 maps exactly, including every non-BaseColor pixel.
"""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F

from . import runtime as common
from .prompt import ATTRIBUTE_DIM


def _groups(channels: int) -> int:
    for groups in (8, 4, 2, 1):
        if channels % groups == 0:
            return groups
    return 1


def _gradient_magnitude(value: torch.Tensor) -> torch.Tensor:
    dx, dy = common.gradient(value.float())
    return (dx.square() + dy.square() + 1.0e-8).sqrt()


def _lowpass(value: torch.Tensor, size: int = 48) -> torch.Tensor:
    height, width = value.shape[-2:]
    pooled = F.adaptive_avg_pool2d(value.float(), (min(size, height), min(size, width)))
    return F.interpolate(pooled, (height, width), mode="bilinear", align_corners=False)


class SeparableResidual(nn.Module):
    def __init__(self, channels: int, expansion: int = 2) -> None:
        super().__init__()
        hidden = channels * expansion
        self.depthwise = nn.Conv2d(
            channels,
            channels,
            3,
            padding=1,
            padding_mode="reflect",
            groups=channels,
        )
        self.norm = nn.GroupNorm(_groups(channels), channels)
        self.expand = nn.Conv2d(channels, hidden, 1)
        self.project = nn.Conv2d(hidden, channels, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = F.silu(self.norm(self.depthwise(value)), inplace=True)
        residual = self.project(F.silu(self.expand(residual), inplace=True))
        return value + residual


class D69IntrinsicBaseColor(nn.Module):
    """Predict nuisances, then refine D57 BaseColor through a gated quotient."""

    WIDTH = 32
    PROMPT = 16

    def __init__(self) -> None:
        super().__init__()
        prompt_dim = common.CONDITION_DIM + ATTRIBUTE_DIM
        self.prompt = nn.Sequential(
            nn.Linear(prompt_dim, 64),
            nn.LayerNorm(64),
            nn.SiLU(inplace=True),
            nn.Linear(64, self.PROMPT),
            nn.SiLU(inplace=True),
        )
        # RGB input, D57 BaseColor, analytic RGB illumination, its low pass,
        # two scalar edge cues, one highlight cue, plus Prompt context.
        input_channels = 3 + 3 + 3 + 3 + 1 + 1 + 1 + self.PROMPT
        self.stem = nn.Sequential(
            nn.Conv2d(
                input_channels,
                self.WIDTH,
                3,
                padding=1,
                padding_mode="reflect",
            ),
            nn.GroupNorm(_groups(self.WIDTH), self.WIDTH),
            nn.SiLU(inplace=True),
        )
        self.blocks = nn.Sequential(*[SeparableResidual(self.WIDTH) for _ in range(4)])
        self.coarse = nn.Sequential(
            nn.Conv2d(self.WIDTH, 40, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(40), 40),
            nn.SiLU(inplace=True),
            SeparableResidual(40),
            SeparableResidual(40),
            nn.Conv2d(40, self.WIDTH, 1),
        )
        # illumination RGB delta, specular, color edge, geometry edge, gate,
        # and a bounded RGB reflectance residual.
        self.head = nn.Conv2d(self.WIDTH * 2, 10, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        # Start at fifteen percent: close enough to the D57 BaseColor to preserve
        # the warm start, but unlike clamp(0) this has a healthy gradient.
        self.fusion_strength_logit = nn.Parameter(torch.tensor(-1.734601))

    def forward(
        self,
        image_srgb: torch.Tensor,
        parent_base_srgb: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        valid_mask: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        image_linear = common.srgb_to_linear(image_srgb.float().clamp(0.0, 1.0))
        parent_linear = common.srgb_to_linear(
            parent_base_srgb.float().clamp(1.0e-4, 1.0)
        )
        valid = valid_mask.float().clamp(0.0, 1.0)
        analytic_log_illumination = (
            torch.log(image_linear + 0.02) - torch.log(parent_linear + 0.02)
        ).clamp(-3.5, 2.0)
        analytic_illumination = torch.exp(analytic_log_illumination).clamp(0.03, 3.0)
        low_illumination = _lowpass(analytic_illumination, 48)
        weights = image_linear.new_tensor([0.2126, 0.7152, 0.0722])[None, :, None, None]
        image_luma = (image_linear * weights).sum(dim=1, keepdim=True)
        parent_luma = (parent_linear * weights).sum(dim=1, keepdim=True)
        image_edge = _gradient_magnitude(image_luma)
        parent_edge = _gradient_magnitude(parent_luma)
        highlight = (
            image_luma - _lowpass(image_luma, 32)
        ).clamp_min(0.0) / (image_luma + 0.05)
        encoded = self.prompt(torch.cat([condition.float(), attributes.float()], dim=1))
        encoded = encoded[:, :, None, None].expand(-1, -1, *image_srgb.shape[-2:])
        feature = self.stem(
            torch.cat(
                [
                    image_linear,
                    parent_linear,
                    analytic_illumination,
                    low_illumination,
                    image_edge,
                    parent_edge,
                    highlight,
                    encoded,
                ],
                dim=1,
            )
        )
        detail = self.blocks(feature)
        coarse_size = (min(128, detail.shape[-2]), min(128, detail.shape[-1]))
        coarse = F.adaptive_avg_pool2d(detail, coarse_size)
        coarse = self.coarse(coarse)
        coarse = F.interpolate(coarse, detail.shape[-2:], mode="bilinear", align_corners=False)
        raw = self.head(torch.cat([detail, coarse], dim=1)).float()

        illumination = (
            analytic_illumination * torch.exp(torch.tanh(raw[:, :3]) * 0.75)
        ).clamp(0.025, 3.0)
        specular = torch.sigmoid(raw[:, 3:4])
        color_edge = torch.sigmoid(raw[:, 4:5])
        geometry_edge = torch.sigmoid(raw[:, 5:6])
        learned_gate = torch.sigmoid(raw[:, 6:7])
        effective_gate = (
            learned_gate
            * (0.12 + 0.88 * color_edge)
            * (1.0 - 0.78 * specular)
            * (1.0 - 0.12 * geometry_edge)
            * valid
        ).clamp(0.0, 1.0)
        quotient = (image_linear + 0.02) / illumination - 0.02
        candidate = (quotient + torch.tanh(raw[:, 7:10]) * 0.20).clamp(0.0, 1.0)
        fusion_strength = torch.sigmoid(self.fusion_strength_logit)
        # Low-frequency de-lighting must be allowed over the whole surface.
        # Only the high-frequency RGB residual is edge gated.  The first D69
        # attempt incorrectly applied the detail gate to both paths and could
        # improve the frozen validation MAE by only 0.22 percent in one epoch.
        coarse_gate = fusion_strength * (1.0 - specular * 0.48) * valid
        coarse_base = (
            parent_linear * (1.0 - coarse_gate) + quotient * coarse_gate
        )
        physical_gate = effective_gate * fusion_strength
        base_linear = (
            coarse_base + torch.tanh(raw[:, 7:10]) * 0.20 * physical_gate
        ).clamp(0.0, 1.0)
        return {
            "basecolor_linear": base_linear,
            "illumination": illumination * valid,
            "specular_mask": specular * valid,
            "color_edge": color_edge * valid,
            "geometry_edge": geometry_edge * valid,
            "skip_gate": learned_gate * valid,
            "effective_gate": effective_gate,
            "physical_gate": physical_gate,
            "coarse_gate": coarse_gate,
            "fusion_strength": fusion_strength,
            "raw": raw,
        }


class D57IntrinsicRecoveryNet(nn.Module):
    """Frozen D57 plus a BaseColor-only intrinsic decomposition replacement."""

    def __init__(self, parent: nn.Module) -> None:
        super().__init__()
        self.parent = parent
        self.intrinsic = D69IntrinsicBaseColor()
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)

    def train(self, mode: bool = True):
        super().train(mode)
        self.parent.eval()
        return self

    def forward(
        self,
        image_srgb: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        valid_mask: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        if valid_mask is None:
            valid_mask = image_srgb.new_ones(
                (image_srgb.shape[0], 1, *image_srgb.shape[-2:])
            )
        with torch.no_grad():
            batch, _channels, height, width = image_srgb.shape
            presence = valid_mask.to(dtype=image_srgb.dtype)
            old = image_srgb.new_zeros((batch, 6, height, width))
            rich = image_srgb.new_zeros((batch, 12, height, width))
            parent_result = self.parent(
                image_srgb, presence, condition, old, rich, attributes
            )
            parent_maps = parent_result["maps"].float()
        intrinsic = self.intrinsic(
            image_srgb,
            parent_maps[:, :3],
            condition,
            attributes,
            valid_mask,
        )
        base_srgb = common.linear_to_srgb(intrinsic["basecolor_linear"]).clamp(0.0, 1.0)
        maps = torch.cat([base_srgb, parent_maps[:, 3:]], dim=1)
        return intrinsic | {
            "maps": maps,
            "parent_maps": parent_maps,
            "parent_basecolor_linear": common.srgb_to_linear(
                parent_maps[:, :3].clamp(0.0, 1.0)
            ),
        }


def manifest(model: D57IntrinsicRecoveryNet) -> dict[str, object]:
    total = sum(parameter.numel() for parameter in model.parameters())
    parent = sum(parameter.numel() for parameter in model.parent.parameters())
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    return {
        "architecture": "D57IntrinsicRecoveryNet-D69",
        "parameters": total,
        "d57_parent_parameters": parent,
        "intrinsic_parameters": total - parent,
        "trainable_parameters": trainable,
        "warm_started_from_d57": True,
        "training_from_scratch": False,
        "non_basecolor_maps_from_frozen_d57": True,
        "unconditional_rgb_skip": False,
        "explicit_intermediates": [
            "illumination-free linear BaseColor",
            "RGB illumination/shadow field",
            "specular mask",
            "color-edge mask",
            "geometry-edge mask",
            "physical high-resolution gate",
        ],
    }
