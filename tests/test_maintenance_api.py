"""Exercise the real maintenance status handler and explicit no-worker startup."""
import argparse
import ast
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / 'module/server/app.py').read_text(encoding='utf-8'))


def load(name, context):
    node = next(n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<app handler>', 'exec'), context)
    return context[name]


class MaintenanceApiTests(unittest.TestCase):
    def test_loopback_status_reports_only_actual_live_workers(self):
        live = Mock(pid=42); live.is_alive.return_value = True
        dead = Mock(pid=99); dead.is_alive.return_value = False
        handler = load('maintenance_status', dict(Request=object, os=os, JSONResponse=JSONResponse,
            mm=SimpleNamespace(script_process={'M1': SimpleNamespace(_process=live),
                'M2': SimpleNamespace(_process=dead), 'M3': SimpleNamespace(_process=None)})))
        result = asyncio.run(handler(SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))))
        self.assertEqual(result, {'version': 1, 'backend_pid': os.getpid(), 'workers': {'M1': 42}})
        self.assertEqual(asyncio.run(handler(SimpleNamespace(client=SimpleNamespace(host='192.0.2.1')))).status_code, 403)

    def test_explicit_no_worker_start_overrides_deploy_run(self):
        app = SimpleNamespace(state=SimpleNamespace())
        factory = load('fastapi_app', dict(argparse=argparse, app=app,
            State=SimpleNamespace(deploy_config=SimpleNamespace(Run='M1,M2'))))
        with patch('sys.argv', ['server.py', '--run-none']):
            factory()
        self.assertEqual(app.state.script_instances, [])
        with patch('sys.argv', ['server.py', '--run', 'M3']):
            factory()
        self.assertEqual(app.state.script_instances, ['M3'])
