"""Regression coverage for versioned MuMu names and safe start/stop commands."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from module.device.platform2.emulator_base import EmulatorInstanceBase

ROOT = Path(__file__).resolve().parents[1]


class MuMuInstanceTests(unittest.TestCase):
    def test_versioned_names(self):
        for prefix in ('MuMuPlayer', 'MuMuPlayerGlobal', 'YXArkNights'):
            for version in ('12.0', '15.0'):
                for index in (0, 1, 2, 3, 12):
                    name = f'{prefix}-{version}-{index}'
                    with self.subTest(name=name):
                        instance = EmulatorInstanceBase('', name, '')
                        self.assertEqual(instance.MuMuPlayer12_id, index)

    def test_invalid_names(self):
        for name in ('MuMuPlayer-15x0-0', 'MuMuPlayer-15.0-',
                     'MuMuPlayer-15.0--1', 'MuMuPlayer-15.0-0-extra',
                     'prefixMuMuPlayer-15.0-0', 'Other-15.0-0'):
            with self.subTest(name=name):
                self.assertIsNone(EmulatorInstanceBase('', name, '').MuMuPlayer12_id)

    def test_commands_and_invalid_id_guard(self):
        # Load only command builders so these tests also run outside Windows.
        tree = ast.parse((ROOT / 'module/device/platform2/platform_windows.py').read_text(encoding='utf-8'))
        methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                   and n.name in ('_emulator_start', '_emulator_stop')]
        emulator = SimpleNamespace(MuMuPlayer='old', MuMuPlayerX='x',
                                  MuMuPlayer12='mumu', single_to_console=lambda _: 'manager.exe')
        namespace = {'Emulator': emulator, 'EmulatorUnknown': ValueError, 'EmulatorInstance': object}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(ROOT), 'exec'), namespace)

        class Instance:
            emulator = SimpleNamespace(path='player.exe')
            name = 'MuMuPlayer-15.0-0'
            MuMuPlayer12_id = 0

            def __eq__(self, other):
                return other == 'mumu'

        device = SimpleNamespace(emulator_window_minimize=False, run_background_only=False)
        owner = SimpleNamespace(config=SimpleNamespace(script=SimpleNamespace(device=device)), execute=Mock())
        for method, command in (('_emulator_start', '"player.exe" -v 0'),
                                ('_emulator_stop', '"manager.exe" api -v 0 shutdown_player')):
            with self.subTest(method=method):
                instance = Instance()
                owner.execute.reset_mock()
                namespace[method](owner, instance)
                self.assertEqual(owner.execute.call_args.args[0], command)
                owner.execute.reset_mock()
                instance.MuMuPlayer12_id = None
                with self.assertRaisesRegex(ValueError, 'Cannot get MuMu instance index'):
                    namespace[method](owner, instance)
                owner.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
