"""Regression coverage for the production improvements promoted to prod."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from module.device.platform2.emulator_base import EmulatorInstanceBase
from module.device.platform2.platform_base import PlatformBase
from tasks.Component.Costume.assets import CostumeAssets
from tasks.DailyTrifles.assets import DailyTriflesAssets


ROOT = Path(__file__).resolve().parents[1]


class ProductionImprovementTests(unittest.TestCase):
    def test_mumu_android_12_and_15_instance_names(self):
        for version in ('12', '15'):
            for index in range(4):
                name = f'MuMuPlayer-{version}.0-{index}'
                with self.subTest(name=name):
                    instance = EmulatorInstanceBase('', name, '')
                    self.assertEqual(instance.MuMuPlayer12_id, index)

    def test_numeric_instance_match_uses_configured_serial(self):
        instance = SimpleNamespace(
            MuMuPlayer12_id=0,
            serial='127.0.0.1:5555',
            name='MuMuPlayer-15.0-0',
            path='D:/MuMu/nx_main/MuMuNxMain.exe',
        )
        manager = SimpleNamespace(
            serial='127.0.0.1:16384',
            all_emulator_instances=[instance],
        )

        result = PlatformBase.find_emulator_instance(
            manager,
            serial='127.0.0.1:16384',
        )

        self.assertIs(result, instance)
        self.assertEqual(result.serial, '127.0.0.1:16384')

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


if __name__ == '__main__':
    unittest.main()
