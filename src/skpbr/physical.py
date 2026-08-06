#!/usr/bin/env python3
"""D70 shared multiscale physical-property decoder on a frozen D69 parent."""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F

from . import runtime as common
from . import runtime as d60
from .prompt import (
    ATTRIBUTE_DIM,
    FINISH_SLICE,
    ROUGHNESS_HINT_INDEX,
)
from .intrinsic import D57IntrinsicRecoveryNet


def _groups(channels: int) -> int:
    for groups in (8, 4, 2, 1):
        if channels % groups == 0:
            return groups
    return 1


class Residual(nn.Module):
    def __init__(self, channels: int, dilation: int = 1) -> None:
        super().__init__()
        self.depthwise = nn.Conv2d(
            channels,
            channels,
            3,
            padding=dilation,
            dilation=dilation,
            padding_mode="reflect",
            groups=channels,
        )
        self.norm = nn.GroupNorm(_groups(channels), channels)
        self.expand = nn.Conv2d(channels, channels * 2, 1)
        self.project = nn.Conv2d(channels * 2, channels, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = F.silu(self.norm(self.depthwise(value)), inplace=True)
        residual = self.project(F.silu(self.expand(residual), inplace=True))
        return value + residual


class Down(nn.Module):
    def __init__(self, source: int, target: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(source, target, 3, stride=2, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(target), target),
            nn.SiLU(inplace=True),
            Residual(target),
            Residual(target),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.block(value)


class Up(nn.Module):
    def __init__(self, source: int, skip: int, target: int) -> None:
        super().__init__()
        self.merge = nn.Sequential(
            nn.Conv2d(source + skip, target, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(target), target),
            nn.SiLU(inplace=True),
            Residual(target),
            Residual(target),
        )

    def forward(self, value: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        value = F.interpolate(value, skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.merge(torch.cat([value, skip], dim=1))


class Head(nn.Module):
    def __init__(self, channels: int, outputs: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(channels, 32, 3, padding=1, padding_mode="reflect"),
            nn.SiLU(inplace=True),
            nn.Conv2d(32, outputs, 1),
        )
        nn.init.zeros_(self.body[-1].weight)
        nn.init.zeros_(self.body[-1].bias)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.body(value).float()


class RoughnessSpatialBranch(nn.Module):
    """Dedicated spatial reasoning after the shared physical representation."""

    def __init__(self, channels: int, outputs: int = 3) -> None:
        super().__init__()
        self.blocks = nn.Sequential(
            Residual(channels, 1),
            Residual(channels, 2),
            Residual(channels, 3),
            Residual(channels, 1),
        )
        self.head = Head(channels, outputs)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.head(self.blocks(value))


class RoughnessEvidenceBranch(nn.Module):
    """Full-resolution path that cannot lose highlight evidence in the shared trunk."""

    INPUTS = 3 + 3 + 3 + 4 + 1 + 2

    def __init__(self) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(self.INPUTS, 32, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(32), 32),
            nn.SiLU(inplace=True),
        )
        self.blocks = nn.Sequential(
            Residual(32, 1),
            Residual(32, 2),
            Residual(32, 4),
            Residual(32, 1),
        )
        self.head = Head(32, 3)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.head(self.blocks(self.stem(value)))


class RoughnessFrequencyBranch(nn.Module):
    """Decode analytic highlight-shape and frequency cues at full resolution."""

    INPUTS = 20

    def __init__(self) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(self.INPUTS, 40, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(40), 40),
            nn.SiLU(inplace=True),
            Residual(40, 1),
            Residual(40, 2),
        )
        self.context = nn.Sequential(
            nn.Conv2d(40, 48, 3, stride=2, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(48), 48),
            nn.SiLU(inplace=True),
            Residual(48, 2),
            Residual(48, 4),
        )
        self.merge = nn.Sequential(
            nn.Conv2d(88, 40, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(40), 40),
            nn.SiLU(inplace=True),
            Residual(40, 1),
            Residual(40, 3),
        )
        self.head = Head(40, 3)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        local = self.stem(value)
        context = self.context(local)
        context = F.interpolate(
            context, local.shape[-2:], mode="bilinear", align_corners=False
        )
        return self.head(self.merge(torch.cat([local, context], dim=1)))


class RoughnessCalibrationBranch(nn.Module):
    """Predict material-level mean and contrast corrections from global evidence."""

    CUE_INPUTS = RoughnessFrequencyBranch.INPUTS
    STABLE_INPUTS = 12

    def __init__(self) -> None:
        super().__init__()
        prompt_dim = common.CONDITION_DIM + ATTRIBUTE_DIM
        statistic_dim = self.CUE_INPUTS * 3
        self.statistic_norm = nn.LayerNorm(statistic_dim)
        self.body = nn.Sequential(
            nn.Linear(statistic_dim + prompt_dim, 160),
            nn.LayerNorm(160),
            nn.SiLU(inplace=True),
            nn.Linear(160, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 3),
        )
        nn.init.zeros_(self.body[-1].weight)
        nn.init.zeros_(self.body[-1].bias)
        # LayerNorm above is useful for comparing cue shapes, but removes the
        # absolute magnitude needed to distinguish a narrow bright highlight
        # from a broad dim one.  Preserve those values through a separate path.
        # Its final layer is zero initialized so all existing D71 checkpoints
        # remain exact numerical warm starts.
        absolute_statistic_dim = self.CUE_INPUTS * 4
        self.absolute_body = nn.Sequential(
            nn.Linear(absolute_statistic_dim + prompt_dim, 160),
            nn.LayerNorm(160),
            nn.SiLU(inplace=True),
            nn.Linear(160, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, 3),
        )
        nn.init.zeros_(self.absolute_body[-1].weight)
        nn.init.zeros_(self.absolute_body[-1].bias)
        stable_statistic_dim = self.STABLE_INPUTS * 4
        self.confidence_body = nn.Sequential(
            nn.Linear(stable_statistic_dim + prompt_dim, 128),
            nn.LayerNorm(128),
            nn.SiLU(inplace=True),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 1),
        )
        nn.init.zeros_(self.confidence_body[-1].weight)
        nn.init.zeros_(self.confidence_body[-1].bias)
        self.class_scale_logits = nn.Parameter(
            torch.zeros(len(common.MATERIAL_CLASSES))
        )
        # Train-split-only robust affine fits from explicit finish words to
        # material Roughness means.  The blend coefficient (0.60) was selected
        # on a domain-balanced train subset; validation targets were audit-only.
        self.register_buffer(
            "prompt_affine_scale",
            torch.tensor(
                [
                    0.8993146043,
                    0.8832931143,
                    0.9674015427,
                    0.8513788060,
                    1.0054969706,
                    0.9795064261,
                    0.8453724182,
                    0.8791379286,
                    0.9387367030,
                    0.8915582895,
                    0.8392554587,
                    0.8786743323,
                    1.0857407147,
                    0.9387470748,
                    0.9044328092,
                ],
                dtype=torch.float32,
            ),
        )
        self.register_buffer(
            "prompt_affine_bias",
            torch.tensor(
                [
                    0.0586433524,
                    0.0979721862,
                    0.0233988389,
                    0.0955271962,
                    0.0534822090,
                    0.0275589785,
                    0.0888911555,
                    0.0725956930,
                    0.0249939490,
                    0.0638529328,
                    0.0867131575,
                    0.0717241580,
                    0.0070636579,
                    0.0364352771,
                    0.0397978087,
                ],
                dtype=torch.float32,
            ),
        )
        self.register_buffer(
            "prompt_blend_alpha", torch.tensor(0.60, dtype=torch.float32)
        )

    def prompt_prior(
        self,
        condition: torch.Tensor,
        attributes: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        classes = condition[:, : len(common.MATERIAL_CLASSES)].float()
        scale = (classes * self.prompt_affine_scale[None, :]).sum(
            dim=1, keepdim=True
        )
        bias = (classes * self.prompt_affine_bias[None, :]).sum(
            dim=1, keepdim=True
        )
        hint = attributes[:, ROUGHNESS_HINT_INDEX : ROUGHNESS_HINT_INDEX + 1].float()
        explicit_finish = attributes[:, FINISH_SLICE].float().sum(
            dim=1, keepdim=True
        ).clamp(0.0, 1.0)
        prior = (scale * hint + bias).clamp(0.04, 0.96)
        return prior[:, :, None, None], explicit_finish[:, :, None, None]

    def forward(
        self,
        cues: torch.Tensor,
        stable_cues: torch.Tensor,
        condition: torch.Tensor,
        attributes: torch.Tensor,
    ) -> torch.Tensor:
        cue = cues.float()
        statistics = torch.cat(
            [
                cue.mean(dim=(2, 3)),
                cue.flatten(2).std(dim=2, unbiased=False),
                cue.flatten(2).amax(dim=2),
            ],
            dim=1,
        )
        statistics = self.statistic_norm(statistics)
        absolute_statistics = torch.cat(
            [
                cue.mean(dim=(2, 3)),
                cue.flatten(2).std(dim=2, unbiased=False),
                cue.flatten(2).amin(dim=2),
                cue.flatten(2).amax(dim=2),
            ],
            dim=1,
        )
        prompt = torch.cat([condition.float(), attributes.float()], dim=1)
        normalized = self.body(torch.cat([statistics, prompt], dim=1))
        absolute = self.absolute_body(
            torch.cat([absolute_statistics, prompt], dim=1)
        )
        stable = stable_cues.float()
        stable_statistics = torch.cat(
            [
                stable.mean(dim=(2, 3)),
                stable.flatten(2).std(dim=2, unbiased=False),
                stable.flatten(2).amin(dim=2),
                stable.flatten(2).amax(dim=2),
            ],
            dim=1,
        )
        confidence = self.confidence_body(
            torch.cat([stable_statistics, prompt], dim=1)
        )
        class_logits = condition[:, : len(common.MATERIAL_CLASSES)].float()
        class_scale_logit = (
            class_logits * self.class_scale_logits[None, :]
        ).sum(dim=1, keepdim=True)
        return torch.cat(
            [normalized + absolute, confidence, class_scale_logit], dim=1
        )[
            :, :, None, None
        ]


class RoughnessMaterialPriorBranch(nn.Module):
    """Recover phase-aligned local Roughness from de-lit material structure."""

    INPUTS = 33

    def __init__(self) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(self.INPUTS, 40, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(40), 40),
            nn.SiLU(inplace=True),
            Residual(40, 1),
            Residual(40, 2),
        )
        self.context = nn.Sequential(
            nn.Conv2d(40, 48, 3, stride=2, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(48), 48),
            nn.SiLU(inplace=True),
            Residual(48, 2),
            Residual(48, 4),
        )
        self.merge = nn.Sequential(
            nn.Conv2d(88, 40, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(40), 40),
            nn.SiLU(inplace=True),
            Residual(40, 1),
            Residual(40, 3),
        )
        self.head = Head(40, 2)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        local = self.stem(value)
        context = self.context(local)
        context = F.interpolate(
            context, local.shape[-2:], mode="bilinear", align_corners=False
        )
        return self.head(self.merge(torch.cat([local, context], dim=1)))


class SharedPhysicalDecoder(nn.Module):
    PROMPT = 16
    FULL = 40
    HALF = 56
    QUARTER = 72

    def __init__(self) -> None:
        super().__init__()
        prompt_dim = common.CONDITION_DIM + ATTRIBUTE_DIM
        self.prompt = nn.Sequential(
            nn.Linear(prompt_dim, 96),
            nn.LayerNorm(96),
            nn.SiLU(inplace=True),
            nn.Linear(96, self.PROMPT),
            nn.SiLU(inplace=True),
        )
        # RGB + intrinsic BaseColor + illumination + four masks + four
        # continuous specular cues + six parent physical channels + Prompt.
        inputs = 3 + 3 + 3 + 4 + 4 + 6 + self.PROMPT
        self.stem = nn.Sequential(
            nn.Conv2d(inputs, self.FULL, 3, padding=1, padding_mode="reflect"),
            nn.GroupNorm(_groups(self.FULL), self.FULL),
            nn.SiLU(inplace=True),
            Residual(self.FULL),
            Residual(self.FULL),
        )
        self.down_half = Down(self.FULL, self.HALF)
        self.down_quarter = Down(self.HALF, self.QUARTER)
        self.bottleneck = nn.Sequential(
            Residual(self.QUARTER, 1),
            Residual(self.QUARTER, 2),
            Residual(self.QUARTER, 3),
            Residual(self.QUARTER, 1),
        )
        self.up_half = Up(self.QUARTER, self.HALF, self.HALF)
        self.up_full = Up(self.HALF, self.FULL, self.FULL)
        self.refine = nn.Sequential(Residual(self.FULL), Residual(self.FULL))
        # Local/global/gate, delta/gate, XYZ/gate, local/global/gate/AO.
        self.roughness = Head(self.FULL, 3)
        # Zero-output at initialization, so older shared checkpoints remain an
        # exact warm start even though the deeper Roughness path is new.
        self.roughness_spatial = RoughnessSpatialBranch(self.FULL)
        self.roughness_evidence = RoughnessEvidenceBranch()
        # D71 branch: zero initialized so every D70 checkpoint remains an exact
        # numerical warm start until this branch is explicitly trained.
        self.roughness_frequency = RoughnessFrequencyBranch()
        self.roughness_calibration = RoughnessCalibrationBranch()
        self.roughness_material_prior = RoughnessMaterialPriorBranch()
        self.metallic = Head(self.FULL, 2)
        self.normal = Head(self.FULL, 4)
        self.normal_detail = RoughnessSpatialBranch(self.FULL, outputs=4)
        self.height = Head(self.FULL, 4)
        self.height_detail = RoughnessSpatialBranch(self.FULL, outputs=4)
        # Train-selected, validation-audited amplitude calibration.  Defaults
        # preserve every historical checkpoint exactly; promoted checkpoints
        # can opt into bounded calibration without retraining any image path.
        self.register_buffer("normal_tangent_scale", torch.tensor(1.0))
        self.register_buffer("height_contrast_scale", torch.tensor(1.0))

    @staticmethod
    def _specular_cues(
        image_srgb: torch.Tensor,
        parent: dict[str, torch.Tensor],
    ) -> list[torch.Tensor]:
        input_linear = common.srgb_to_linear(image_srgb.float())
        diffuse = (
            parent["basecolor_linear"].float() * parent["illumination"].float()
        ).clamp(0.0, 1.0)
        residual = (input_linear - diffuse).clamp(0.0, 1.0)
        luma = (
            residual
            * residual.new_tensor([0.2126, 0.7152, 0.0722])[None, :, None, None]
        ).sum(dim=1, keepdim=True)
        small = F.avg_pool2d(
            F.pad(luma, (4, 4, 4, 4), mode="reflect"), 9, stride=1
        )
        large = F.avg_pool2d(
            F.pad(luma, (15, 15, 15, 15), mode="reflect"), 31, stride=1
        )
        return [luma, small, large, (small - large).abs()]

    @staticmethod
    def _roughness_frequency_cues(
        image_srgb: torch.Tensor,
        parent: dict[str, torch.Tensor],
    ) -> torch.Tensor:
        """Expose highlight width and spatial frequency without learned compression."""
        input_linear = common.srgb_to_linear(image_srgb.float())
        diffuse = (
            parent["basecolor_linear"].float() * parent["illumination"].float()
        ).clamp(0.0, 1.0)
        residual = (input_linear - diffuse).clamp(-1.0, 1.0)
        weights = residual.new_tensor([0.2126, 0.7152, 0.0722])[
            None, :, None, None
        ]
        observed_luma = (input_linear * weights).sum(dim=1, keepdim=True)
        diffuse_luma = (diffuse * weights).sum(dim=1, keepdim=True)
        residual_luma = (residual * weights).sum(dim=1, keepdim=True)
        positive = residual_luma.clamp_min(0.0)

        def average(value: torch.Tensor, kernel: int) -> torch.Tensor:
            pad = kernel // 2
            return F.avg_pool2d(
                F.pad(value, (pad, pad, pad, pad), mode="reflect"),
                kernel,
                stride=1,
            )

        blur3 = average(positive, 3)
        blur7 = average(positive, 7)
        blur15 = average(positive, 15)
        blur31 = average(positive, 31)
        variance7 = (average(positive.square(), 7) - blur7.square()).clamp_min(0.0)
        variance31 = (
            average(positive.square(), 31) - blur31.square()
        ).clamp_min(0.0)
        gx = F.pad(positive[..., 1:] - positive[..., :-1], (0, 1, 0, 0))
        gy = F.pad(positive[..., 1:, :] - positive[..., :-1, :], (0, 0, 0, 1))
        magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-6)
        laplacian = average(positive, 3) - positive
        chroma = (residual - residual_luma).square().mean(dim=1, keepdim=True).sqrt()
        illumination_luma = (
            parent["illumination"].float() * weights
        ).sum(dim=1, keepdim=True)
        maps = parent["maps"].float()
        cues = [
            residual_luma,
            positive,
            positive - blur3,
            blur3 - blur7,
            blur7 - blur15,
            blur15 - blur31,
            variance7.sqrt(),
            variance31.sqrt(),
            gx,
            gy,
            magnitude,
            laplacian,
            parent["specular_mask"].float(),
            parent["color_edge"].float(),
            parent["geometry_edge"].float(),
            maps[:, 3:4],
            maps[:, 4:5],
            observed_luma,
            diffuse_luma,
            chroma,
        ]
        return torch.cat(cues, dim=1)

    def material_prior_features(
        self,
        image_srgb: torch.Tensor,
        parent: dict[str, torch.Tensor],
        condition: torch.Tensor,
        attributes: torch.Tensor,
    ) -> torch.Tensor:
        """Build the de-lit full-resolution inputs for the local prior branch."""
        maps = parent["maps"].float()
        prompt = self.prompt(torch.cat([condition.float(), attributes.float()], dim=1))
        prompt = prompt[:, :, None, None].expand(-1, -1, *maps.shape[-2:])
        illumination_luma = parent["illumination"].float().mean(dim=1, keepdim=True)
        return torch.cat(
            [
                image_srgb.float(),
                parent["basecolor_linear"].float(),
                maps[:, 3:4],
                maps[:, 4:5],
                maps[:, 5:8],
                maps[:, 8:9],
                maps[:, 9:10],
                parent["color_edge"].float(),
                parent["geometry_edge"].float(),
                parent["effective_gate"].float(),
                illumination_luma,
                prompt,
            ],
            dim=1,
        )

    def forward(
        self,
        image_srgb: torch.Tensor,
        parent: dict[str, torch.Tensor],
        condition: torch.Tensor,
        attributes: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        maps = parent["maps"].float()
        prompt = self.prompt(torch.cat([condition.float(), attributes.float()], dim=1))
        prompt = prompt[:, :, None, None].expand(-1, -1, *maps.shape[-2:])
        specular_cues = self._specular_cues(image_srgb, parent)
        features = torch.cat(
            [
                image_srgb.float(),
                parent["basecolor_linear"].float(),
                parent["illumination"].float(),
                parent["specular_mask"].float(),
                parent["color_edge"].float(),
                parent["geometry_edge"].float(),
                parent["effective_gate"].float(),
                *specular_cues,
                maps[:, 3:9],
                prompt,
            ],
            dim=1,
        )
        full = self.stem(features)
        half = self.down_half(full)
        quarter = self.bottleneck(self.down_quarter(half))
        decoded = self.refine(self.up_full(self.up_half(quarter, half), full))
        evidence = torch.cat(
            [
                image_srgb.float(),
                parent["basecolor_linear"].float(),
                parent["illumination"].float(),
                *specular_cues,
                parent["specular_mask"].float(),
                maps[:, 3:5],
            ],
            dim=1,
        )
        frequency_cues = self._roughness_frequency_cues(image_srgb, parent)
        material_prior_features = self.material_prior_features(
            image_srgb, parent, condition, attributes
        )
        stable_material_cues = torch.cat(
            [
                parent["basecolor_linear"].float(),
                maps[:, 3:10],
                parent["color_edge"].float(),
                parent["geometry_edge"].float(),
            ],
            dim=1,
        )
        return {
            "roughness": (
                self.roughness(decoded)
                + self.roughness_spatial(decoded)
                + self.roughness_evidence(evidence)
                + self.roughness_frequency(frequency_cues)
            ),
            "roughness_calibration": self.roughness_calibration(
                frequency_cues, stable_material_cues, condition, attributes
            ),
            "roughness_material_prior": self.roughness_material_prior(
                material_prior_features
            ),
            "metallic": self.metallic(decoded),
            "normal": self.normal(decoded) + self.normal_detail(decoded),
            "height": self.height(decoded) + self.height_detail(decoded),
        }


class D70JointRecoveryNet(nn.Module):
    def __init__(self, parent: D57IntrinsicRecoveryNet) -> None:
        super().__init__()
        self.parent = parent
        self.physical = SharedPhysicalDecoder()
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)

    def train(self, mode: bool = True):
        super().train(mode)
        self.parent.eval()
        return self

    @staticmethod
    def _zero_mean_local(raw: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        value = torch.tanh(raw) * gate
        return value - value.mean(dim=(2, 3), keepdim=True)

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
            parent = self.parent(image_srgb, condition, attributes, valid_mask)
        maps = parent["maps"].float()
        raw = self.physical(image_srgb, parent, condition, attributes)

        rough_gate = torch.sigmoid(raw["roughness"][:, 2:3])
        rough_local = self._zero_mean_local(raw["roughness"][:, :1], rough_gate)
        rough_global = torch.tanh(
            raw["roughness"][:, 1:2].mean(dim=(2, 3), keepdim=True)
        )
        roughness = (
            maps[:, 3:4] + rough_local * 0.45 + rough_global * 0.15
        ).clamp(0.0, 1.0)
        roughness_precalibration = roughness
        calibration = raw["roughness_calibration"]
        calibration_gate = torch.sigmoid(calibration[:, 2:3])
        calibration_base_delta = (
            torch.tanh(calibration[:, :1]) * calibration_gate * 0.40
        )
        calibration_confidence_scale = torch.sigmoid(calibration[:, 3:4]) * 2.0
        calibration_class_scale = torch.sigmoid(calibration[:, 4:5]) * 2.0
        calibration_scale = calibration_confidence_scale * calibration_class_scale
        calibration_delta = calibration_base_delta * calibration_scale
        calibration_contrast = torch.exp(
            torch.tanh(calibration[:, 1:2])
            * calibration_gate
            * calibration_scale
            * 0.45
        )
        roughness_mean = roughness.mean(dim=(2, 3), keepdim=True)
        roughness = (
            roughness_mean
            + calibration_delta
            + (roughness - roughness_mean) * calibration_contrast
        ).clamp(0.0, 1.0)
        roughness_prematerial_prior = roughness
        material_prior = raw["roughness_material_prior"]
        material_prior_gate = torch.sigmoid(material_prior[:, 1:2])
        material_prior_delta = self._zero_mean_local(
            material_prior[:, :1], material_prior_gate
        )
        roughness = (roughness + material_prior_delta * 0.30).clamp(0.0, 1.0)
        prompt_roughness_prior, prompt_roughness_confidence = (
            self.physical.roughness_calibration.prompt_prior(condition, attributes)
        )
        roughness_mean = roughness.mean(dim=(2, 3), keepdim=True)
        prompt_blend = (
            self.physical.roughness_calibration.prompt_blend_alpha
            * prompt_roughness_confidence
        )
        roughness = (
            roughness + prompt_blend * (prompt_roughness_prior - roughness_mean)
        ).clamp(0.0, 1.0)

        metal_delta = torch.tanh(raw["metallic"][:, :1])
        metal_gate = torch.sigmoid(raw["metallic"][:, 1:2])
        metallic = torch.sigmoid(
            torch.logit(maps[:, 4:5].clamp(1.0e-4, 1.0 - 1.0e-4))
            + metal_delta * metal_gate * 5.5
        )

        normal_gate = torch.sigmoid(raw["normal"][:, 3:4])
        normal_parent = F.normalize(
            maps[:, 5:8] * 2.0 - 1.0, dim=1, eps=1.0e-6
        )
        normal_delta = torch.tanh(raw["normal"][:, :3]) * normal_gate * 0.42
        normal = F.normalize(normal_parent + normal_delta, dim=1, eps=1.0e-6)
        normal = F.normalize(
            torch.cat(
                (
                    normal[:, :2] * self.physical.normal_tangent_scale,
                    normal[:, 2:3],
                ),
                dim=1,
            ),
            dim=1,
            eps=1.0e-6,
        )
        normal_01 = normal * 0.5 + 0.5

        height_gate = torch.sigmoid(raw["height"][:, 2:3])
        height_local = self._zero_mean_local(raw["height"][:, :1], height_gate)
        height_global = torch.tanh(
            raw["height"][:, 1:2].mean(dim=(2, 3), keepdim=True)
        )
        height = (
            maps[:, 8:9] + height_local * 0.38 + height_global * 0.08
        ).clamp(0.0, 1.0)
        height_mean = height.mean(dim=(2, 3), keepdim=True)
        height = (
            height_mean
            + (height - height_mean) * self.physical.height_contrast_scale
        ).clamp(0.0, 1.0)
        ao_derived = d60.derive_ao_torch(height, normal_01)
        ao_correction = torch.tanh(raw["height"][:, 3:4]) * 0.04
        ao = (ao_derived + ao_correction).clamp(0.30, 1.0)

        valid = valid_mask.float().clamp(0.0, 1.0)
        refined = torch.cat(
            [maps[:, :3], roughness, metallic, normal_01, height, ao], dim=1
        )
        refined = refined * valid + maps * (1.0 - valid)
        return parent | {
            "maps": refined,
            "parent_maps": maps,
            "roughness": roughness,
            "roughness_precalibration": roughness_precalibration,
            "roughness_prematerial_prior": roughness_prematerial_prior,
            "roughness_calibration_delta": calibration_delta,
            "roughness_calibration_base_delta": calibration_base_delta,
            "roughness_calibration_scale": calibration_scale,
            "roughness_calibration_confidence_scale": calibration_confidence_scale,
            "roughness_calibration_class_scale": calibration_class_scale,
            "prompt_roughness_prior": prompt_roughness_prior,
            "prompt_roughness_confidence": prompt_roughness_confidence,
            "prompt_roughness_blend": prompt_blend,
            "roughness_calibration_contrast": calibration_contrast,
            "metallic": metallic,
            "normal": normal_01,
            "height": height,
            "ao_derived": ao_derived,
            "ao_correction": ao_correction,
            "raw_roughness": raw["roughness"],
            "raw_roughness_calibration": calibration,
            "raw_roughness_material_prior": material_prior,
            "raw_metallic": raw["metallic"],
            "raw_normal": raw["normal"],
            "raw_height": raw["height"],
        }


def manifest(model: D70JointRecoveryNet) -> dict[str, object]:
    total = sum(parameter.numel() for parameter in model.parameters())
    parent = sum(parameter.numel() for parameter in model.parent.parameters())
    return {
        "architecture": "D70JointRecoveryNet-SharedMultiscalePhysicalDecoder",
        "parameters": total,
        "d69_parent_parameters": parent,
        "shared_physical_decoder_parameters": total - parent,
        "trainable_parameters": sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        ),
        "basecolor_from_frozen_d69": True,
        "shared_multiscale_physical_features": True,
        "explicit_roughness_frequency_cues": True,
        "global_roughness_calibration": True,
        "absolute_roughness_statistics_bypass": True,
        "confidence_gated_roughness_calibration": True,
        "class_conditioned_roughness_calibration_scale": True,
        "train_fitted_prompt_roughness_prior": True,
        "prompt_roughness_blend_alpha": 0.60,
        "phase_aligned_roughness_material_prior": True,
        "normal_tangent_scale": float(model.physical.normal_tangent_scale),
        "height_contrast_scale": float(model.physical.height_contrast_scale),
        "independent_zero_initialized_output_heads": [
            "roughness",
            "metallic",
            "normal",
            "height_ao",
        ],
        "ao_policy": "derived from refined Height/Normal plus bounded 0.04 correction",
    }
