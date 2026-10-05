"""Exercise skin changes after matching has already loaded an older template."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from module.atom.image import RuleImage
from tasks.Component.Costume.costume_base import CostumeBase


class SkinTemplateReloadTests(unittest.TestCase):
    def test_replaced_skin_matches_new_pixels_after_old_template_was_loaded(self):
        rng = np.random.default_rng(6)
        old_pixels = rng.integers(0, 256, (24, 24, 3), dtype=np.uint8)
        new_pixels = rng.integers(0, 256, (24, 24, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as folder:
            old_file, new_file = Path(folder) / 'old.png', Path(folder) / 'new.png'
            cv2.imwrite(str(old_file), old_pixels)
            cv2.imwrite(str(new_file), new_pixels)
            def rule(path):
                return RuleImage((0, 0, 24, 24), (0, 0, 24, 24), 'Template matching', .8, str(path))
            original, replacement = rule(old_file), rule(new_file)
            task = SimpleNamespace(I_TEST=original)
            old_rgb = cv2.cvtColor(old_pixels, cv2.COLOR_BGR2RGB)
            new_rgb = cv2.cvtColor(new_pixels, cv2.COLOR_BGR2RGB)
            self.assertTrue(original.match(old_rgb))
            self.assertFalse(original.match(new_rgb))
            CostumeBase.replace_img(task, 'I_TEST', replacement)
            self.assertIs(task.I_TEST, original)
            self.assertTrue(task.I_TEST.match(new_rgb))
            self.assertFalse(task.I_TEST.match(old_rgb))

    def test_skin_change_preserves_fixed_search_region(self):
        original = RuleImage((1, 2, 3, 4), (10, 20, 30, 40), 'Template matching', .8, 'old.png')
        replacement = RuleImage((5, 6, 7, 8), (50, 60, 70, 80), 'Template matching', .9, 'new.png')
        task = SimpleNamespace(I_TEST=original)
        CostumeBase.replace_img(task, 'I_TEST', replacement, rp_roi_back=False)
        self.assertEqual(task.I_TEST.roi_back, (10, 20, 30, 40))
