"""Check soul presence, bounded selection and retry scheduling without a device."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from module.exception import TaskEnd
from tasks.CollectiveMissions.script_task import MC, ScriptTask


class SoulSelectionTask(ScriptTask):
    def __init__(self, frames):
        self.frames = iter(frames)
        self.frame = ('', False)
        self.now = 100.0
        self.presses = 0
        self.device = SimpleNamespace(image=None)
        self.O_SL_NUMBER = SimpleNamespace(ocr=lambda _: self.frame[0])
    def screenshot(self):
        self.now += .4
        self.frame = next(self.frames, self.frame)
    def ocr_appear(self, rule):
        raise AssertionError("Selection must not depend on grade OCR")
    def click(self, rule, interval=None):
        assert rule is self.L_SL_LONG
        assert rule.duration == 1500 and interval == 2.5
        self.presses += 1
        self.now += 1.5
        return True
    def sleep(self, seconds):
        self.now += seconds


def select(frames):
    task = SoulSelectionTask(frames)
    with patch('module.base.timer.time.time', side_effect=lambda: task.now), \
         patch('tasks.CollectiveMissions.script_task.time.sleep', side_effect=task.sleep):
        result = task._select_souls()
    return task, result


def test_zero_with_visible_level_long_presses_instead_of_exiting():
    task, result = select([('0', True), ('30', True)])
    assert result and task.presses == 1


def test_existing_selection_does_not_press_again():
    task, result = select([('30', True)])
    assert result and task.presses == 0


def test_missing_level_still_selects_visible_souls():
    task, result = select([('0', False), ('30', False)])
    assert result and task.presses == 1


def test_empty_inventory_is_bounded_even_without_grade_text():
    task, result = select([('0', False)])
    assert not result and task.presses == 3


def test_unresponsive_selection_is_bounded_to_three_presses():
    task, result = select([('0', True)])
    assert not result and task.presses == 3


def test_unreadable_count_is_not_assumed_zero():
    task, result = select([('', True)])
    assert not result and task.presses == 0 and task.now >= 115


@pytest.mark.parametrize('soul_result,success', [(False, False), (None, True)])
def test_run_schedules_unselected_souls_as_retry(soul_result, success):
    task = object.__new__(ScriptTask)
    task.config = SimpleNamespace(collective_missions=SimpleNamespace(
        missions_config=SimpleNamespace(missions_rule='test', missions_select='test')))
    task.device = SimpleNamespace(image=None)
    task.O_CM_NUMBER = SimpleNamespace(ocr=lambda _: (0, 30, 30))
    task.goto_page = Mock()
    task.ui_click = Mock()
    task.screenshot = Mock()
    task.select_mission = Mock()
    task.detect_best = Mock(return_value=(MC.SO2, 0))
    task._soul = Mock(return_value=soul_result)
    task.appear = Mock(return_value=True)
    task.set_next_run = Mock()
    before = datetime.now()
    with pytest.raises(TaskEnd):
        task.run()
    params = task.set_next_run.call_args.kwargs
    assert params['success'] is success
    if not success:
        assert params['server'] is False
        assert before + timedelta(minutes=10) <= params['target'] <= datetime.now() + timedelta(minutes=10)
    else:
        assert 'target' not in params
