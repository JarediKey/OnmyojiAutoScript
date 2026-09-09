"""Focused regression coverage for cloud courtyard. """
import json
from pathlib import Path
import unittest
from tasks.Component.Costume.assets import CostumeAssets

ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    def test_cloud_courtyard_source_and_generated_assets_are_synchronized(self):
        expected = {
            'pet_house_13': (0, 269, 1280, 37),
            'main_goto_town_13': (0, 191, 1280, 54),
            'check_main_13': (0, 273, 1280, 31),
            'main_goto_exploration_13': (0, 125, 1280, 64),
        }
        source = json.loads(
            (ROOT / 'tasks/Component/Costume/main13/image.json').read_text(
                encoding='utf-8'))

        for item in source:
            name = item['itemName']
            if name not in expected:
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    tuple(map(int, item['roiBack'].split(','))),
                    expected[name],
                )
                generated = getattr(CostumeAssets, f'I_{name.upper()}')
                self.assertEqual(tuple(generated.roi_back), expected[name])
