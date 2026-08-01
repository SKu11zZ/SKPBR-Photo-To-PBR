from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
import torch

from skpbr.cli import default_checkpoint, load_model, run
from skpbr.io import MAP_FILES, periodic_seed_field
from skpbr.model import parameter_count, rich_periodic_seed_field
from skpbr.prompt import CONDITION_DIM, parse_prompt


class PublicContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.device = torch.device("cpu")
        cls.model, cls.payload = load_model(Path(default_checkpoint()), cls.device)

    def test_bilingual_prompt_contract(self) -> None:
        self.assertEqual(CONDITION_DIM, 93)
        cases = {
            "brushed aluminum, satin finish": ("bare_metal", "conductor"),
            "生锈的铜，带绿色铜锈，粗糙表面": ("rusted_metal", "mixed"),
            "蓝色汽车金属漆，亮光表面": ("automotive_paint", "coated_conductor"),
        }
        for prompt, expected in cases.items():
            parsed = parse_prompt(prompt)
            condition = parsed["condition"]
            self.assertEqual((parsed["material_class"], parsed["physical_regime"]), expected)
            self.assertIsInstance(condition, np.ndarray)
            self.assertEqual(condition.shape, (93,))
            self.assertEqual(condition.dtype, np.float32)
            self.assertTrue(np.isfinite(condition).all())

    def test_checkpoint_contract(self) -> None:
        state = self.payload["model"]
        self.assertEqual(sum(tensor.numel() for tensor in state.values()), 4_042_230)
        self.assertTrue(all(isinstance(key, str) for key in state))
        self.assertTrue(all(torch.is_tensor(value) for value in state.values()))
        self.assertEqual(parameter_count(self.model), 4_042_230)

    @torch.inference_mode()
    def test_image_and_text_only_forward(self) -> None:
        size = 64
        condition = torch.from_numpy(parse_prompt("rough gray concrete with pores")["condition"])[None]
        image = torch.rand(1, 3, size, size)
        present = torch.ones(1, 1, size, size)
        zeros6 = torch.zeros(1, 6, size, size)
        zeros12 = torch.zeros(1, 12, size, size)
        reconstructed = self.model(image, present, condition, zeros6, zeros12)["maps"]
        self.assertEqual(tuple(reconstructed.shape), (1, 10, size, size))
        self.assertTrue(torch.isfinite(reconstructed).all())

        seed = torch.tensor([42])
        absent = torch.zeros_like(present)
        generated_a = self.model(
            torch.zeros_like(image),
            absent,
            condition,
            periodic_seed_field(seed, size, size),
            rich_periodic_seed_field(seed, size, size),
        )["maps"]
        generated_b = self.model(
            torch.zeros_like(image),
            absent,
            condition,
            periodic_seed_field(seed, size, size),
            rich_periodic_seed_field(seed, size, size),
        )["maps"]
        self.assertTrue(torch.equal(generated_a, generated_b))

    def test_cli_writes_six_maps_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "input.png"
            rgb = np.zeros((128, 128, 3), dtype=np.uint8)
            rgb[..., 0] = 92
            rgb[..., 1] = 96
            rgb[..., 2] = 99
            Image.fromarray(rgb, "RGB").save(image_path)
            output = root / "output"
            metadata = run(
                Namespace(
                    image=image_path,
                    prompt="rough gray concrete with fine pores",
                    seed=41,
                    output=output,
                    checkpoint=Path(default_checkpoint()),
                    device="cpu",
                    resolution=128,
                )
            )
            self.assertEqual(metadata["mode"], "image_prompt_reconstruction")
            self.assertTrue((output / "preview.png").is_file())
            self.assertTrue((output / "inference_manifest.json").is_file())
            for name in MAP_FILES:
                self.assertTrue((output / "maps" / f"{name}.png").is_file())
            saved = json.loads((output / "inference_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["model"]["total_parameters"], 4_042_230)


if __name__ == "__main__":
    unittest.main()
