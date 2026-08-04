"""Photometric BaseColor recovery and color/geometry separation heads."""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F

from .model import StructuredReliefSpatialPBRNet, _logit, parameter_count
from .prompt import ATTRIBUTE_DIM, CONDITION_DIM


def _group_count(channels: int) -> int:
    for groups in (8, 4, 2, 1):
        if channels % groups == 0:
            return groups
    return 1


def _lowpass(value: torch.Tensor, size: int = 32) -> torch.Tensor:
    height, width = value.shape[-2:]
    pooled = F.adaptive_avg_pool2d(value.float(), (min(size, height), min(size, width)))
    return F.interpolate(pooled, (height, width), mode="bilinear", align_corners=False)


def _gradient_magnitude(value: torch.Tensor) -> torch.Tensor:
    value = value.float()
    dx = torch.roll(value, -1, dims=-1) - value
    dy = torch.roll(value, -1, dims=-2) - value
    return (dx.square() + dy.square() + 1.0e-8).sqrt()


class ExpandedCircularResidual(nn.Module):
    """Memory-light full-resolution residual block with circular boundaries."""

    def __init__(self, channels: int, expansion: int = 2) -> None:
        super().__init__()
        hidden = channels * expansion
        self.depthwise = nn.Conv2d(
            channels,
            channels,
            3,
            padding=1,
            padding_mode="circular",
            groups=channels,
        )
        self.norm = nn.GroupNorm(_group_count(channels), channels)
        self.expand = nn.Conv2d(channels, hidden, 1)
        self.project = nn.Conv2d(hidden, channels, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = F.silu(self.norm(self.depthwise(value)), inplace=True)
        residual = self.project(F.silu(self.expand(residual), inplace=True))
        return value + residual


class PhotometricBaseColorRefiner(nn.Module):
    """Recover reflectance color while rejecting illumination and white balance."""

    WIDTH = 40
    CONTEXT = 32

    def __init__(self) -> None:
        super().__init__()
        prompt_dim = CONDITION_DIM + ATTRIBUTE_DIM
        self.context = nn.Sequential(
            nn.Linear(prompt_dim, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, self.CONTEXT),
            nn.SiLU(inplace=True),
        )
        self.stem = nn.Sequential(
            nn.Conv2d(
                3 + 3 + 3 + self.CONTEXT,
                self.WIDTH,
                3,
                padding=1,
                padding_mode="circular",
            ),
            nn.GroupNorm(_group_count(self.WIDTH), self.WIDTH),
            nn.SiLU(inplace=True),
        )
        self.blocks = nn.Sequential(
            *[ExpandedCircularResidual(self.WIDTH) for _ in range(4)]
        )
        self.local_head = nn.Conv2d(self.WIDTH, 3, 1)
        self.global_head = nn.Sequential(
            nn.Linear(prompt_dim + 6, 96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 3),
        )
        nn.init.zeros_(self.local_head.weight)
        nn.init.zeros_(self.local_head.bias)
        nn.init.zeros_(self.global_head[-1].weight)
        nn.init.zeros_(self.global_head[-1].bias)
        self.register_buffer("enabled", torch.tensor(0.0))

    def forward(
        self,
        image: torch.Tensor,
        maps: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        presence: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch, _, height, width = maps.shape
        if not bool(self.enabled.item() > 0.5) or not bool((presence[:, :1] > 0.5).any()):
            zeros = maps.new_zeros((batch, 3, height, width))
            return maps, zeros, maps.new_zeros((batch, 3))

        prompt = torch.cat([condition.float(), attributes.float()], dim=1)
        encoded = self.context(prompt).to(dtype=maps.dtype)
        encoded_map = encoded[:, :, None, None].expand(-1, -1, height, width)
        low_image = _lowpass(image, 32).to(dtype=maps.dtype)
        feature = self.stem(
            torch.cat([image, maps[:, :3], low_image, encoded_map], dim=1)
        )
        local_raw = self.local_head(self.blocks(feature)).float()
        statistics = torch.cat(
            [
                image.float().mean(dim=(-2, -1)),
                maps[:, :3].float().mean(dim=(-2, -1)),
            ],
            dim=1,
        )
        global_raw = self.global_head(torch.cat([prompt, statistics], dim=1))
        residual = (
            torch.tanh(local_raw) * 0.52
            + torch.tanh(global_raw)[:, :, None, None] * 0.78
        )
        gate = presence[:, :1].float() * self.enabled.to(
            device=maps.device, dtype=torch.float32
        )
        base = torch.sigmoid(_logit(maps[:, :3].float()) + residual * gate)
        adjusted = torch.cat([base, maps[:, 3:].float()], dim=1).to(dtype=maps.dtype)
        result = maps * (1.0 - gate.to(dtype=maps.dtype)) + adjusted * gate.to(
            dtype=maps.dtype
        )
        return result, local_raw.to(dtype=maps.dtype), global_raw.to(dtype=maps.dtype)


class ColorGeometryDisentangler(nn.Module):
    """Correct image-side relief while suppressing BaseColor-only edges."""

    WIDTH = 40
    CONTEXT = 32

    def __init__(self) -> None:
        super().__init__()
        prompt_dim = CONDITION_DIM + ATTRIBUTE_DIM
        self.context = nn.Sequential(
            nn.Linear(prompt_dim, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, self.CONTEXT),
            nn.SiLU(inplace=True),
        )
        input_channels = 3 + 3 + 1 + 2 + 1 + 1 + 1 + 1 + self.CONTEXT
        self.stem = nn.Sequential(
            nn.Conv2d(
                input_channels,
                self.WIDTH,
                3,
                padding=1,
                padding_mode="circular",
            ),
            nn.GroupNorm(_group_count(self.WIDTH), self.WIDTH),
            nn.SiLU(inplace=True),
        )
        self.blocks = nn.Sequential(
            *[ExpandedCircularResidual(self.WIDTH) for _ in range(4)]
        )
        self.head = nn.Conv2d(self.WIDTH, 4, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.register_buffer("enabled", torch.tensor(0.0))

    @staticmethod
    def _evidence(
        image: torch.Tensor, base: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        weights = image.new_tensor([0.2126, 0.7152, 0.0722])[None, :, None, None]
        image_luma = (image.float() * weights).sum(dim=1, keepdim=True).clamp_min(1.0e-3)
        base_luma = (base.float() * weights).sum(dim=1, keepdim=True).clamp_min(1.0e-3)
        ratio = torch.log(image_luma) - torch.log(base_luma)
        ratio_low = _lowpass(ratio, 32)
        base_edge = _gradient_magnitude(base_luma)
        ratio_edge = _gradient_magnitude(ratio - ratio_low)
        color_only = torch.sigmoid((base_edge - 0.022) * 72.0) * torch.sigmoid(
            (0.020 - ratio_edge) * 82.0
        )
        return ratio, color_only

    def forward(
        self,
        image: torch.Tensor,
        maps: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        presence: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch, _, height, width = maps.shape
        if not bool(self.enabled.item() > 0.5) or not bool((presence[:, :1] > 0.5).any()):
            return (
                maps,
                maps.new_zeros((batch, 4, height, width)),
                maps.new_zeros((batch, 1, height, width)),
            )

        normal = F.normalize(maps[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        ratio, color_only = self._evidence(image, maps[:, :3])
        prompt = torch.cat([condition.float(), attributes.float()], dim=1)
        encoded = self.context(prompt).to(dtype=maps.dtype)
        encoded_map = encoded[:, :, None, None].expand(-1, -1, height, width)
        feature = torch.cat(
            [
                image,
                maps[:, :3],
                maps[:, 3:4],
                normal[:, :2].to(dtype=maps.dtype),
                maps[:, 8:9],
                ratio.to(dtype=maps.dtype),
                _lowpass(ratio, 32).to(dtype=maps.dtype),
                color_only.to(dtype=maps.dtype),
                encoded_map,
            ],
            dim=1,
        )
        raw = self.head(self.blocks(self.stem(feature))).float()
        gate = presence[:, :1].float() * self.enabled.to(
            device=maps.device, dtype=torch.float32
        )

        attenuation = (1.0 - color_only * torch.tanh(raw[:, 3:4]) * 0.34).clamp(
            0.62, 1.14
        )
        tangent = normal[:, :2] * attenuation + torch.tanh(raw[:, :2]) * 0.10
        corrected_normal = F.normalize(
            torch.cat([tangent, normal[:, 2:3].clamp_min(0.04)], dim=1),
            dim=1,
            eps=1.0e-6,
        )

        height_map = maps[:, 8:9].float()
        height_low = F.avg_pool2d(
            F.pad(height_map, (3, 3, 3, 3), mode="circular"), 7, stride=1
        )
        separated_height = height_low + (height_map - height_low) * attenuation
        corrected_height = torch.sigmoid(
            _logit(separated_height.clamp(1.0e-4, 1.0 - 1.0e-4))
            + raw[:, 2:3] * 0.28
        )
        adjusted = torch.cat(
            [
                maps[:, :5].float(),
                corrected_normal * 0.5 + 0.5,
                corrected_height,
                maps[:, 9:10].float(),
            ],
            dim=1,
        )
        result = maps.float() * (1.0 - gate) + adjusted * gate
        return result, raw, color_only


class AlbedoDisentangledMultimodalPBRNet(StructuredReliefSpatialPBRNet):
    """D54 architecture with the fixed-data D57 weights released in v0.5."""

    def __init__(self) -> None:
        super().__init__()
        self.basecolor_refiner = PhotometricBaseColorRefiner()
        self.geometry_disentangler = ColorGeometryDisentangler()

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
        result = super().forward(
            image, presence, condition, seed_field, rich_seed, attributes
        )
        result["maps_before_basecolor_refinement"] = result["maps"]
        maps, local_raw, global_raw = self.basecolor_refiner(
            image, result["maps"], condition, attributes, presence
        )
        result["maps_before_geometry_disentanglement"] = maps
        maps, geometry_raw, color_only_hint = self.geometry_disentangler(
            image, maps, condition, attributes, presence
        )
        result["maps"] = maps
        result["basecolor_local_raw"] = local_raw
        result["basecolor_global_raw"] = global_raw
        result["geometry_raw"] = geometry_raw
        result["color_only_hint"] = color_only_hint
        return result


def parameter_manifest(
    model: AlbedoDisentangledMultimodalPBRNet,
) -> dict[str, object]:
    total = parameter_count(model)
    core = parameter_count(model.core)
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    return {
        "architecture": "AlbedoDisentangledMultimodalPBRNet",
        "total_parameters": total,
        "frozen_core_parameters": core,
        "adapter_parameters": total - core,
        "currently_trainable_parameters": trainable,
        "image_spatial_core_frozen": True,
        "structured_prompt_attributes": ATTRIBUTE_DIM,
        "basecolor_refiner_enabled": bool(model.basecolor_refiner.enabled.item() > 0.5),
        "geometry_disentangler_enabled": bool(
            model.geometry_disentangler.enabled.item() > 0.5
        ),
        "prompt_seed_basis": "12-channel deterministic isotropic multiscale filtered noise",
        "training_resolution": 512,
    }
