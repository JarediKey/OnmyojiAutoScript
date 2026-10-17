"""Check shared confirmation geometry, context and dialog recovery."""

from pathlib import Path
from types import SimpleNamespace
import ast
import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from module.exception import GameStuckError
from tasks.GlobalGame.confirmation import DialogConfirmation
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.HeroTest.assets import HeroTestAssets
from tasks.base_task import BaseTask


ROOT = Path(__file__).resolve().parents[1]


class SharedConfirmationTests(unittest.TestCase):
    def test_all_active_button_variants_return_the_matched_click_region(self):
        for source, position in (
            (GlobalGameAssets.I_UI_CONFIRM, (665, 407)),
            (GlobalGameAssets.I_UI_CONFIRM_SAMLL, (680, 392)),
            (GlobalGameAssets.I_UI_CONFIRM_SMALL, (672, 513)),
            (GlobalGameAssets.I_UI_CONFIRM_PLAIN, (419, 617)),
            (GlobalGameAssets.I_UI_CONFIRM_BLUE, (377, 630)),
        ):
            with self.subTest(button=source.name):
                image = np.zeros((720, 1280, 3), dtype=np.uint8)
                x, y = position
                h, w = source.image.shape[:2]
                image[y:y+h, x:x+w] = source.image
                rule = DialogConfirmation()
                self.assertTrue(rule.match(image))
                px, py = rule.coord()
                self.assertTrue(x <= px < x+w and y <= py < y+h)

    def test_reset_and_empty_frames_are_not_plain_confirmations(self):
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        rule = DialogConfirmation()
        self.assertFalse(rule.match(image))
        reset = HeroTestAssets.I_BCMJ_RESET_CONFIRM
        x, y, _, _ = reset.roi_front
        h, w = reset.image.shape[:2]
        image[y:y+h, x:x+w] = reset.image
        self.assertFalse(rule.match(image))
        self.assertTrue(reset.match(image))

    def test_summon_confirmation_is_not_added_to_unknown_page_closers(self):
        from tasks.GameUi.navigator import GameUi
        self.assertFalse(any(isinstance(rule, DialogConfirmation)
                             for rule in GameUi.DEFAULT_UNKNOWN_CLOSERS))

    def test_network_popup_uses_existing_error_recovery_without_clicking(self):
        task = object.__new__(BaseTask)
        task.device = Mock()
        task._burst = Mock()
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        rule = GlobalGameAssets.I_NETWORK_ERROR
        x, y, _, _ = rule.roi_front
        h, w = rule.image.shape[:2]
        image[y:y+h, x:x+w] = rule.image
        task.device.image = image
        with self.assertRaisesRegex(GameStuckError, 'server disconnected'):
            task.screenshot()
        task.device.click.assert_not_called()

    def test_normal_screenshot_does_not_trigger_network_recovery(self):
        task = object.__new__(BaseTask)
        task.device = Mock(image=np.zeros((720, 1280, 3), dtype=np.uint8))
        task._burst = Mock()
        self.assertIs(task.screenshot(), task.device.image)
        task.device.click.assert_not_called()

    def test_dokan_pending_dialog_is_confirmed_before_another_exit_click(self):
        from tasks.Dokan.script_task import ScriptTask
        task = object.__new__(ScriptTask)
        task.ui_click_until_disappear = Mock()
        task.click = Mock()
        task.device = SimpleNamespace(image=np.zeros((720, 1280, 3), dtype=np.uint8))
        rule = GlobalGameAssets.I_UI_CONFIRM
        x, y, _, _ = rule.roi_front
        h, w = rule.image.shape[:2]
        task.device.image[y:y+h, x:x+w] = rule.image
        task.screenshot = Mock()
        task.interval_timer = {}
        task.appear = lambda target: (
            isinstance(target, DialogConfirmation) and target.match(task.device.image))
        task.quit_battle()
        task.ui_click_until_disappear.assert_called_once_with(task.I_UI_CONFIRM_DIALOG)
        task.click.assert_not_called()

    def test_legacy_reward_loop_acknowledges_inventory_notice_before_reward(self):
        from tasks.Component.GeneralBattle.general_battle import GeneralBattle
        task = object.__new__(GeneralBattle)
        frames = iter(('reward', 'reward', 'overflow', 'done'))
        task.frame = None
        task.device = Mock()
        task.screenshot = lambda: setattr(task, 'frame', next(frames))
        task.appear = lambda target, **kwargs: target is task.I_REWARD and task.frame == 'reward'
        task.appear_then_click = Mock(side_effect=lambda target, **kwargs:
                                      target is task.I_UI_GOTIT_SMALL and task.frame == 'overflow')
        task.wait_until_appear = Mock(return_value=True)
        task._hook_special_reward = Mock(return_value=False)
        task.battle_wait(False)
        self.assertTrue(any(call.args[0] is task.I_UI_GOTIT_SMALL
                            for call in task.appear_then_click.call_args_list))


if __name__ == '__main__':
    unittest.main()
