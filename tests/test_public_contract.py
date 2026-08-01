from __future__ import annotations

from pathlib import Path
from argparse import Namespace
import tempfile
import unittest

import numpy as np
from PIL import Image
import torch

from skpbr.cli import default_checkpoint, load_model, run
from skpbr.io import NON_BASECOLOR_MAPS, sha256
from skpbr.model import parameter_count
from skpbr.prompt import CONDITION_DIM, parse_prompt


PROMPTS = (
    "dark rubber, rough matte finish",
    "rough coarse steel",
    "white marble with subtle gray veins, polished finish",
    "cyan blue automotive clearcoat, glossy metallic finish",
)


class PublicContractTest(unittest.TestCase):
    def test_prompt_contract(self) -> None:
        self.assertEqual(CONDITION_DIM, 72)
        for value in PROMPTS:
            parsed = parse_prompt(value)
            condition = parsed["condition_vector"]
            self.assertIsInstance(condition, np.ndarray)
            self.assertEqual(condition.shape, (72,))
            self.assertEqual(condition.dtype, np.float32)
            self.assertTrue(np.isfinite(condition).all())

    def test_checkpoint_is_tensor_only(self) -> None:
        checkpoint = Path(default_checkpoint())
        self.assertTrue(checkpoint.is_file())
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.assertEqual(len(state), 104)
        self.assertTrue(all(isinstance(key, str) for key in state))
        self.assertTrue(all(torch.is_tensor(value) for value in state.values()))

    def test_parameter_count_and_exact_screen_invariance(self) -> None:
        model = load_model(Path(default_checkpoint()), torch.device("cpu"))
        self.assertEqual(parameter_count(model), 266_241)
        parent = torch.rand(1, 11, 64, 64)
        parent[:, -1:] = 1.0
        condition = torch.tensor(
            parse_prompt(PROMPTS[0])["condition_vector"], dtype=torch.float32
        )[None]
        first = model(torch.rand(1, 3, 128, 128), parent, condition)[
            "basecolor"
        ]
        second = model(torch.zeros(1, 3, 128, 128), parent, condition)[
            "basecolor"
        ]
        self.assertTrue(torch.equal(first, second))

    def test_source_free_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            parent = tmp_path / "parent"
            parent.mkdir()
            rgb = np.zeros((512, 512, 3), dtype=np.uint8)
            rgb[..., 0] = 72
            rgb[..., 1] = 76
            rgb[..., 2] = 81
            Image.fromarray(rgb, mode="RGB").save(parent / "basecolor.png")
            normal = np.zeros_like(rgb)
            normal[..., 0] = 128
            normal[..., 1] = 128
            normal[..., 2] = 255
            Image.fromarray(normal, mode="RGB").save(parent / "normal.png")
            for name, value in (
                ("roughness", 190),
                ("metallic", 220),
                ("height", 128),
                ("ao", 245),
            ):
                Image.fromarray(
                    np.full((512, 512), value, dtype=np.uint8), mode="L"
                ).save(parent / f"{name}.png")
            image = tmp_path / "reference.png"
            Image.fromarray(rgb, mode="RGB").save(image)
            confidence = tmp_path / "visible_confidence.png"
            Image.fromarray(
                np.full((512, 512), 255, dtype=np.uint8), mode="L"
            ).save(confidence)
            output = tmp_path / "output"
            metadata = run(
                Namespace(
                    image=image,
                    prompt="rough coarse steel",
                    parent_dir=parent,
                    visible_confidence=confidence,
                    output=output,
                    checkpoint=Path(default_checkpoint()),
                    device="cpu",
                )
            )
            self.assertEqual(metadata["model_parameter_count"], 266_241)
            self.assertTrue((output / "basecolor.png").is_file())
            self.assertTrue((output / "metadata.json").is_file())
            for name in NON_BASECOLOR_MAPS:
                self.assertEqual(
                    sha256(parent / f"{name}.png"),
                    sha256(output / f"{name}.png"),
                )


if __name__ == "__main__":
    unittest.main()
