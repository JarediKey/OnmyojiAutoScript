"""Exercise Dokan scheduling through the real scheduler without game dependencies."""
import ast
from datetime import datetime, time, timedelta
from pathlib import Path
from threading import Lock
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class Clock(datetime):
    current = datetime(2026, 9, 10, 5, 20)

    @classmethod
    def now(cls):
        return cls.current


def load_function(path, name, namespace, class_name=None):
    """Load production function bodies while excluding emulator/OCR imports."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    body = tree.body
    if class_name:
        body = next(node.body for node in body
                    if isinstance(node, ast.ClassDef) and node.name == class_name)
    node = next(node for node in body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class DokanScheduleTests(unittest.TestCase):
    def setUp(self):
        Clock.current = datetime(2026, 9, 10, 5, 20)
        self.random = SimpleNamespace(randint=Mock(return_value=571))
        namespace = dict(datetime=Clock, time=time, timedelta=timedelta,
                         random=self.random, logger=Mock(), ScriptError=RuntimeError,
                         convert_to_underscore=str.lower, dict_to_kv=Mock(return_value=""))
        for name in ("nearest_future", "parse_tomorrow_server"):
            load_function("module/config/utils.py", name, namespace)
        delay = load_function("module/config/config.py", "task_delay", namespace, "Config")
        set_next = load_function("tasks/base_task.py", "set_next_run", namespace, "BaseTask")
        next_run = load_function("tasks/Dokan/script_task.py", "next_run", namespace, "ScriptTask")
        self.scheduler = SimpleNamespace(
            server_update=time(5), failure_interval=timedelta(minutes=10),
            success_interval=timedelta(days=1), delay_date=1, float_time=time(0, 30),
            next_run=None)
        self.count = SimpleNamespace(remain_attack_count=1, daily_attack_count=2)
        dokan = SimpleNamespace(scheduler=self.scheduler, attack_count_config=self.count)
        self.config = SimpleNamespace(dokan=dokan, model=SimpleNamespace(dokan=dokan),
                                      reload=Mock(), save=Mock(), lock_config=Lock())
        self.config.task_delay = MethodType(delay, self.config)
        self.task = SimpleNamespace(config=self.config, start_time=datetime(2026, 9, 10, 5, 9, 31))
        self.task.set_next_run = MethodType(set_next, self.task)
        self.task.next_run = MethodType(next_run, self.task)

    def assert_scheduled(self, expected):
        self.assertEqual(self.scheduler.next_run, expected)
        self.config.save.assert_called_once_with()

    def test_second_round_uses_completion_time_without_jitter(self):
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 10, 5, 30))
        self.random.randint.assert_not_called()

    def test_second_round_is_not_limited_to_opening_retry_window(self):
        Clock.current = datetime(2026, 9, 10, 13, 52, 50)
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 10, 14, 2, 50))

    def test_interval_is_configurable(self):
        for interval in (timedelta(minutes=3), timedelta(minutes=10), timedelta(days=1)):
            with self.subTest(interval=interval):
                self.config.save.reset_mock()
                self.scheduler.failure_interval = interval
                self.task.next_run(is_dokan_activated=True)
                self.assert_scheduled(Clock.current + interval)
        self.random.randint.assert_not_called()

    def test_both_rounds_schedule_next_daily_clock_with_one_jitter(self):
        self.count.remain_attack_count = 0
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 11, 5, 9, 31))
        self.random.randint.assert_called_once_with(0, 1800)

    def test_jitter_bounds(self):
        self.count.remain_attack_count = 0
        for jitter in (0, 1800):
            with self.subTest(jitter=jitter):
                self.config.save.reset_mock()
                self.random.randint.return_value = jitter
                self.task.next_run(is_dokan_activated=True)
                self.assert_scheduled(datetime(2026, 9, 11, 5) + timedelta(seconds=jitter))

    def test_nine_am_preserves_shared_interval_schedule(self):
        self.count.remain_attack_count = 0
        self.scheduler.server_update = time(9)
        self.task.start_time = datetime(2026, 9, 10, 8, 40)
        self.scheduler.success_interval = timedelta(hours=3)
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 10, 11, 49, 31))
        self.random.randint.assert_called_once_with(0, 1800)

    def test_nine_am_second_round_still_uses_failure_interval(self):
        self.scheduler.server_update = time(9)
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 10, 5, 30))
        self.random.randint.assert_not_called()

    def test_single_round_setting_schedules_next_day(self):
        self.count.daily_attack_count = 1
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 11, 5, 9, 31))

    def test_skipped_day_does_not_schedule_second_round(self):
        self.task.next_run(skip_today=True, is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 11, 5, 9, 31))

    def test_unopened_before_daily_clock_preserves_exact_clock(self):
        Clock.current = datetime(2026, 9, 10, 4, 45, 18)
        self.scheduler.server_update = time(5, 0, 30)
        self.task.next_run(is_dokan_activated=False)
        self.assert_scheduled(datetime(2026, 9, 10, 5, 0, 30))
        self.random.randint.assert_not_called()

    def test_unopened_retries_through_two_hour_boundary(self):
        for now in (datetime(2026, 9, 10, 5), datetime(2026, 9, 10, 7)):
            with self.subTest(now=now):
                Clock.current = now
                self.config.save.reset_mock()
                self.task.next_run(is_dokan_activated=False)
                self.assert_scheduled(now + timedelta(minutes=10))
        self.random.randint.assert_not_called()

    def test_unopened_after_retry_window_schedules_next_day(self):
        Clock.current = datetime(2026, 9, 10, 7, 0, 1)
        self.task.next_run(is_dokan_activated=False)
        self.assert_scheduled(datetime(2026, 9, 11, 5, 9, 31))

    def test_daily_delay_configuration_is_preserved(self):
        self.count.remain_attack_count = 0
        self.scheduler.delay_date = 2
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 12, 5, 9, 31))

    def test_two_rounds_and_next_day_end_to_end(self):
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 10, 5, 30))
        self.config.save.reset_mock()
        self.task.start_time = self.scheduler.next_run
        Clock.current = datetime(2026, 9, 10, 5, 46)
        self.count.remain_attack_count = 0
        self.task.next_run(is_dokan_activated=True)
        self.assert_scheduled(datetime(2026, 9, 11, 5, 9, 31))
        self.random.randint.assert_called_once_with(0, 1800)


if __name__ == "__main__":
    unittest.main()
