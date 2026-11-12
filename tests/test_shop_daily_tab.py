"""Focused regression coverage for shop daily tab. """
import json
from pathlib import Path
import unittest
from tasks.DailyTrifles.assets import DailyTriflesAssets
from module.atom.image import ROI_BACK_EXPAND
from module.base.utils import expand_roi

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
            expand_roi((1162, 77, 98, 535), ROI_BACK_EXPAND),
        )
