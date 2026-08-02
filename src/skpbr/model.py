"""Structured dual-mode planar PBR network released with SKPBR v0.3."""

from __future__ import annotations

import math

import torch
from torch import nn
import torch.nn.functional as F

from .prompt import (
    ATTRIBUTE_DIM,
    COLOR_NAMES,
    CONDITION_DIM,
    EFFECTS,
    FINISHES,
    MATERIAL_CLASSES,
    PHYSICAL_REGIMES,
    RELIEF_HINT_INDEX,
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
        calibrated_base = calibrated_base * torch.exp(
            0.55 * torch.tanh(scale)[:, :, None, None]
        )
        calibrated_base = calibrated_base + 0.24 * torch.tanh(bias)[:, :, None, None]
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


def _circular_blur(value: torch.Tensor, kernel: int) -> torch.Tensor:
    padding = kernel // 2
    return F.avg_pool2d(
        F.pad(value, (padding, padding, padding, padding), mode="circular"),
        kernel_size=kernel,
        stride=1,
    )


def deterministic_relief_prior(condition: torch.Tensor) -> torch.Tensor:
    """Bounded material/finish/effect relief prior in [0, 1]."""
    class_values = condition.new_tensor(
        [0.24, 0.68, 0.18, 0.20, 0.18, 0.16, 0.62, 0.66, 0.68, 0.16, 0.34, 0.58, 0.42, 0.38, 0.88]
    )
    class_end = len(MATERIAL_CLASSES)
    value = (condition[:, :class_end] * class_values[None]).sum(dim=1)
    finish_start = len(MATERIAL_CLASSES) + len(PHYSICAL_REGIMES) + len(COLOR_NAMES) + 3
    finish_end = finish_start + len(FINISHES)
    finish_values = condition.new_tensor([-0.20, -0.14, -0.05, 0.02, 0.22, -0.18])
    value += (condition[:, finish_start:finish_end] * finish_values[None]).sum(dim=1)
    effect_start = finish_end
    effect_end = effect_start + len(EFFECTS)
    effect_values = condition.new_tensor(
        [0.08, 0.16, 0.23, 0.12, 0.02, 0.06, 0.24, 0.24, 0.22, -0.16, 0.03, 0.08, 0.10, -0.10, 0.14, 0.05]
    )
    value += (condition[:, effect_start:effect_end] * effect_values[None]).sum(dim=1)
    return value.clamp(0.05, 0.98)


class ReliefController(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(CONDITION_DIM, 64),
            nn.LayerNorm(64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 3),
        )
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(self, condition: torch.Tensor) -> torch.Tensor:
        prior = deterministic_relief_prior(condition.float())
        residual = torch.tanh(self.network(condition.float()))
        normal = (prior + residual[:, 0] * 0.24).clamp(0.04, 1.15)
        height_low = (prior + residual[:, 1] * 0.28).clamp(0.04, 1.18)
        height_high = (prior.pow(1.30) + residual[:, 2] * 0.22).clamp(0.025, 1.08)
        return torch.stack([normal, height_low, height_high], dim=1)


class ImageEvidenceAdapter(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        condition_channels = 96
        self.condition = nn.Sequential(
            nn.Linear(CONDITION_DIM, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, condition_channels),
            nn.SiLU(inplace=True),
        )
        self.stem = CircularConv(3 + MAP_CHANNELS, 24)
        self.at_full = ConditionalResidual(24, 24, condition_channels)
        self.at_half = Down(24, 32, condition_channels)
        self.at_quarter = Down(32, 48, condition_channels)
        self.bottleneck = ConditionalResidual(48, 48, condition_channels)
        self.up_half = Up(48, 32, 32, condition_channels)
        self.up_full = Up(32, 24, 32, condition_channels)
        self.refine = ConditionalResidual(32, 32, condition_channels)
        self.head = CircularConv(32, MAP_CHANNELS)
        nn.init.zeros_(self.head.conv.weight)

    def forward(
        self,
        image: torch.Tensor,
        maps: torch.Tensor,
        condition: torch.Tensor,
    ) -> torch.Tensor:
        encoded = self.condition(condition.float()).to(dtype=maps.dtype)
        full = self.at_full(self.stem(torch.cat([image, maps], dim=1)), encoded)
        half = self.at_half(full, encoded)
        quarter = self.bottleneck(self.at_quarter(half, encoded), encoded)
        value = self.up_half(quarter, half, encoded)
        value = self.up_full(value, full, encoded)
        return self.head(self.refine(value, encoded))


class ControlledDualModePBRNet(nn.Module):
    """Bounded text relief and image-evidence adapters around the frozen core."""

    def __init__(self) -> None:
        super().__init__()
        parent = PromptRemediatedPBRNet()
        self.core = parent.core
        self.color_calibrator = parent.color_calibrator
        self.texture_adapter = parent.texture_adapter
        self.relief_controller = ReliefController()
        self.image_adapter = ImageEvidenceAdapter()
        for parameter in self.core.parameters():
            parameter.requires_grad_(False)

    @staticmethod
    def _apply_relief_control(
        maps: torch.Tensor,
        gates: torch.Tensor,
        prompt_gate: torch.Tensor,
    ) -> torch.Tensor:
        normal = F.normalize(maps[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        controlled_normal = torch.cat(
            [normal[:, :2] * gates[:, 0:1, None, None], normal[:, 2:3].clamp_min(0.05)],
            dim=1,
        )
        controlled_normal = F.normalize(controlled_normal, dim=1, eps=1.0e-6)
        normal = F.normalize(
            normal * (1.0 - prompt_gate) + controlled_normal * prompt_gate,
            dim=1,
            eps=1.0e-6,
        )
        height = maps[:, 8:9].float()
        mean = height.mean(dim=(-2, -1), keepdim=True)
        low = _circular_blur(height, 7)
        controlled_height = (
            mean
            + (low - mean) * gates[:, 1:2, None, None]
            + (height - low) * gates[:, 2:3, None, None]
        ).clamp(0.0, 1.0)
        height = height * (1.0 - prompt_gate) + controlled_height * prompt_gate
        return torch.cat(
            [maps[:, :5], normal.to(dtype=maps.dtype) * 0.5 + 0.5, height.to(dtype=maps.dtype), maps[:, 9:10]],
            dim=1,
        )

    @staticmethod
    def _apply_image_residual(
        maps: torch.Tensor,
        raw: torch.Tensor,
        image_gate: torch.Tensor,
    ) -> torch.Tensor:
        base = torch.sigmoid(_logit(maps[:, :3].float(), 0.012) + raw[:, :3].float() * 0.58)
        roughness = torch.sigmoid(_logit(maps[:, 3:4].float(), 0.012) + raw[:, 3:4].float() * 0.72)
        metallic = torch.sigmoid(_logit(maps[:, 4:5].float(), 0.012) + raw[:, 4:5].float() * 0.50)
        normal = F.normalize(maps[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        tangent = torch.cat(
            [torch.tanh(raw[:, 5:7].float()) * 0.20, torch.tanh(raw[:, 7:8].float()) * 0.06],
            dim=1,
        )
        normal = F.normalize(normal + tangent, dim=1, eps=1.0e-6)
        height = torch.sigmoid(_logit(maps[:, 8:9].float(), 0.012) + raw[:, 8:9].float() * 0.58)
        ao = torch.sigmoid(_logit(maps[:, 9:10].float(), 0.012) + raw[:, 9:10].float() * 0.42)
        adjusted = torch.cat(
            [base, roughness, metallic, normal * 0.5 + 0.5, height, ao], dim=1
        ).to(dtype=maps.dtype)
        return maps * (1.0 - image_gate) + adjusted * image_gate

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
        calibrated_base = calibrated_base * torch.exp(
            0.55 * torch.tanh(scale)[:, :, None, None]
        )
        calibrated_base = calibrated_base + 0.24 * torch.tanh(bias)[:, :, None, None]
        calibrated_base = calibrated_base.clamp(0.0, 1.0).to(dtype=core.dtype)
        texture_raw = self.texture_adapter(core, condition, rich_seed)
        prompt_gate = 1.0 - presence[:, :1]
        base = torch.sigmoid(_logit(calibrated_base.float(), 0.012) + texture_raw[:, :3].float() * 0.82 * prompt_gate)
        roughness = torch.sigmoid(_logit(core[:, 3:4].float(), 0.012) + texture_raw[:, 3:4].float() * 1.25 * prompt_gate)
        metallic = torch.sigmoid(_logit(core[:, 4:5].float(), 0.012) + texture_raw[:, 4:5].float() * 1.10 * prompt_gate)
        normal = F.normalize(core[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        tangent_delta = torch.cat(
            [torch.tanh(texture_raw[:, 5:7].float()) * 0.38, torch.tanh(texture_raw[:, 7:8].float()) * 0.12],
            dim=1,
        ) * prompt_gate
        normal = F.normalize(normal + tangent_delta, dim=1, eps=1.0e-6)
        height = torch.sigmoid(_logit(core[:, 8:9].float(), 0.012) + texture_raw[:, 8:9].float() * 1.35 * prompt_gate)
        ao = torch.sigmoid(_logit(core[:, 9:10].float(), 0.012) + texture_raw[:, 9:10].float() * prompt_gate)
        legacy_maps = torch.cat(
            [base, roughness, metallic, normal * 0.5 + 0.5, height, ao], dim=1
        ).to(dtype=core.dtype)
        relief_gates = self.relief_controller(condition)
        controlled = self._apply_relief_control(legacy_maps, relief_gates, prompt_gate)
        if bool((presence[:, :1] > 0.5).any()):
            image_raw = self.image_adapter(image, controlled, condition)
        else:
            image_raw = controlled.new_zeros(controlled.shape)
        maps = self._apply_image_residual(controlled, image_raw, presence[:, :1])
        return {
            "maps": maps,
            "core_maps": core,
            "legacy_maps": legacy_maps,
            "texture_raw": texture_raw,
            "image_raw": image_raw,
            "color_code": color_code,
            "relief_gates": relief_gates,
        }


@torch.no_grad()
def isotropic_multiscale_seed_field(
    seeds: torch.Tensor,
    height: int,
    width: int,
    *,
    channels: int = 12,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Deterministic tileable filtered noise without a privileged direction."""
    if height < 8 or width < 8:
        raise ValueError("seed field requires at least 8x8 pixels")
    device = seeds.device
    interior_h, interior_w = height - 1, width - 1
    samples = []
    for sample_seed in seeds.to(dtype=torch.long).reshape(-1):
        generator = torch.Generator(device=device)
        generator.manual_seed(int(sample_seed.item()) & 0x7FFF_FFFF_FFFF_FFFF)
        samples.append(
            torch.randn(
                channels,
                interior_h,
                interior_w,
                generator=generator,
                device=device,
                dtype=torch.float32,
            )
        )
    white = torch.stack(samples, dim=0)
    levels = (
        _circular_blur(white[:, 0:3], 3),
        _circular_blur(white[:, 3:6], 7),
        _circular_blur(white[:, 6:9], 15),
        _circular_blur(white[:, 9:12], 31),
    )
    field = torch.cat(levels, dim=1)
    field[:, 1::3] = torch.sign(field[:, 1::3]) * field[:, 1::3].abs().sqrt()
    field[:, 2::3] = torch.cos(field[:, 2::3] * 2.15) - 0.25
    field -= field.mean(dim=(-2, -1), keepdim=True)
    field /= field.std(dim=(-2, -1), keepdim=True, unbiased=False).clamp_min(1.0e-4)
    field = field.clamp(-3.0, 3.0) / 3.0
    field = torch.cat([field, field[..., :1]], dim=-1)
    field = torch.cat([field, field[..., :1, :]], dim=-2)
    return field.to(dtype=dtype)


class EnvelopeReliefController(ReliefController):
    def __init__(self) -> None:
        super().__init__()
        self.register_buffer("envelope_strength", torch.tensor(0.0))

    def forward(self, condition: torch.Tensor) -> torch.Tensor:
        legacy = super().forward(condition)
        prior = deterministic_relief_prior(condition.float())
        maximum = torch.stack(
            [0.050 + prior * 0.96, 0.060 + prior * 1.02, 0.035 + prior.pow(1.10) * 0.88],
            dim=1,
        )
        minimum = torch.stack(
            [0.025 + prior * 0.10, 0.025 + prior * 0.08, 0.018 + prior * 0.06],
            dim=1,
        )
        bounded = torch.minimum(torch.maximum(legacy, minimum), maximum)
        strength = self.envelope_strength.to(device=legacy.device, dtype=legacy.dtype)
        return legacy * (1.0 - strength) + bounded * strength


class SurfacePropertyCalibrator(nn.Module):
    EXTRA_DIM = 13

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(CONDITION_DIM + self.EXTRA_DIM, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, 64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 4),
        )
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(
        self,
        image: torch.Tensor,
        maps: torch.Tensor,
        core_maps: torch.Tensor,
        condition: torch.Tensor,
        presence: torch.Tensor,
    ) -> torch.Tensor:
        image_f, maps_f, core_f = image.float(), maps.float(), core_maps.float()
        image_mean = image_f.mean(dim=(-2, -1))
        image_std = image_f.std(dim=(-2, -1), unbiased=False)
        luma = image_f.mean(dim=1, keepdim=True)
        dx = torch.roll(luma, -1, dims=-1) - luma
        dy = torch.roll(luma, -1, dims=-2) - luma
        image_gradient = torch.cat(
            [dx.abs().mean(dim=(-2, -1)), dy.abs().mean(dim=(-2, -1))], dim=1
        )
        core_normal = core_f[:, 5:7] * 2.0 - 1.0
        core_summary = torch.stack(
            [
                core_f[:, 3].mean(dim=(-2, -1)),
                core_f[:, 4].mean(dim=(-2, -1)),
                core_normal.square().sum(dim=1).mean(dim=(-2, -1)).sqrt(),
                core_f[:, 8].std(dim=(-2, -1), unbiased=False),
            ],
            dim=1,
        )
        present = presence.float().mean(dim=(1, 2, 3), keepdim=False)[:, None]
        code = self.network(
            torch.cat([condition.float(), image_mean, image_std, image_gradient, core_summary, present], dim=1)
        )
        rough_bias, metal_bias, normal_scale, height_scale = code.unbind(dim=1)
        roughness = torch.sigmoid(_logit(maps_f[:, 3:4], 0.012) + torch.tanh(rough_bias)[:, None, None, None] * 0.90)
        metallic = torch.sigmoid(_logit(maps_f[:, 4:5], 0.012) + torch.tanh(metal_bias)[:, None, None, None] * 0.55)
        normal = F.normalize(maps_f[:, 5:8] * 2.0 - 1.0, dim=1, eps=1.0e-6)
        normal_xy_gain = torch.exp(torch.tanh(normal_scale) * 0.70)[:, None, None, None]
        normal = F.normalize(
            torch.cat([normal[:, :2] * normal_xy_gain, normal[:, 2:3]], dim=1),
            dim=1,
            eps=1.0e-6,
        )
        height = maps_f[:, 8:9]
        height_mean = height.mean(dim=(-2, -1), keepdim=True)
        height_gain = torch.exp(torch.tanh(height_scale) * 0.75)[:, None, None, None]
        height = (height_mean + (height - height_mean) * height_gain).clamp(0.0, 1.0)
        adjusted = torch.cat(
            [maps_f[:, :3], roughness, metallic, normal * 0.5 + 0.5, height, maps_f[:, 9:10]],
            dim=1,
        ).to(dtype=maps.dtype)
        gate = presence[:, :1].to(dtype=maps.dtype)
        return maps * (1.0 - gate) + adjusted * gate


class IsotropicEnvelopePBRNet(ControlledDualModePBRNet):
    def __init__(self) -> None:
        super().__init__()
        self.relief_controller = EnvelopeReliefController()
        self.property_calibrator = SurfacePropertyCalibrator()

    def forward(
        self,
        image: torch.Tensor,
        presence: torch.Tensor,
        condition: torch.Tensor,
        seed_field: torch.Tensor,
        rich_seed: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        result = super().forward(image, presence, condition, seed_field, rich_seed)
        result["maps_before_property_calibration"] = result["maps"]
        result["maps"] = self.property_calibrator(
            image, result["maps"], result["core_maps"], condition, presence
        )
        return result


class StructuredPromptCalibrator(nn.Module):
    MAP_STATS_DIM = 8

    def __init__(self) -> None:
        super().__init__()
        input_dim = CONDITION_DIM + ATTRIBUTE_DIM + self.MAP_STATS_DIM + 1
        self.network = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, 64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 5),
        )
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    @staticmethod
    def _stats(maps: torch.Tensor) -> torch.Tensor:
        value = maps.float()
        normal_xy = value[:, 5:7] * 2.0 - 1.0
        height = value[:, 8:9]
        return torch.cat(
            [
                value[:, :3].mean(dim=(-2, -1)),
                value[:, 3:4].mean(dim=(-2, -1)),
                value[:, 4:5].mean(dim=(-2, -1)),
                normal_xy.square().sum(dim=1).mean(dim=(-2, -1)).sqrt()[:, None],
                height.std(dim=(-2, -1), unbiased=False),
                value[:, 9:10].mean(dim=(-2, -1)),
            ],
            dim=1,
        )

    def forward(
        self,
        maps: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        presence: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        present = presence.float().mean(dim=(1, 2, 3))[:, None]
        code = torch.tanh(
            self.network(
                torch.cat([condition.float(), attributes.float(), self._stats(maps), present], dim=1)
            )
        )
        base_weight = 1.0 - present * 0.65
        property_weight = 1.0 - present * 0.25
        base = torch.sigmoid(
            _logit(maps[:, :3].float(), 0.012)
            + code[:, :3, None, None] * 0.72 * base_weight[:, :, None, None]
        )
        roughness = torch.sigmoid(
            _logit(maps[:, 3:4].float(), 0.012)
            + code[:, 3:4, None, None] * 1.05 * property_weight[:, :, None, None]
        )
        metallic = torch.sigmoid(
            _logit(maps[:, 4:5].float(), 0.012)
            + code[:, 4:5, None, None] * 1.32 * property_weight[:, :, None, None]
        )
        result = torch.cat([base, roughness, metallic, maps[:, 5:]], dim=1).to(dtype=maps.dtype)
        return result, code


class ZeroFloorReliefLimiter(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(CONDITION_DIM + ATTRIBUTE_DIM, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 48),
            nn.SiLU(inplace=True),
            nn.Linear(48, 3),
        )
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)
        self.register_buffer("enabled", torch.tensor(0.0))

    def forward(self, condition: torch.Tensor, attributes: torch.Tensor) -> torch.Tensor:
        if not bool(self.enabled.item() > 0.5):
            return condition.new_ones((condition.shape[0], 3), dtype=torch.float32)
        hint = attributes[:, RELIEF_HINT_INDEX : RELIEF_HINT_INDEX + 1].float().clamp(0.0, 1.0)
        base = torch.cat(
            [
                (hint * 1.25).clamp_max(1.0),
                (hint * 1.15).clamp_max(1.0),
                (hint.pow(1.10) * 1.08).clamp_max(1.0),
            ],
            dim=1,
        )
        residual = torch.exp(
            torch.tanh(self.network(torch.cat([condition.float(), attributes.float()], dim=1))) * 0.48
        )
        return (base * residual).clamp(0.0, 1.0)


class DepthwiseResidual(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.depthwise = nn.Conv2d(
            channels, channels, 3, padding=1, padding_mode="circular", groups=channels
        )
        self.norm = nn.GroupNorm(_groups(channels), channels)
        self.expand = nn.Conv2d(channels, channels * 2, 1)
        self.project = nn.Conv2d(channels * 2, channels, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = self.depthwise(value)
        residual = F.silu(self.norm(residual), inplace=True)
        residual = self.project(F.silu(self.expand(residual), inplace=True))
        return value + residual


class SpatialPropertySeparator(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.condition = nn.Sequential(
            nn.Linear(CONDITION_DIM + ATTRIBUTE_DIM, 64),
            nn.LayerNorm(64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 24),
            nn.SiLU(inplace=True),
        )
        self.stem = nn.Sequential(
            nn.Conv2d(3 + MAP_CHANNELS + 24, 32, 3, padding=1, padding_mode="circular"),
            nn.GroupNorm(8, 32),
            nn.SiLU(inplace=True),
        )
        self.blocks = nn.Sequential(DepthwiseResidual(32), DepthwiseResidual(32))
        self.head = nn.Conv2d(32, 8, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.register_buffer("enabled", torch.tensor(0.0))

    def forward(
        self,
        image: torch.Tensor,
        maps: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
        presence: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        batch, _, height, width = maps.shape
        if not bool(self.enabled.item() > 0.5) or not bool((presence[:, :1] > 0.5).any()):
            return maps, maps.new_zeros((batch, 8, height, width))
        encoded = self.condition(torch.cat([condition.float(), attributes.float()], dim=1))
        encoded = encoded.to(dtype=maps.dtype)[:, :, None, None].expand(-1, -1, height, width)
        raw = self.head(self.blocks(self.stem(torch.cat([image, maps, encoded], dim=1))))
        gate = presence[:, :1].float() * self.enabled.to(device=maps.device, dtype=torch.float32)
        base = torch.sigmoid(_logit(maps[:, :3].float(), 0.012) + raw[:, :3].float() * 0.38 * gate)
        roughness = torch.sigmoid(_logit(maps[:, 3:4].float(), 0.012) + raw[:, 3:4].float() * 0.62 * gate)
        metallic = torch.sigmoid(_logit(maps[:, 4:5].float(), 0.012) + raw[:, 4:5].float() * 0.52 * gate)
        normal = F.normalize(maps[:, 5:8].float() * 2.0 - 1.0, dim=1, eps=1.0e-6)
        normal_delta = torch.cat(
            [torch.tanh(raw[:, 5:7].float()) * 0.12, torch.zeros_like(raw[:, 5:6].float())],
            dim=1,
        ) * gate
        normal = F.normalize(normal + normal_delta, dim=1, eps=1.0e-6)
        height_map = torch.sigmoid(_logit(maps[:, 8:9].float(), 0.012) + raw[:, 7:8].float() * 0.46 * gate)
        adjusted = torch.cat(
            [base, roughness, metallic, normal * 0.5 + 0.5, height_map, maps[:, 9:10].float()],
            dim=1,
        ).to(dtype=maps.dtype)
        return maps * (1.0 - gate.to(dtype=maps.dtype)) + adjusted * gate.to(dtype=maps.dtype), raw


class StructuredReliefSpatialPBRNet(IsotropicEnvelopePBRNet):
    """Released v0.3 network with structured Prompt and exact flat relief."""

    def __init__(self) -> None:
        super().__init__()
        self.structured_calibrator = StructuredPromptCalibrator()
        self.relief_limiter = ZeroFloorReliefLimiter()
        self.spatial_separator = SpatialPropertySeparator()

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
        result = super().forward(image, presence, condition, seed_field, rich_seed)
        result["maps_before_structured_calibration"] = result["maps"]
        maps, structured_code = self.structured_calibrator(
            result["maps"], condition, attributes, presence
        )
        prompt_gate = 1.0 - presence[:, :1]
        limiter_gates = self.relief_limiter(condition, attributes)
        maps = self._apply_relief_control(maps, limiter_gates, prompt_gate)
        result["maps_before_spatial_separation"] = maps
        maps, spatial_raw = self.spatial_separator(image, maps, condition, attributes, presence)
        result["maps"] = maps
        result["structured_code"] = structured_code
        result["limiter_gates"] = limiter_gates
        result["spatial_raw"] = spatial_raw
        return result


def parameter_manifest(model: StructuredReliefSpatialPBRNet) -> dict[str, object]:
    total = parameter_count(model)
    core = parameter_count(model.core)
    return {
        "architecture": "StructuredReliefSpatialPBRNet",
        "total_parameters": total,
        "frozen_core_parameters": core,
        "adapter_parameters": total - core,
        "image_spatial_core_frozen": True,
        "structured_prompt_attributes": ATTRIBUTE_DIM,
        "prompt_seed_basis": "12-channel deterministic isotropic multiscale filtered noise",
        "zero_floor_relief_limiter": bool(model.relief_limiter.enabled.item() > 0.5),
        "full_resolution_spatial_separator": bool(model.spatial_separator.enabled.item() > 0.5),
    }
