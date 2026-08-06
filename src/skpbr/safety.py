#!/usr/bin/env python3
"""D72 integrated safety calibration for intrinsic BaseColor and derived AO.

This is deliberately not another spatial texture adapter.  The frozen D71
reconstruction remains the only source of spatial PBR detail.  A small global
confidence model chooses how much to trust the D69 de-lit BaseColor over its
D57 anchor and how much to trust Height/Normal-derived AO over the D57 AO.
Roughness, Metallic, Normal, and Height are returned bit-for-bit unchanged.
"""

from __future__ import annotations

import torch
from torch import nn

from . import runtime as legacy
from .albedo import AlbedoDisentangledMultimodalPBRNet
from .intrinsic import D57IntrinsicRecoveryNet
from .physical import D70JointRecoveryNet
from .prompt import ATTRIBUTE_DIM


FEATURE_DIM = 104


def _statistics(value: torch.Tensor) -> torch.Tensor:
    value = value.float()
    # The gate only needs material-level evidence.  Pooling before reductions
    # is mathematically consistent with that scope and avoids repeatedly
    # scanning 512px feature maps in the production path.
    if value.shape[-2] > 64 or value.shape[-1] > 64:
        value = torch.nn.functional.adaptive_avg_pool2d(value, (64, 64))
    flat = value.flatten(2)
    return torch.cat(
        [
            flat.mean(dim=2),
            flat.std(dim=2, unbiased=False),
            flat.amin(dim=2),
            flat.amax(dim=2),
        ],
        dim=1,
    )


class IntrinsicAOSafetyCalibration(nn.Module):
    """Predict two image-level confidence gates from observable evidence."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(FEATURE_DIM),
            nn.Linear(FEATURE_DIM, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 48),
            nn.LayerNorm(48),
            nn.SiLU(inplace=True),
            nn.Linear(48, 2),
        )
        nn.init.normal_(self.network[-1].weight, mean=0.0, std=1.0e-3)
        # Epoch zero is close to D71: 12% D57 BaseColor rollback and 88%
        # Height/Normal-derived AO.  Both remain trainable with healthy slopes.
        with torch.no_grad():
            self.network[-1].bias.copy_(torch.tensor([-2.0, 2.0]))

    @staticmethod
    def features(
        image_srgb: torch.Tensor,
        result: dict[str, torch.Tensor],
    ) -> torch.Tensor:
        image_linear = legacy.srgb_to_linear(image_srgb.float().clamp(0.0, 1.0))
        candidate_base = result["basecolor_linear"].float()
        anchor_base = result["parent_basecolor_linear"].float()
        masks = torch.cat(
            [
                result["specular_mask"].float(),
                result["color_edge"].float(),
                result["geometry_edge"].float(),
                result["effective_gate"].float(),
            ],
            dim=1,
        )
        maps = result["maps"].float()
        parent_maps = result["parent_maps"].float()
        normal = maps[:, 5:8] * 2.0 - 1.0
        normal_xy = normal[:, :2].square().sum(dim=1, keepdim=True).sqrt()
        physical = torch.cat(
            [
                maps[:, 3:4],
                maps[:, 4:5],
                normal_xy,
                maps[:, 8:9],
                maps[:, 9:10],
                parent_maps[:, 9:10],
                (maps[:, 9:10] - parent_maps[:, 9:10]).abs(),
            ],
            dim=1,
        )
        features = torch.cat(
            [
                _statistics(image_linear),
                _statistics(candidate_base),
                _statistics(anchor_base),
                _statistics((candidate_base - anchor_base).abs()),
                _statistics(result["illumination"].float()),
                _statistics(masks),
                _statistics(physical),
            ],
            dim=1,
        )
        if features.shape[1] != FEATURE_DIM:
            raise RuntimeError(
                f"D72 safety feature drift: {features.shape[1]} != {FEATURE_DIM}"
            )
        return features

    def forward(
        self,
        image_srgb: torch.Tensor,
        result: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        logits = self.network(self.features(image_srgb, result))
        gates = torch.sigmoid(logits)[:, :, None, None]
        return {
            "basecolor_anchor_gate": gates[:, :1],
            "derived_ao_gate": gates[:, 1:2],
            "safety_logits": logits,
        }


class D72IntrinsicAOSafetyNet(nn.Module):
    def __init__(self, parent: D70JointRecoveryNet) -> None:
        super().__init__()
        self.parent = parent
        self.safety = IntrinsicAOSafetyCalibration()
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
        with torch.no_grad():
            result = self.parent(image_srgb, condition, attributes, valid_mask)
        calibration = self.safety(image_srgb, result)
        base_gate = calibration["basecolor_anchor_gate"]
        ao_gate = calibration["derived_ao_gate"]
        candidate_base = result["basecolor_linear"].float()
        anchor_base = result["parent_basecolor_linear"].float()
        base_linear = candidate_base * (1.0 - base_gate) + anchor_base * base_gate
        base_srgb = legacy.linear_to_srgb(base_linear).clamp(0.0, 1.0)
        candidate_maps = result["maps"].float()
        anchor_ao = result["parent_maps"][:, 9:10].float()
        ao = (anchor_ao * (1.0 - ao_gate) + candidate_maps[:, 9:10] * ao_gate).clamp(
            0.0, 1.0
        )
        maps = torch.cat(
            [base_srgb, candidate_maps[:, 3:9], ao], dim=1
        )
        return result | calibration | {
            "maps": maps,
            "parent_maps": candidate_maps,
            "basecolor_linear": base_linear,
            "ao": ao,
        }


class SKPBRD72Net(D72IntrinsicAOSafetyNet):
    """Public D72 model with the historical deterministic text-only branch."""

    def __init__(self) -> None:
        base = AlbedoDisentangledMultimodalPBRNet()
        intrinsic = D57IntrinsicRecoveryNet(base)
        super().__init__(D70JointRecoveryNet(intrinsic))

    def forward(
        self,
        image: torch.Tensor,
        presence: torch.Tensor,
        condition: torch.Tensor,
        seed_field: torch.Tensor,
        rich_seed: torch.Tensor,
        attributes: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        if attributes is None:
            attributes = condition.new_zeros((condition.shape[0], ATTRIBUTE_DIM))
        if bool(torch.all(presence <= 0.5)):
            return self.parent.parent.parent(
                image,
                presence,
                condition,
                seed_field,
                rich_seed,
                attributes,
            )
        return super().forward(image, condition, attributes, presence)


def model_manifest(model: D72IntrinsicAOSafetyNet) -> dict[str, object]:
    total = sum(parameter.numel() for parameter in model.parameters())
    parent = sum(parameter.numel() for parameter in model.parent.parameters())
    safety = sum(parameter.numel() for parameter in model.safety.parameters())
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    return {
        "architecture": "D72IntrinsicAOSafetyNet",
        "parameters": total,
        "total_parameters": total,
        "d71_parent_parameters": parent,
        "safety_parameters": safety,
        "trainable_parameters": trainable,
        "spatial_texture_source": "frozen D71 only",
        "basecolor_policy": "confidence blend of D69 de-lit result and D57 anchor",
        "ao_policy": "confidence blend of Height/Normal-derived AO and D57 AO",
        "roughness_metallic_normal_height_bitwise_unchanged": True,
        "prompt_used_by_safety_gate": False,
        "text_only_policy": "frozen deterministic D57 prompt-and-seed branch",
        "training_resolution": 512,
    }
