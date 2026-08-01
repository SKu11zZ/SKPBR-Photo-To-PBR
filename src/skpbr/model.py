"""Dual-resolution BaseColor calibrator used by SKPBR v0.1."""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F

from .prompt import CONDITION_DIM


PARENT_CHANNELS = 11


class ConvNormAct(nn.Sequential):
    def __init__(
        self,
        input_channels: int,
        output_channels: int,
        *,
        kernel_size: int = 3,
        stride: int = 1,
    ) -> None:
        padding = kernel_size // 2
        groups = min(8, output_channels)
        while output_channels % groups:
            groups -= 1
        super().__init__(
            nn.Conv2d(
                input_channels,
                output_channels,
                kernel_size,
                stride=stride,
                padding=padding,
            ),
            nn.GroupNorm(groups, output_channels),
            nn.SiLU(inplace=True),
        )


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            ConvNormAct(channels, channels),
            nn.Conv2d(channels, channels, 3, padding=1),
        )
        groups = min(8, channels)
        while channels % groups:
            groups -= 1
        self.norm = nn.GroupNorm(groups, channels)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.silu(self.norm(value + self.layers(value)), inplace=True)


class SKPBRBaseColorCalibrator(nn.Module):
    """Predict bounded global affine color and a smooth UV residual."""

    def __init__(self) -> None:
        super().__init__()
        self.screen_feature_scale = 0.0
        self.screen_encoder = nn.Sequential(
            ConvNormAct(3, 16, kernel_size=5, stride=2),
            ConvNormAct(16, 24, stride=2),
            ResidualBlock(24),
            ConvNormAct(24, 32, stride=2),
            ResidualBlock(32),
            ConvNormAct(32, 48, stride=2),
            ResidualBlock(48),
            nn.AdaptiveAvgPool2d(1),
        )
        self.prompt_encoder = nn.Sequential(
            nn.Linear(CONDITION_DIM, 96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 64),
            nn.SiLU(inplace=True),
        )
        self.global_head = nn.Sequential(
            nn.Linear(48 + 64 + 23, 160),
            nn.SiLU(inplace=True),
            nn.Dropout(0.08),
            nn.Linear(160, 96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 6),
        )
        self.uv_encoder = nn.Sequential(
            ConvNormAct(PARENT_CHANNELS, 16, kernel_size=5, stride=2),
            ResidualBlock(16),
            ConvNormAct(16, 24, stride=2),
            ResidualBlock(24),
            ConvNormAct(24, 40, stride=2),
            ResidualBlock(40),
        )
        self.film = nn.Sequential(
            nn.Linear(48 + 64 + 6, 96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 80),
        )
        self.residual_head = nn.Sequential(
            ResidualBlock(40),
            ConvNormAct(40, 24),
            nn.Conv2d(24, 3, 3, padding=1),
        )
        nn.init.zeros_(self.global_head[-1].weight)
        nn.init.zeros_(self.global_head[-1].bias)
        nn.init.zeros_(self.residual_head[-1].weight)
        nn.init.zeros_(self.residual_head[-1].bias)

    @staticmethod
    def parent_statistics(parent: torch.Tensor) -> torch.Tensor:
        mean = parent.mean(dim=(2, 3))
        std = parent.std(dim=(2, 3), unbiased=False)
        confidence_coverage = (parent[:, -1:] > 0.01).float().mean(dim=(2, 3))
        return torch.cat((mean, std, confidence_coverage), dim=1)

    def forward(
        self,
        screen_rgb_128: torch.Tensor,
        parent_512: torch.Tensor,
        prompt_condition: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        if parent_512.shape[1] != PARENT_CHANNELS:
            raise ValueError(
                f"Expected {PARENT_CHANNELS} parent channels, "
                f"received {parent_512.shape[1]}"
            )
        screen_feature = self.screen_encoder(screen_rgb_128).flatten(1)
        screen_feature = screen_feature * float(self.screen_feature_scale)
        prompt_feature = self.prompt_encoder(prompt_condition)
        statistics = self.parent_statistics(parent_512)
        raw_affine = self.global_head(
            torch.cat((screen_feature, prompt_feature, statistics), dim=1)
        )
        log_gain = torch.tanh(raw_affine[:, :3]) * 0.70
        bias = torch.tanh(raw_affine[:, 3:]) * 0.35
        uv_feature = self.uv_encoder(parent_512)
        film = self.film(
            torch.cat((screen_feature, prompt_feature, raw_affine), dim=1)
        )
        scale, shift = film.chunk(2, dim=1)
        uv_feature = uv_feature * (
            1.0 + torch.tanh(scale)[:, :, None, None] * 0.35
        ) + torch.tanh(shift)[:, :, None, None] * 0.20
        residual_low = torch.tanh(self.residual_head(uv_feature)) * 0.24
        residual = F.interpolate(
            residual_low,
            size=parent_512.shape[-2:],
            mode="bicubic",
            align_corners=False,
        )
        parent_rgb = parent_512[:, :3]
        affine_rgb = (
            parent_rgb * torch.exp(log_gain[:, :, None, None])
            + bias[:, :, None, None]
        )
        output = (affine_rgb + residual).clamp(0.0, 1.0)
        return {
            "basecolor": output,
            "affine_basecolor": affine_rgb.clamp(0.0, 1.0),
            "log_gain": log_gain,
            "bias": bias,
            "residual_low": residual_low,
            "residual": residual,
        }


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
