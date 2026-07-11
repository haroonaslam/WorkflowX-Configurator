import itertools
import pathlib
import sys
import unittest

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anything_swap_bridge.src.crop import AnythingCropForSwap
from anything_swap_bridge.src.stitch import AnythingStitch
from anything_swap_bridge.utils import resize


def make_image(h=512, w=512, seed=0):
    generator = torch.Generator().manual_seed(seed)
    return torch.rand((1, h, w, 3), generator=generator)


def make_mask(h, w, x, y, mask_w, mask_h):
    mask = torch.zeros((1, h, w))
    mask[:, y : y + mask_h, x : x + mask_w] = 1.0
    return mask


CROP = dict(
    use_sam3=False,
    sam3_prompt="face",
    sam3_checkpoint="",
    threshold=0.5,
    refine_iterations=2,
    keep_model_loaded=True,
    select_mode="largest",
    object_index=0,
    expand_factor=1.4,
    expand_pixels=0,
    force_square=True,
    padding=16,
    edge_handling="shift",
    resize_mode="none",
    target_size=1024,
    upscale_method="lanczos",
    downscale_method="area",
    mask_grow=0,
    mask_blur=0,
    swap_prompt="test",
)
STITCH = dict(
    mask_mode="payload_mask",
    feather=0,
    color_match=False,
    color_match_method="mkl",
    color_match_strength=1.0,
)


class AnythingSwapBridgeTests(unittest.TestCase):
    def test_categories_and_identity_roundtrip(self):
        self.assertEqual(
            AnythingCropForSwap.CATEGORY,
            "WorkflowX_Configurator/Image/Anything Swap",
        )
        self.assertEqual(AnythingStitch.CATEGORY, AnythingCropForSwap.CATEGORY)

        image = make_image()
        mask = make_mask(512, 512, 200, 180, 90, 110)
        crop, _, _, _, payload, detected = AnythingCropForSwap().execute(
            image=image, mask=mask, **CROP
        )
        self.assertTrue(detected)
        output, changed = AnythingStitch().execute(stitch=payload, swapped=crop, **STITCH)
        self.assertTrue(torch.equal(output, image))
        self.assertGreater(float(changed.sum()), 0.0)

    def test_pixels_outside_changed_mask_are_exact_across_modes(self):
        image = make_image(240, 320, seed=1)
        mask = make_mask(240, 320, 12, 10, 48, 70)
        cases = itertools.product(
            ("shift", "pad_replicate", "clamp"),
            ("none", "target_size", "max_dimension"),
            (0, 8),
            (True, False),
        )
        for edge, resize_mode, feather, force_square in cases:
            if resize_mode == "target_size" and not force_square:
                continue
            with self.subTest(
                edge=edge,
                resize_mode=resize_mode,
                feather=feather,
                force_square=force_square,
            ):
                crop, _, _, _, payload, detected = AnythingCropForSwap().execute(
                    image=image,
                    mask=mask,
                    **{
                        **CROP,
                        "edge_handling": edge,
                        "resize_mode": resize_mode,
                        "target_size": 128,
                        "force_square": force_square,
                    },
                )
                self.assertTrue(detected)
                edited = torch.rand_like(crop)
                output, changed = AnythingStitch().execute(
                    stitch=payload,
                    swapped=edited,
                    **{**STITCH, "feather": feather},
                )
                untouched = changed[0] == 0
                self.assertTrue(torch.equal(output[0][untouched], image[0][untouched]))

    def test_edges_and_non_square_objects_roundtrip(self):
        image = make_image(400, 640, seed=2)
        for x, y in ((0, 0), (440, 380), (0, 380), (600, 0)):
            with self.subTest(position=(x, y)):
                mask = make_mask(400, 640, x, y, 40, 20)
                crop, _, _, _, payload, detected = AnythingCropForSwap().execute(
                    image=image,
                    mask=mask,
                    **{**CROP, "expand_factor": 3.0, "edge_handling": "pad_replicate"},
                )
                self.assertTrue(detected)
                self.assertEqual(crop.shape[1], crop.shape[2])
                output, _ = AnythingStitch().execute(stitch=payload, swapped=crop, **STITCH)
                self.assertTrue(torch.equal(output, image))

        tall_mask = make_mask(512, 512, 100, 100, 40, 160)
        image = make_image()
        crop, _, _, _, payload, detected = AnythingCropForSwap().execute(
            image=image, mask=tall_mask, **{**CROP, "force_square": False}
        )
        self.assertTrue(detected)
        self.assertGreater(crop.shape[1], crop.shape[2])
        output, _ = AnythingStitch().execute(stitch=payload, swapped=crop, **STITCH)
        self.assertTrue(torch.equal(output, image))

    def test_empty_mask_and_readable_input_errors(self):
        image = make_image()
        crop, _, _, _, payload, detected = AnythingCropForSwap().execute(
            image=image, mask=torch.zeros((1, 512, 512)), **CROP
        )
        self.assertFalse(detected)
        output, changed = AnythingStitch().execute(stitch=payload, swapped=crop, **STITCH)
        self.assertTrue(torch.equal(output, image))
        self.assertEqual(float(changed.sum()), 0.0)

        with self.assertRaisesRegex(ValueError, "no mask is connected"):
            AnythingCropForSwap().execute(image=image, **CROP)
        with self.assertRaisesRegex(ValueError, "'image' is not connected"):
            AnythingCropForSwap().execute(**CROP)
        with self.assertRaisesRegex(ValueError, "'stitch' is not connected"):
            AnythingStitch().execute(**STITCH)

    def test_batch_aspect_and_resized_return_validation(self):
        image = make_image()
        with self.assertRaisesRegex(ValueError, "single image"):
            AnythingCropForSwap().execute(
                image=torch.rand((3, 256, 256, 3)),
                mask=make_mask(256, 256, 50, 50, 40, 40).repeat(3, 1, 1),
                **CROP,
            )

        mask = make_mask(512, 512, 200, 180, 90, 110)
        crop, _, _, _, payload, _ = AnythingCropForSwap().execute(
            image=image, mask=mask, **CROP
        )
        wrong = torch.rand((1, crop.shape[1], crop.shape[2] * 2, 3))
        with self.assertRaisesRegex(ValueError, "aspect"):
            AnythingStitch().execute(stitch=payload, swapped=wrong, **STITCH)

        scaled = resize.resize_image(crop, crop.shape[2] * 2, crop.shape[1] * 2, "bicubic")
        output, _ = AnythingStitch().execute(stitch=payload, swapped=scaled, **STITCH)
        self.assertEqual(output.shape, image.shape)

    def test_selection_prompt_colour_and_bbox_helpers(self):
        image = make_image()
        stacked = torch.cat(
            [
                make_mask(512, 512, 20, 20, 30, 30),
                make_mask(512, 512, 200, 200, 90, 90),
            ],
            dim=0,
        )
        _, _, _, _, payload, detected = AnythingCropForSwap().execute(
            image=image, mask=stacked, **CROP
        )
        self.assertTrue(detected)
        self.assertGreater(payload["bbox"][0], 100)

        from anything_swap_bridge.utils.bboxes import scores
        from anything_swap_bridge.utils.colormatch import color_match
        from anything_swap_bridge.utils.prompting import render

        source = torch.rand((1, 64, 64, 3))
        full_mask = torch.ones((1, 64, 64))
        for method in ("reinhard", "mkl", "hm"):
            delta = (color_match(source, source.clone(), full_mask, method, 1.0) - source).abs().max()
            self.assertLess(float(delta), 2e-2, method)

        rendered = render(
            '{"style":"photo","w":{width},"o":"{target}"}',
            {"width": 1024, "target": "face"},
        )
        self.assertEqual(rendered, '{"style":"photo","w":1024,"o":"face"}')
        self.assertEqual(scores([{"score": 0.9}, {"score": 0.1}], 2), [0.9, 0.1])
        self.assertEqual(scores([(0, 0, 10, 10, 0.7)], 1), [0.7])
        self.assertIsNone(scores([{"score": 0.9}], 2))
        self.assertIsNone(scores(None, 1))


if __name__ == "__main__":
    unittest.main()
