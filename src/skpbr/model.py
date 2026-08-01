"""Compact dual-mode planar PBR network released with SKPBR v0.2."""

from __future__ import annotations

import math

import torch
from torch import nn
import torch.nn.functional as F

from .prompt import (
    COLOR_NAMES,
    CONDITION_DIM,
    EFFECTS,
    FINISHES,
    MATERIAL_CLASSES,
    PHYSICAL_REGIMES,
)


MAP_CHANNELS = 10


def _groups(channels: int) -> int:
    value = min(8, channels)
    while channels % value:
        value -= 1
    return value


class CircularConv(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, *, stride: int = 1) -> None:
        super().__init__()
        self.conv = nn.Conv2d(
            input_channels,
            output_channels,
            kernel_size=3,
            stride=stride,
            padding=0,
            bias=False,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.conv(F.pad(value, (1, 1, 1, 1), mode="circular"))


class ConditionalResidual(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, condition_channels: int) -> None:
        super().__init__()
        self.norm1 = nn.GroupNorm(_groups(input_channels), input_channels)
        self.conv1 = CircularConv(input_channels, output_channels)
        self.norm2 = nn.GroupNorm(_groups(output_channels), output_channels)
        self.film = nn.Linear(condition_channels, output_channels * 2)
        self.conv2 = CircularConv(output_channels, output_channels)
        self.skip = (
            nn.Identity()
            if input_channels == output_channels
            else nn.Conv2d(input_channels, output_channels, kernel_size=1, bias=False)
        )
        nn.init.zeros_(self.conv2.conv.weight)
        nn.init.zeros_(self.film.weight)
        nn.init.zeros_(self.film.bias)

    def forward(self, value: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        residual = self.conv1(F.silu(self.norm1(value)))
        residual = self.norm2(residual)
        scale, shift = self.film(condition.float()).chunk(2, dim=1)
        residual = residual * (1.0 + 0.20 * torch.tanh(scale)[:, :, None, None])
        residual = residual + shift[:, :, None, None].to(dtype=residual.dtype)
        residual = self.conv2(F.silu(residual))
        return self.skip(value) + residual


class Down(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, condition_channels: int) -> None:
        super().__init__()
        self.down = CircularConv(input_channels, output_channels, stride=2)
        self.block = ConditionalResidual(output_channels, output_channels, condition_channels)

    def forward(self, value: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        return self.block(self.down(value), condition)


class Up(nn.Module):
    def __init__(
        self,
        input_channels: int,
        skip_channels: int,
        output_channels: int,
        condition_channels: int,
    ) -> None:
        super().__init__()
        self.block = ConditionalResidual(
            input_channels + skip_channels, output_channels, condition_channels
        )

    def forward(
        self,
        value: torch.Tensor,
        skip: torch.Tensor,
        condition: torch.Tensor,
    ) -> torch.Tensor:
        value = F.interpolate(value, size=skip.shape[-2:], mode="nearest")
        return self.block(torch.cat([value, skip], dim=1), condition)


def _logit(value: torch.Tensor, margin: float = 0.015) -> torch.Tensor:
    value = value.clamp(margin, 1.0 - margin)
    return torch.log(value) - torch.log1p(-value)


class PlanarDualModePBRNet(nn.Module):
    """Full-resolution image carrier plus a structured Prompt-conditioned U-Net."""

    input_channels = 10
    output_channels = MAP_CHANNELS
    condition_channels = 192

    def __init__(self) -> None:
        super().__init__()
        self.condition = nn.Sequential(
            nn.Linear(CONDITION_DIM, 256),
            nn.LayerNorm(256),
            nn.SiLU(inplace=True),
            nn.Linear(256, self.condition_channels),
            nn.LayerNorm(self.condition_channels),
            nn.SiLU(inplace=True),
        )
        widths = (40, 64, 96, 128, 160)
        self.stem = CircularConv(self.input_channels, widths[0])
        self.at_256 = ConditionalResidual(widths[0], widths[0], self.condition_channels)
        self.at_128 = Down(widths[0], widths[1], self.condition_channels)
        self.at_64 = Down(widths[1], widths[2], self.condition_channels)
        self.at_32 = Down(widths[2], widths[3], self.condition_channels)
        self.at_16 = Down(widths[3], widths[4], self.condition_channels)
        self.bottleneck = ConditionalResidual(widths[4], widths[4], self.condition_channels)
        self.up_32 = Up(widths[4], widths[3], widths[3], self.condition_channels)
        self.up_64 = Up(widths[3], widths[2], widths[2], self.condition_channels)
        self.up_128 = Up(widths[2], widths[1], widths[1], self.condition_channels)
        self.up_256 = Up(widths[1], widths[0], 48, self.condition_channels)
        self.refine = ConditionalResidual(48, 48, self.condition_channels)
        self.head = CircularConv(48, MAP_CHANNELS)
        nn.init.normal_(self.head.conv.weight, mean=0.0, std=0.002)

    @staticmethod
    def prompt_prior(
        image: torch.Tensor,
        presence: torch.Tensor,
        condition: torch.Tensor,
    ) -> torch.Tensor:
        batch, _, height, width = image.shape
        color_offset = len(MATERIAL_CLASSES) + len(PHYSICAL_REGIMES) + len(COLOR_NAMES)
        prompt_rgb = condition[:, color_offset : color_offset + 3].to(dtype=image.dtype)
        confidence_index = color_offset + 3 + len(FINISHES) + len(EFFECTS) + 2
        confidence = condition[:, confidence_index : confidence_index + 1]
        fallback = image.new_full((batch, 3), 0.45)
        prompt_rgb = prompt_rgb * confidence + fallback * (1.0 - confidence)
        prompt_rgb = prompt_rgb[:, :, None, None].expand(-1, -1, height, width)
        carrier = image * presence + prompt_rgb * (1.0 - presence)

        hint_offset = color_offset + 3 + len(FINISHES) + len(EFFECTS)
        roughness = condition[:, hint_offset : hint_offset + 1].to(dtype=image.dtype)
        metallic = condition[:, hint_offset + 1 : hint_offset + 2].to(dtype=image.dtype)
        prior = image.new_empty((batch, MAP_CHANNELS, height, width))
        prior[:, :3] = carrier
        prior[:, 3:4] = roughness[:, :, None, None]
        prior[:, 4:5] = metallic[:, :, None, None]
        prior[:, 5:6] = 0.5
        prior[:, 6:7] = 0.5
        prior[:, 7:8] = 0.985
        prior[:, 8:9] = 0.5
        prior[:, 9:10] = 0.94
        return prior

    def forward(
        self,
        image: torch.Tensor,
        presence: torch.Tensor,
        condition: torch.Tensor,
        seed_field: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        encoded = self.condition(condition.float()).to(dtype=image.dtype)
        at_256 = self.at_256(
            self.stem(torch.cat([image, presence, seed_field], dim=1)), encoded
        )
        at_128 = self.at_128(at_256, encoded)
        at_64 = self.at_64(at_128, encoded)
        at_32 = self.at_32(at_64, encoded)
        at_16 = self.bottleneck(self.at_16(at_32, encoded), encoded)
        value = self.up_32(at_16, at_32, encoded)
        value = self.up_64(value, at_64, encoded)
        value = self.up_128(value, at_128, encoded)
        value = self.up_256(value, at_256, encoded)
        raw = self.head(self.refine(value, encoded))

        prior = self.prompt_prior(image, presence, condition)
        base = torch.sigmoid(_logit(prior[:, :3]) + raw[:, :3] * 1.35)
        roughness = torch.sigmoid(_logit(prior[:, 3:4]) + raw[:, 3:4] * 1.65)
        metallic = torch.sigmoid(_logit(prior[:, 4:5]) + raw[:, 4:5] * 2.0)
        tangent_xy = torch.tanh(raw[:, 5:7]) * 0.72
        tangent_z = F.softplus(raw[:, 7:8] + 1.8) + 0.08
        normal = F.normalize(torch.cat([tangent_xy, tangent_z], dim=1), dim=1, eps=1.0e-6)
        maps = torch.cat(
            [
                base,
                roughness,
                metallic,
                normal * 0.5 + 0.5,
                torch.sigmoid(raw[:, 8:9] * 1.7),
                torch.sigmoid(_logit(prior[:, 9:10]) + raw[:, 9:10] * 1.7),
            ],
            dim=1,
        )
        return {"maps": maps, "raw": raw, "prior": prior}


def rich_periodic_seed_field(
    seeds: torch.Tensor,
    height: int,
    width: int,
    *,
    channels: int = 12,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Deterministic multi-harmonic periodic fields used by text-only mode."""
    seeds_i = seeds.to(dtype=torch.long).reshape(-1)
    yy = torch.arange(height, device=seeds.device, dtype=torch.float32) / max(height, 1)
    xx = torch.arange(width, device=seeds.device, dtype=torch.float32) / max(width, 1)
    grid_y, grid_x = torch.meshgrid(yy, xx, indexing="ij")
    fields = []
    for channel in range(channels):
        code0 = seeds_i + 130_363 * (channel + 1)
        field = torch.zeros((len(seeds_i), height, width), device=seeds.device)
        for octave, weight in enumerate((0.52, 0.27, 0.14, 0.07)):
            code = code0 + octave * 1_000_003
            limit = (2, 5, 11, 23)[octave]
            fx = (code.remainder(limit) + 1).float()[:, None, None]
            fy = ((code // 19).remainder(limit) + 1).float()[:, None, None]
            sx = torch.where(((code // 37) & 1)[:, None, None] == 0, 1.0, -1.0)
            phase = ((code // 53).remainder(4093)).float()[:, None, None]
            phase = phase / 4093.0 * (2.0 * math.pi)
            directional = torch.sin(2.0 * math.pi * (fx * grid_x + sx * fy * grid_y) + phase)
            cellular = torch.sin(2.0 * math.pi * fx * grid_x + phase * 1.31)
            cellular *= torch.cos(2.0 * math.pi * fy * grid_y - phase * 0.83)
            field += weight * (directional * 0.58 + cellular * 0.42)
        if channel % 3 == 1:
            field = torch.sign(field) * field.abs().sqrt()
        elif channel % 3 == 2:
            field = torch.sin(field * 2.35)
        field -= field.mean(dim=(-2, -1), keepdim=True)
        field /= field.std(dim=(-2, -1), keepdim=True, unbiased=False).clamp_min(0.20)
        fields.append(field.clamp(-2.5, 2.5) / 2.5)
    return torch.stack(fields, dim=1).to(dtype=dtype)


class PromptTextureAdapter(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        condition_channels = 128
        self.condition = nn.Sequential(
            nn.Linear(CONDITION_DIM, 160),
            nn.LayerNorm(160),
            nn.SiLU(inplace=True),
            nn.Linear(160, condition_channels),
            nn.SiLU(inplace=True),
        )
        self.stem = CircularConv(MAP_CHANNELS + 12, 32)
        self.at_256 = ConditionalResidual(32, 32, condition_channels)
        self.at_128 = Down(32, 48, condition_channels)
        self.at_64 = Down(48, 72, condition_channels)
        self.bottleneck = ConditionalResidual(72, 80, condition_channels)
        self.up_128 = Up(80, 48, 48, condition_channels)
        self.up_256 = Up(48, 32, 40, condition_channels)
        self.refine = ConditionalResidual(40, 40, condition_channels)
        self.head = CircularConv(40, MAP_CHANNELS)
        nn.init.zeros_(self.head.conv.weight)

    def forward(
        self,
        core_maps: torch.Tensor,
        condition: torch.Tensor,
        rich_seed: torch.Tensor,
    ) -> torch.Tensor:
        encoded = self.condition(condition.float()).to(dtype=core_maps.dtype)
        at_256 = self.at_256(self.stem(torch.cat([core_maps, rich_seed], dim=1)), encoded)
        at_128 = self.at_128(at_256, encoded)
        at_64 = self.bottleneck(self.at_64(at_128, encoded), encoded)
        value = self.up_128(at_64, at_128, encoded)
        value = self.up_256(value, at_256, encoded)
        return self.head(self.refine(value, encoded))


class PromptRemediatedPBRNet(nn.Module):
    """Frozen spatial reconstruction core with small Prompt-control adapters."""

    def __init__(self, core_state: dict[str, torch.Tensor] | None = None) -> None:
        super().__init__()
        self.core = PlanarDualModePBRNet()
        if core_state is not None:
            self.core.load_state_dict(core_state, strict=True)
        for parameter in self.core.parameters():
            parameter.requires_grad_(False)
        self.color_calibrator = nn.Sequential(
            nn.Linear(CONDITION_DIM + 7, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, 64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 6),
        )
        nn.init.zeros_(self.color_calibrator[-1].weight)
        nn.init.zeros_(self.color_calibrator[-1].bias)
        self.texture_adapter = PromptTextureAdapter()

    def train(self, mode: bool = True):
        super().train(mode)
        self.core.eval()
        return self

    def forward(
        self,
        image: torch.Tensor,
        presence: torch.Tensor,
        condition: torch.Tensor,
        seed_field: torch.Tensor,
        rich_seed: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        with torch.no_grad():
            core = self.core(image, presence, condition, seed_field)["maps"]
        image_mean = image.float().mean(dim=(-2, -1))
        core_mean = core[:, :3].float().mean(dim=(-2, -1))
        present_scalar = presence.float().mean(dim=(1, 2, 3), keepdim=False)[:, None]
        color_code = self.color_calibrator(
            torch.cat([condition.float(), image_mean, core_mean, present_scalar], dim=1)
        )
        scale, bias = color_code.chunk(2, dim=1)
        calibrated_base = core[:, :3].float()
        calibrated_base *= torch.exp(0.55 * torch.tanh(scale)[:, :, None, None])
        calibrated_base += 0.24 * torch.tanh(bias)[:, :, None, None]
        calibrated_base = calibrated_base.clamp(0.0, 1.0).to(dtype=core.dtype)

        raw = self.texture_adapter(core, condition, rich_seed)
        prompt_gate = 1.0 - presence[:, :1]
        base = torch.sigmoid(_logit(calibrated_base, 0.012) + raw[:, :3] * 0.82 * prompt_gate)
        roughness = torch.sigmoid(_logit(core[:, 3:4], 0.012) + raw[:, 3:4] * 1.25 * prompt_gate)
        metallic = torch.sigmoid(_logit(core[:, 4:5], 0.012) + raw[:, 4:5] * 1.10 * prompt_gate)
        normal = F.normalize(core[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        tangent_delta = torch.cat(
            [torch.tanh(raw[:, 5:7]) * 0.38, torch.tanh(raw[:, 7:8]) * 0.12], dim=1
        ) * prompt_gate
        normal = F.normalize(normal + tangent_delta.float(), dim=1, eps=1.0e-6)
        height = torch.sigmoid(_logit(core[:, 8:9], 0.012) + raw[:, 8:9] * 1.35 * prompt_gate)
        ao = torch.sigmoid(_logit(core[:, 9:10], 0.012) + raw[:, 9:10] * prompt_gate)
        maps = torch.cat([base, roughness, metallic, normal * 0.5 + 0.5, height, ao], dim=1)
        return {"maps": maps, "core_maps": core, "texture_raw": raw, "color_code": color_code}


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def parameter_manifest(model: PromptRemediatedPBRNet) -> dict[str, object]:
    total = parameter_count(model)
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {
        "architecture": "PromptRemediatedPBRNet",
        "total_parameters": total,
        "frozen_core_parameters": total - trainable,
        "trainable_adapter_parameters": trainable,
        "image_spatial_core_frozen": True,
        "prompt_seed_channels": 12,
    }
