"""Verify buff switching uses round controls with bounded state confirmation."""

import copy
import unittest
from unittest.mock import patch

from tasks.Component.GeneralBuff.general_buff import GeneralBuff


class FrameTimer:
    def __init__(self, *_args):
        self.frames = 0
    def start(self):
        return self
    def reached(self):
        self.frames += 1
        return self.frames > 12


class BuffTask(GeneralBuff):
    def __init__(self, states):
        self.states = iter(states)
        self.state = None
        self.clicks = []
        self.I_OPEN_YELLOW = copy.deepcopy(self.I_OPEN_YELLOW)
        self.I_CLOSE_RED = copy.deepcopy(self.I_CLOSE_RED)
    def screenshot(self):
        self.state = next(self.states, self.state)
    def appear(self, rule):
        return ((rule is self.I_OPEN_YELLOW and self.state == 'open')
                or (rule is self.I_CLOSE_RED and self.state == 'closed'))
    def click(self, rule, interval=None):
        self.clicks.append((rule, interval))
        return True


@patch('tasks.Component.GeneralBuff.general_buff.Timer', FrameTimer)
@patch('tasks.Component.GeneralBuff.general_buff.time.sleep')
class BuffSwitchControlTests(unittest.TestCase):
    def test_already_closed_does_not_click(self, _sleep):
        task = BuffTask(['closed'])
        self.assertTrue(task._set_buff_switch(False))
        self.assertEqual(task.clicks, [])

    def test_close_clicks_round_control_center_then_checks_fresh_frame(self, _sleep):
        task = BuffTask(['open', 'closed'])
        self.assertTrue(task._set_buff_switch(False))
        self.assertEqual(len(task.clicks), 1)
        button, interval = task.clicks[0]
        x, y = task.I_OPEN_YELLOW.front_center()
        self.assertEqual(button.roi_front, (x - 4, y - 4, 8, 8))
        self.assertEqual(interval, 2)

    def test_open_from_paused_state(self, _sleep):
        task = BuffTask(['closed', 'open'])
        self.assertTrue(task._set_buff_switch(True))
        self.assertEqual(len(task.clicks), 1)

    def test_unresponsive_control_stops_after_three_clicks(self, _sleep):
        task = BuffTask(['open'])
        self.assertFalse(task._set_buff_switch(False))
        self.assertEqual(len(task.clicks), 3)

    def test_unknown_state_does_not_click(self, _sleep):
        task = BuffTask(['unknown'])
        self.assertFalse(task._set_buff_switch(False))
        self.assertEqual(task.clicks, [])
