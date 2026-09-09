"""HTTP contract and OS-timezone isolation regression tests."""
import asyncio
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi import FastAPI

from module.server import system_timezone as module


class SystemTimezoneTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(module.system_timezone_app, prefix='/home')

    def request(self, method='GET'):
        async def send():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), base_url='http://test'
            ) as client:
                return await client.request(method, '/home/system_timezone')
        return asyncio.run(send())

    def test_success_contract_and_fresh_read(self):
        with patch.object(module, 'read_system_timezone', side_effect=[
            {'timezone': 'Asia/Shanghai'}, {'timezone': 'America/Los_Angeles'}
        ]) as read:
            first, second = self.request(), self.request()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {'timezone': 'Asia/Shanghai'})
        self.assertEqual(second.json(), {'timezone': 'America/Los_Angeles'})
        self.assertEqual(read.call_count, 2)
        self.assertEqual(first.headers['cache-control'], 'no-store')

    def test_all_error_contracts(self):
        for code in module.MESSAGES:
            with self.subTest(code=code), patch.object(module, 'read_system_timezone', return_value={'code': code}):
                response = self.request()
                self.assertEqual(response.status_code, 501 if code == module.UNSUPPORTED else 500)
                self.assertEqual(response.json(), {'code': code, 'message': module.MESSAGES[code]})
                self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_mutation_methods_rejected(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                self.assertEqual(self.request(method).status_code, 405)

    def test_openapi_has_no_parameters_and_documents_responses(self):
        op = self.app.openapi()['paths']['/home/system_timezone']['get']
        self.assertFalse(op.get('parameters'))
        self.assertFalse(op.get('requestBody'))
        self.assertTrue({'200', '500', '501'} <= set(op['responses']))

    def test_probe_excludes_tz_without_mutating_parent(self):
        with patch.dict(os.environ, {'TZ': 'America/New_York'}), \
                patch.object(module.subprocess, 'run', return_value=Mock(stdout='{"timezone":"Asia/Shanghai"}')) as run:
            self.assertEqual(module.read_system_timezone(), {'timezone': 'Asia/Shanghai'})
            self.assertNotIn('TZ', run.call_args.kwargs['env'])
            self.assertEqual(os.environ['TZ'], 'America/New_York')
            self.assertEqual(run.call_args.kwargs['timeout'], 5)

    def test_windows_pythonw_uses_matching_console_runtime(self):
        with patch.object(sys, 'platform', 'win32'), \
                patch.object(sys, 'executable', '/runtime/pythonw.exe'), \
                patch.object(subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                patch.object(subprocess, 'run', return_value=Mock(stdout='{"timezone":"Asia/Shanghai"}')) as run:
            module.read_system_timezone()
            self.assertTrue(run.call_args.args[0][0].endswith('python.exe'))
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)

    def test_unsupported_platform_does_not_launch_probe(self):
        with patch.object(sys, 'platform', 'unknown'), patch.object(subprocess, 'run') as run:
            self.assertEqual(module.read_system_timezone(), {'code': module.UNSUPPORTED})
            run.assert_not_called()

    def test_timeout_launch_failure_and_malformed_output_are_sanitized(self):
        for error in (OSError('private path'), subprocess.TimeoutExpired('private command', 5),
                      subprocess.CalledProcessError(1, 'private command')):
            with self.subTest(error=error), patch.object(subprocess, 'run', side_effect=error):
                self.assertEqual(module.read_system_timezone(), {'code': module.READ_FAILED})
        for output in ('not json', '[]', '{}', '{"timezone":null}', '{"code":"secret"}'):
            with self.subTest(output=output), patch.object(subprocess, 'run', return_value=Mock(stdout=output)):
                self.assertEqual(module.read_system_timezone(), {'code': module.READ_FAILED})

    def test_probe_mapping_failure_is_preserved(self):
        with patch.object(subprocess, 'run', return_value=Mock(stdout=json.dumps({'code': module.MAPPING_FAILED}))):
            self.assertEqual(module.read_system_timezone(), {'code': module.MAPPING_FAILED})

    def test_real_system_timezone_ignores_process_override(self):
        baseline = module.read_system_timezone()
        self.assertIn('timezone', baseline, baseline)
        with patch.dict(os.environ, {'TZ': 'Pacific/Kiritimati'}):
            self.assertEqual(module.read_system_timezone(), baseline)


if __name__ == '__main__':
    unittest.main()
