"""Exercise clone selection without starting games or changing Android users."""

import ast
import json
from pathlib import Path
import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from module.device.app_control import AppControl
from module.device.connection import Connection
from module.exception import RequestHumanTakeover
from tasks.Script.config_device import Device as DeviceConfig


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'com.netease.onmyoji.wyzymnqsd_cps'
USERS = (0, 10, 11, 12, 13, 14)


class FakeAndroid:
    def __init__(self, selected=12):
        self.selected = selected
        self.users = USERS
        self.installed = set(USERS)
        self.commands = []
        self.failures = {}
        self.resolved = PACKAGE + '/com.netease.onmyoji.tag0'
        self.foreground = f'topResumedActivity=ActivityRecord{{abc u{selected} {PACKAGE}/.Client t2}}'

    def shell(self, command, **kwargs):
        args = tuple(shlex.split(command.split('; printf', 1)[0]))
        self.commands.append(args)
        if args in self.failures:
            return self.failures[args]
        if args == ('pm', 'list', 'users'):
            body = 'Users:\n' + '\n'.join(f'UserInfo{{{user}:clone:1020}}' for user in self.users)
        elif args[:3] == ('pm', 'list', 'packages'):
            body = f'package:{PACKAGE}' if int(args[4]) in self.installed else ''
        elif args[:3] == ('cmd', 'package', 'resolve-activity'):
            body = self.resolved
        elif args == ('dumpsys', 'activity', 'activities'):
            body = self.foreground
        else:
            body = ''
        return body + '\nOAS_APP_EXIT:0\n'

    @property
    def mutations(self):
        return [args for args in self.commands if args[0] == 'am']


def device(user_id=12, method='uiautomator2'):
    obj = object.__new__(AppControl)
    obj.config = SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(
        user_id=user_id, screenshot_method=method, control_method=method)))
    obj.serial = '127.0.0.1:16512'
    obj.package = PACKAGE
    android = FakeAndroid(user_id)
    obj.adb_shell = android.shell
    return obj, android


def test_user_setting_defaults_validation_template_and_translations():
    assert DeviceConfig().user_id == -1
    for value in (-1, 0, 12):
        assert DeviceConfig(user_id=value).user_id == value
    for value in (-2, 1.5, 'not-a-user'):
        with pytest.raises(ValidationError):
            DeviceConfig(user_id=value)
    schema = DeviceConfig.model_json_schema()['properties']['user_id']
    assert schema['type'] == 'integer'
    assert schema['minimum'] == -1
    assert schema['description'] == 'user_id_help'
    template = json.loads((ROOT / 'config/template.json').read_text(encoding='utf-8'))
    assert template['script']['device']['user_id'] == -1
    for language in ('en-US', 'zh-CN'):
        data = json.loads((ROOT / f'assets/i18n/{language}.json').read_text(encoding='utf-8'))
        assert data['user_id'] and data['user_id_help']


@pytest.mark.parametrize('method', ['uiautomator2', 'ADB'])
def test_disabled_selection_preserves_existing_app_control(method):
    obj, android = device(-1, method)
    obj.app_start_uiautomator2 = Mock()
    obj.app_start_adb = Mock()
    obj.app_stop_uiautomator2 = Mock()
    obj.app_stop_adb = Mock()
    obj.app_current_uiautomator2 = Mock(return_value=PACKAGE)
    obj.app_current_adb = Mock(return_value=PACKAGE)
    obj.ensure_app_user()
    obj.app_start()
    assert obj.app_is_running()
    obj.app_stop()
    suffix = 'uiautomator2' if method == 'uiautomator2' else 'adb'
    getattr(obj, 'app_start_' + suffix).assert_called_once_with()
    getattr(obj, 'app_stop_' + suffix).assert_called_once_with()
    getattr(obj, 'app_current_' + suffix).assert_called_once_with()
    assert android.commands == []


@pytest.mark.parametrize('selected', [0, 12])
@pytest.mark.parametrize('method', ['uiautomator2', 'ADB'])
def test_selected_user_stops_only_other_copies_then_launches_and_verifies(selected, method):
    obj, android = device(selected, method)
    android.installed.remove(14)
    obj.ensure_app_user()
    expected = [('am', 'start-user', '-w', str(selected))]
    expected += [('am', 'force-stop', '--user', str(user), PACKAGE)
                 for user in USERS if user != selected and user != 14]
    expected += [('am', 'start', '--user', str(selected), '-a', 'android.intent.action.MAIN',
                  '-c', 'android.intent.category.LAUNCHER', '-n', android.resolved)]
    assert android.mutations == expected
    assert obj._started_app_user == (selected, PACKAGE)
    count = len(android.commands)
    obj.ensure_app_user()
    assert len(android.commands) == count


def test_explicit_relaunch_rechecks_other_copies_and_stop_targets_selected_user():
    obj, android = device()
    obj.app_start()
    first_mutations = list(android.mutations)
    obj.app_start()
    assert android.mutations == first_mutations * 2
    obj.app_stop()
    assert android.mutations[-1] == ('am', 'force-stop', '--user', '12', PACKAGE)
    assert obj._started_app_user is None


@pytest.mark.parametrize('problem', ['missing_user', 'missing_package', 'missing_launcher', 'query_error'])
def test_invalid_target_never_stops_or_starts_any_app(problem):
    obj, android = device()
    if problem == 'missing_user':
        android.users = (0, 10)
    elif problem == 'missing_package':
        android.installed.remove(12)
    elif problem == 'missing_launcher':
        android.resolved = 'No activity found'
    else:
        android.failures[('pm', 'list', 'packages', '--user', '14', PACKAGE)] = 'Error: denied\nOAS_APP_EXIT:0'
    with pytest.raises(RequestHumanTakeover):
        obj.app_start()
    assert android.mutations == []


def test_profile_start_failure_does_not_stop_other_games():
    obj, android = device()
    android.failures[('am', 'start-user', '-w', '12')] = 'Error: user locked\nOAS_APP_EXIT:1'
    with pytest.raises(RequestHumanTakeover):
        obj.app_start()
    assert android.mutations == [('am', 'start-user', '-w', '12')]


def test_other_copy_stop_failure_prevents_target_launch():
    obj, android = device()
    android.failures[('am', 'force-stop', '--user', '0', PACKAGE)] = 'Security exception: denied\nOAS_APP_EXIT:0'
    with pytest.raises(RequestHumanTakeover):
        obj.app_start()
    assert not any(args[:2] == ('am', 'start') for args in android.mutations)
    assert obj._started_app_user is None


@pytest.mark.parametrize('output', ['Error: denied\nOAS_APP_EXIT:0', 'failed\nOAS_APP_EXIT:1', 'truncated'])
def test_failed_shell_commands_are_not_treated_as_success(output):
    obj, android = device()
    obj.adb_shell = Mock(return_value=output)
    with pytest.raises(RequestHumanTakeover):
        obj._app_user_command(['am', 'force-stop', '--user', '12', PACKAGE])


def test_launch_error_does_not_mark_selection_ready():
    obj, android = device()
    launch = ('am', 'start', '--user', '12', '-a', 'android.intent.action.MAIN',
              '-c', 'android.intent.category.LAUNCHER', '-n', android.resolved)
    android.failures[launch] = 'Error: Activity not started\nOAS_APP_EXIT:0'
    with pytest.raises(RequestHumanTakeover):
        obj.app_start()
    assert obj._started_app_user is None


def test_wrong_user_with_same_package_is_not_accepted_and_wait_is_bounded(monkeypatch):
    obj, android = device()
    android.foreground = f'topResumedActivity=ActivityRecord{{abc u0 {PACKAGE}/.Client t2}}'
    assert not obj.app_is_running()
    clock = iter((0, 0, 31))
    monkeypatch.setattr('module.device.app_user.time', SimpleNamespace(
        monotonic=lambda: next(clock), sleep=Mock()))
    with pytest.raises(RequestHumanTakeover, match='did not reach the foreground'):
        obj.app_start()
    assert obj._started_app_user is None


@pytest.mark.parametrize('foreground,expected', [
    (f'mResumedActivity: ActivityRecord{{abc u12 {PACKAGE}/.Client t2}}', (12, PACKAGE)),
    (f'mResumedActivity=ActivityRecord{{abc u12 {PACKAGE}/.Client t2}}', (12, PACKAGE)),
    (f'topResumedActivity=ActivityRecord{{abc u12 {PACKAGE}/.Client t2}}', (12, PACKAGE)),
    ('topResumedActivity=ActivityRecord{abc u0 app.lawnchair/.Launcher t2}', (0, 'app.lawnchair')),
    ('', None),
    (f'topResumedActivity=ActivityRecord{{abc u12 {PACKAGE}/.Client t2}}\n'
     'topResumedActivity=ActivityRecord{def u0 app.lawnchair/.Launcher t3}', None),
])
def test_foreground_identity_requires_an_unambiguous_resumed_activity(foreground, expected):
    obj, android = device()
    android.foreground = foreground
    assert obj.app_current_user() == expected


def test_auto_package_detection_queries_selected_user_only():
    obj, _ = device()
    obj.adb_shell = Mock(return_value=f'package:{PACKAGE}\npackage:com.example.game')
    # Exercise the undecorated body to avoid ADB transport retries in this unit test.
    method = Connection.list_package
    while hasattr(method, '__wrapped__'):
        method = method.__wrapped__
    assert method(obj) == [PACKAGE, 'com.example.game']
    obj.adb_shell.assert_called_once_with(['pm', 'list', 'packages', '--user', 12])


def test_task_runner_prepares_clone_before_screenshot_or_task_loading():
    tree = ast.parse((ROOT / 'script.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Script')
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    namespace = dict(logger=Mock(), RequestHumanTakeover=RequestHumanTakeover,
                     TaskEnd=type('TaskEnd', (Exception,), {}), GameNotRunningError=type('GameNotRunningError', (Exception,), {}),
                     GameStuckError=type('GameStuckError', (Exception,), {}), GameTooManyClickError=type('GameTooManyClickError', (Exception,), {}),
                     GameBugError=type('GameBugError', (Exception,), {}), GamePageUnknownError=type('GamePageUnknownError', (Exception,), {}),
                     ScriptError=type('ScriptError', (Exception,), {}),
                     I18n=SimpleNamespace(trans_zh_cn=lambda value: value), exit=Mock(side_effect=SystemExit))
    exec(compile(ast.Module(body=[run], type_ignores=[]), '<runner-user-selection>', 'exec'), namespace)
    obj = Mock()
    obj._try_acquire_queue_token.return_value = True
    obj.instance_guard = None
    obj.device.ensure_app_user.side_effect = RequestHumanTakeover('Wrong Android user')
    obj.config_name = 'test'
    with pytest.raises(SystemExit):
        namespace['run'](obj, 'DailyTrifles')
    obj.device.screenshot.assert_not_called()
