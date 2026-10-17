"""Exercise shifted dialogs and delayed entry without a live game."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import numpy as np

from module.exception import GameStuckError
from tasks.HeroTest.assets import HeroTestAssets
from tasks.HeroTest.script_task import ScriptTask


class EntryTask(ScriptTask):
    def __init__(self, phase='home', fire_dialog=None, confirm_works=True):
        self.now = 100.0
        self.phase = phase
        self.fire_dialog = fire_dialog
        self.confirm_works = confirm_works
        self.events = []
        self.pending = []
        self.last_click = {}
        self.device = Mock()
        self.set_next_run = Mock()

    def screenshot(self):
        self.now += .2
        for when, phase in list(self.pending):
            if self.now >= when:
                self.phase = phase
                self.pending.remove((when, phase))
        if self.now > 132:
            raise AssertionError('Entry did not respect its deadline')

    def is_in_battle(self, _):
        return self.phase in ('prepare', 'battle')

    def appear(self, rule, **kwargs):
        return rule is self.I_REAL_MONEY and self.phase == 'tickets'

    def appear_then_click(self, rule, interval):
        name = ('start' if rule is self.I_START_CHALLENGE else
                'reset' if rule is self.I_BCMJ_RESET_CONFIRM else 'fire')
        visible = self.phase == name if name != 'fire' else self.phase == 'home'
        if not visible or self.now-self.last_click.get(name, 0) < interval:
            return False
        self.last_click[name] = self.now
        self.events.append((name, self.now))
        if name == 'fire' and self.fire_dialog:
            target = self.fire_dialog(sum(kind == 'fire' for kind, _ in self.events))
            if target:
                self.pending.append((self.now+.8, target))
        elif name == 'reset' and self.confirm_works:
            self.phase = 'transition'
            self.pending.append((self.now+.8, 'start'))
        elif name == 'start' and self.confirm_works:
            self.phase = 'transition'
            self.pending.append((self.now+1.5, 'prepare'))
        return True


class HeroEntryTests(unittest.TestCase):
    def run_entry(self, task):
        with patch('module.base.timer.time.time', side_effect=lambda: task.now), \
                patch('tasks.HeroTest.script_task.random.randint', return_value=3):
            return task.enter_battle()

    def test_open_start_dialog_is_confirmed_without_background_challenge_clicks(self):
        task = EntryTask('start')
        self.assertTrue(self.run_entry(task))
        self.assertEqual([name for name, _ in task.events], ['start'])

    def test_reset_and_start_dialogs_are_handled_as_separate_states(self):
        task = EntryTask(fire_dialog=lambda count: 'reset')
        self.assertTrue(self.run_entry(task))
        self.assertEqual([name for name, _ in task.events], ['fire', 'reset', 'start'])

    def test_dialog_arriving_after_final_challenge_still_gets_confirmed(self):
        task = EntryTask(fire_dialog=lambda count: 'start' if count == 3 else None)
        self.assertTrue(self.run_entry(task))
        self.assertEqual([name for name, _ in task.events], ['fire', 'fire', 'fire', 'start'])

    def test_ignored_challenge_clicks_are_spaced_and_use_existing_recovery(self):
        task = EntryTask()
        with self.assertRaises(GameStuckError):
            self.run_entry(task)
        times = [time for name, time in task.events if name == 'fire']
        self.assertEqual(len(times), 3)
        self.assertTrue(all(b-a >= 2 for a, b in zip(times, times[1:])))
        task.set_next_run.assert_not_called()

    def test_unknown_page_has_a_deadline_and_no_blind_clicks(self):
        task = EntryTask('unknown')
        with self.assertRaises(GameStuckError):
            self.run_entry(task)
        self.assertEqual(task.events, [])
        task.set_next_run.assert_not_called()

    def test_insufficient_tickets_keep_the_normal_skip(self):
        task = EntryTask('tickets')
        self.assertFalse(self.run_entry(task))
        self.assertEqual(task.events, [])

    def test_shifted_start_text_is_detected_without_accepting_confirm_reset(self):
        rule = deepcopy(HeroTestAssets.I_START_CHALLENGE)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        h, w = rule.image.shape[:2]
        image[414:414+h, 680:680+w] = rule.image
        self.assertTrue(rule.match(image))
        old = deepcopy(rule)
        old.roi_back = (685, 407, 142, 47)
        self.assertFalse(old.match(image))
        image[:] = 0
        reset = HeroTestAssets.I_BCMJ_RESET_CONFIRM.image
        h, w = reset.shape[:2]
        image[407:407+h, 664:664+w] = reset
        self.assertFalse(rule.match(image))


if __name__ == '__main__':
    unittest.main()
