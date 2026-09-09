"""Focused regression coverage for shop daily tab. """
import json
from pathlib import Path
import unittest
from tasks.DailyTrifles.assets import DailyTriflesAssets

ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    def test_daily_tab_source_and_generated_asset_are_synchronized(self):
        source = json.loads(
            (ROOT / 'tasks/DailyTrifles/store/image.json').read_text(
                encoding='utf-8'))
        daily = next(item for item in source
                     if item['itemName'] == 'gift_recommend')

        self.assertEqual(daily['roiBack'], '1162,77,98,535')
        self.assertEqual(
            tuple(DailyTriflesAssets.I_GIFT_RECOMMEND.roi_back),
            (1162, 77, 98, 535),
        )
