"""Pixel and OCR-pipeline regressions without model downloads or device access."""

import importlib
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from module.ocr.color_filter import OcrMethod, apply_color_filter, parse_ocr_method


class ColorFilterTests(unittest.TestCase):
    def test_default_preserves_identity_and_enum_value(self):
        for method in ("Default", "DEFAULT", " default ", OcrMethod.DEFAULT):
            with self.subTest(method=method):
                parsed, bounds = parse_ocr_method(method)
                image = np.zeros((2, 2), dtype=np.uint16)
                self.assertIs(parsed, OcrMethod.DEFAULT)
                self.assertEqual(parsed.value, 1)
                self.assertIsNone(bounds)
                self.assertIs(apply_color_filter(image, parsed, bounds), image)

    def test_rgb_bounds_are_inclusive_and_input_is_unchanged(self):
        image = np.array([[[204, 204, 204], [255, 255, 255], [203, 255, 255], [255, 200, 255]]], dtype=np.uint8)
        before = image.copy()
        result = apply_color_filter(image, *parse_ocr_method("CF_RGB(CCCCCC,FFFFFF)"))
        expected = before.copy()
        expected[0, 2:] = 0
        np.testing.assert_array_equal(result, expected)
        np.testing.assert_array_equal(image, before)
        self.assertFalse(np.shares_memory(result, image))

    def test_hsv_selection_keeps_original_rgb_pixels(self):
        image = np.array([[[220, 180, 80], [255, 0, 0], [0, 0, 255], [255, 255, 255]]], dtype=np.uint8)
        original = image.copy()
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        self.assertTrue(np.all(hsv[0, 0] >= (9, 128, 180)))
        self.assertTrue(np.all(hsv[0, 0] <= (30, 210, 255)))
        result = apply_color_filter(image, *parse_ocr_method("CF_HSV(0980B4,1ED2FF)"))
        expected = np.zeros_like(image)
        expected[0, 0] = original[0, 0]
        np.testing.assert_array_equal(result, expected)
        np.testing.assert_array_equal(image, original)
        self.assertEqual(result.dtype, image.dtype)
        self.assertEqual(result.shape, image.shape)

    def test_case_and_whitespace(self):
        self.assertEqual(parse_ocr_method(" cf_hsv ( 0980b4 , 1ed2ff ) "),
                         (OcrMethod.CF_HSV, ((9, 128, 180), (30, 210, 255))))

    def test_invalid_methods_fail_explicitly(self):
        for method in ("", "Other", "Default()", "CF_RGB", "CF_RGB(CCC,FFFFFF)",
                       "CF_RGB(ZZZZZZ,FFFFFF)", "CF_RGB(FFFFFF,000000)",
                       "CF_HSV(B40000,B4FFFF)", "CF_RGB(000000,FFFFFF)junk",
                       "CF_RGB(000000,FFFFFF,FFFFFF)", "CF_HSV(0980B4,1E70FF)",
                       OcrMethod.CF_RGB, None, 1):
            with self.subTest(method=method), self.assertRaises(ValueError):
                parse_ocr_method(method)

    def test_filter_rejects_non_rgb_or_non_uint8(self):
        method, bounds = parse_ocr_method("CF_RGB(000000,FFFFFF)")
        for image in (np.zeros((2, 2), dtype=np.uint8),
                      np.zeros((2, 2, 4), dtype=np.uint8),
                      np.zeros((2, 2, 3), dtype=np.float32)):
            with self.subTest(shape=image.shape, dtype=image.dtype), self.assertRaises(ValueError):
                apply_color_filter(image, method, bounds)

    def test_existing_task_ocr_methods_still_parse(self):
        count = 0
        for path in (Path(__file__).resolve().parents[1] / "tasks").rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, list):
                continue
            for rule in data:
                if isinstance(rule, dict) and "mode" in rule and "keyword" in rule:
                    with self.subTest(path=str(path), name=rule.get("itemName")):
                        parse_ocr_method(rule.get("method", "Default"))
                    count += 1
        self.assertGreater(count, 0)


class OcrPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Replace only external model-loading/service boundaries; use actual OCR
        # classes, image operations, cropping, and result postprocessing.
        dependencies = {}
        for name in ("ppocronnx", "ppocronnx.predict_system", "module.ocr.models",
                     "module.ocr.ppocr", "module.logger"):
            dependencies[name] = ModuleType(name)
        dependencies["ppocronnx.predict_system"].BoxedResult = object
        dependencies["module.ocr.models"].get_ocr_model = Mock(side_effect=AssertionError("Unexpected model load"))
        dependencies["module.ocr.ppocr"].TextSystem = Mock(side_effect=AssertionError("Unexpected model load"))
        dependencies["module.logger"].logger = Mock()
        cls.boundaries = patch.dict(sys.modules, dependencies)
        cls.boundaries.start()
        try:
            cls.RuleOcr = importlib.import_module("module.atom.ocr").RuleOcr
            cls.base = importlib.import_module("module.ocr.base_ocr")
        except Exception:
            cls.boundaries.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.boundaries.stop()

    def make_rule(self, method="Default", mode="Single", roi=(1, 1, 2, 1)):
        rule = self.RuleOcr(name="test", mode=mode, method=method,
                            roi=roi, area=roi, keyword="")
        rule.model = Mock()
        return rule

    def test_enum_import_contract(self):
        self.assertIs(self.base.OcrMethod, OcrMethod)
        rule = self.make_rule(OcrMethod.DEFAULT)
        self.assertIs(rule.method, OcrMethod.DEFAULT)

    def test_single_line_filters_crop_before_model_call(self):
        image = np.full((3, 5, 3), 255, dtype=np.uint8)
        image[1, 2] = (100, 255, 255)
        before = image.copy()
        rule = self.make_rule("CF_RGB(CCCCCC,FFFFFF)")
        rule.model.ocr_single_line.return_value = ("text", 0.99)
        self.assertEqual(rule.ocr(image), "text")
        np.testing.assert_array_equal(rule.model.ocr_single_line.call_args.args[0],
                                      np.array([[[255, 255, 255], [0, 0, 0]]], dtype=np.uint8))
        np.testing.assert_array_equal(image, before)

    def test_default_single_line_input_is_unchanged(self):
        image = np.arange(45, dtype=np.uint8).reshape(3, 5, 3)
        rule = self.make_rule()
        rule.model.ocr_single_line.return_value = ("text", 0.99)
        self.assertEqual(rule.ocr(image), "text")
        np.testing.assert_array_equal(rule.model.ocr_single_line.call_args.args[0], image[1:2, 1:3])

    def test_detection_filters_before_canvas_padding(self):
        image = np.array([[[220, 180, 80], [255, 255, 255]]], dtype=np.uint8)
        rule = self.make_rule("CF_HSV(0980B4,1ED2FF)", mode="Full", roi=(0, 0, 2, 1))
        rule.model.detect_and_ocr.return_value = []
        self.assertEqual(rule.detect_and_ocr(image), [])
        received = rule.model.detect_and_ocr.call_args.args[0]
        expected = np.zeros((32, 32, 3), dtype=np.uint8)
        expected[0, 0] = image[0, 0]
        np.testing.assert_array_equal(received, expected)

    def test_legacy_abyss_rules_load_and_preserve_digit_postprocessing(self):
        rules = [("damage", "Digit", "CF_HSV(0980B4,1ED2FF)")]
        rules += [(name + "_done", "Single", "CF_RGB(CCCCCC,FFFFFF)")
                  for name in ("dragon", "peacock", "fox", "leopard")]
        for name, mode, method in rules:
            with self.subTest(name=name):
                rule = self.make_rule(method, mode, roi=(0, 0, 2, 1))
                rule.model.ocr_single_line.return_value = ("42", 0.99)
                self.assertEqual(rule.ocr(np.full((1, 2, 3), 220, dtype=np.uint8)),
                                 42 if mode == "Digit" else "42")


if __name__ == "__main__":
    unittest.main()
