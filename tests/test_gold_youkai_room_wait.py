"""Exercise GoldYoukai waiting deadlines and entry confirmation without a game."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from module.exception import GameStuckError
from tasks.GoldYoukai.script_task import ScriptTask


class RoomTask(ScriptTask):
    def __init__(self, frames):
        self.frames = iter(frames)
        self.now = 100.0
        self.scene = None
        self.empty = 4
        self.button = True
        self.clicks = []
        self.device = SimpleNamespace(stuck_record_clear=Mock(), stuck_record_add=Mock())
    def screenshot(self):
        self.now, self.scene, self.empty, self.button = next(self.frames)
    def is_in_prepare(self, _):
        return self.scene == 'prepare'
    def is_in_real_battle(self, _):
        return self.scene == 'battle'
    def is_in_room(self, _):
        return self.scene == 'room'
    def appear(self, rule, **_):
        if rule is self.I_GI_IN_ROOM:
            return self.scene == 'room'
        if rule is self.I_FIRE:
            return self.button
        slots = (self.I_ADD_5_1, self.I_ADD_5_2, self.I_ADD_5_3, self.I_ADD_5_4)
        return any(rule is slot for slot in slots[:self.empty])
    def appear_then_click(self, rule, **kwargs):
        assert kwargs['interval'] == 2
        if self.appear(rule):
            self.clicks.append(self.now)
            return True
        return False


def run(frames):
    task = RoomTask(frames)
    with patch('module.base.timer.time.time', side_effect=lambda: task.now):
        task.wait_for_full_team()
    task.device.stuck_record_add.assert_any_call('PREPARE_BEFORE_BATTLE')
    assert task.device.stuck_record_clear.call_count == 2
    return task


def test_one_teammate_does_not_start_early_but_180_seconds_does():
    task = run([(101, 'room', 3, True), (151, 'room', 3, True),
                (279, 'room', 3, True), (281, 'room', 3, True), (282, 'prepare', 0, False)])
    assert task.clicks == [281]


def test_full_team_is_confirmed_across_frames_then_starts_early():
    task = run([(101, 'room', 0, True), (102, 'room', 0, True),
                (104, 'room', 0, True), (105, 'battle', 0, False)])
    assert task.clicks == [104]


def test_departure_resets_full_team_confirmation():
    task = run([(101, 'room', 0, True), (102, 'room', 0, True),
                (103, 'room', 1, True), (104, 'room', 0, True),
                (105, 'room', 0, True), (107, 'room', 0, True), (108, 'prepare', 0, False)])
    assert task.clicks == [107]


def test_game_auto_start_needs_no_extra_challenge_click():
    task = run([(101, 'room', 3, True), (221, 'battle', 0, False)])
    assert task.clicks == []


def test_room_detection_miss_does_not_mean_battle_started():
    task = run([(101, 'unknown', 0, False), (103, 'room', 3, True),
                (281, 'room', 3, True), (282, 'battle', 0, False)])
    assert task.clicks == [281]


def test_unresponsive_start_is_bounded_and_long_wait_marker_is_cleared():
    task = RoomTask([(281, 'room', 3, True), (297, 'room', 3, True)])
    with patch('module.base.timer.time.time', side_effect=lambda: task.now):
        with pytest.raises(GameStuckError, match='within 15 seconds'):
            task.wait_for_full_team()
    assert task.clicks == [281]
    assert task.device.stuck_record_clear.call_count == 2


def test_missing_room_times_out_without_blind_clicks():
    task = RoomTask([(101, 'unknown', 0, False), (281, 'unknown', 0, False)])
    with patch('module.base.timer.time.time', side_effect=lambda: task.now):
        with pytest.raises(GameStuckError, match='after 180 seconds'):
            task.wait_for_full_team()
    assert task.clicks == []
