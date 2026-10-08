"""Bounded OAS/ADB operations; never terminate a shared emulator service."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from policy import emulator_identity


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.root = Path(settings['root'])
        self.private = Path(settings['private'])
        self.private.mkdir(parents=True, exist_ok=True)
        self.adb = self.root / 'toolkit/Lib/site-packages/adbutils/binaries/adb.exe'
        self.python = self.root / 'toolkit/python.exe'
        self.base = 'http://127.0.0.1:' + str(settings.get('oas_port', 22288))

    def configs(self):
        return {p.stem: json.loads(p.read_text(encoding='utf-8-sig'))
                for p in (self.root / 'config').glob('*.json') if p.stem != 'template'}

    def status(self):
        with urlopen(self.base + '/maintenance/status', timeout=5) as response:
            return json.load(response)['workers']

    def set_value(self, name, task, group, key, value, kind):
        path = '/'.join(quote(p, safe='') for p in (name, task, group, key, 'value'))
        query = urlencode({'types': kind, 'value': str(value)})
        with urlopen(Request(self.base + '/' + path + '?' + query, method='PUT'), timeout=8) as response:
            return json.load(response)

    def control(self, name, action):
        async def run():
            import websockets
            async with websockets.connect(self.base.replace('http:', 'ws:') + '/ws/' + quote(name),
                                          open_timeout=5, close_timeout=2) as ws:
                # Drain initial state/schedule before sending the mutation.
                for _ in range(2):
                    await asyncio.wait_for(ws.recv(), 5)
                await ws.send(action)
                until = time.monotonic() + 15
                while time.monotonic() < until:
                    message = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if message.get('state') == (1 if action == 'start' else 0):
                        break
        # An initial stale RUNNING acknowledgment is never accepted as proof.
        asyncio.run(run())
        until = time.monotonic() + 15
        while time.monotonic() < until:
            if (name in self.status()) == (action == 'start'):
                return
            time.sleep(.5)
        raise RuntimeError('Worker process did not ' + action + ': ' + name)

    def adb_run(self, serial, *args, timeout=8):
        return subprocess.run([str(self.adb), '-s', serial, *args], capture_output=True,
                              timeout=timeout, check=True).stdout

    def capture(self, device, destination):
        import cv2
        import numpy as np
        raw = self.adb_run(device['serial'], 'exec-out', 'screencap', '-p')
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (720, 1280):
            raise RuntimeError('Invalid screenshot size or data')
        Path(destination).write_bytes(raw)
        return image

    def probe(self, device):
        evidence = []
        for attempt in range(3):
            item = {}
            try:
                out = self.adb_run(device['serial'], 'shell', 'echo pong; getprop sys.boot_completed')
                item['shell'] = b'pong' in out and b'1' in out
            except (subprocess.SubprocessError, OSError):
                item['shell'] = False
            try:
                self.capture(device, self.private / ('probe-' + device['serial'].split(':')[-1] + '.png'))
                item['adb_capture'] = True
            except (subprocess.SubprocessError, OSError, RuntimeError):
                item['adb_capture'] = False
            evidence.append(item)
            if all(item.values()):
                return True, evidence
            if attempt == 0:
                subprocess.run([str(self.adb), 'connect', device['serial']], capture_output=True, timeout=8)
            if attempt < 2:
                time.sleep(5)
        return False, evidence

    def capture_configured(self, device):
        if device['screenshot_method'] == 'adb':
            self.capture(device, self.private / 'configured-adb.png')
            return
        if device['screenshot_method'] != 'nemu_ipc':
            raise RuntimeError('Configured screenshot method needs an explicit probe adapter')
        version, index = emulator_identity(device)
        folder = str(Path(device['emulatorinfo_path']).parent.parent)
        subprocess.run([str(self.python), str(Path(__file__).resolve()), '--capture-nemu',
                        str(self.root), folder, str(index), str(self.private / ('nemu-' + str(index) + '.png'))],
                       cwd=self.root, capture_output=True, timeout=15, check=True)

    def dismiss_known_update(self, device):
        """Only click the exact visually approved native engine-update dialog."""
        import cv2
        template_path = self.private / 'engine-update-dialog.png'
        if not template_path.exists():
            return False
        image = self.capture(device, self.private / 'before-dialog.png')
        template = cv2.imread(str(template_path))
        region = image[230:489, 415:865]
        if template is None or template.shape != region.shape:
            return False
        score = float(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)[0, 0])
        if score < .985:
            return False
        self.adb_run(device['serial'], 'shell', 'input', 'tap', '530', '440')
        time.sleep(1)
        after = self.capture(device, self.private / 'after-dialog.png')[230:489, 415:865]
        if float(cv2.matchTemplate(after, template, cv2.TM_CCOEFF_NORMED)[0, 0]) >= .985:
            raise RuntimeError('Native update dialog did not close')
        return True

    def restart_emulator(self, device):
        """Run only after the caller excludes all active profiles on this VM."""
        import psutil
        version, index = emulator_identity(device)
        manager = Path(device['emulatorinfo_path']).parent / 'MuMuManager.exe'
        expected_vm = 'MuMuPlayer-' + version + '.0-' + str(index)
        expected_exe = (manager.parent.parent / 'nx_device' / (version + '.0') / 'shell/MuMuNxDevice.exe')
        owned = []
        for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
            try:
                if process.info['exe'] and os.path.normcase(process.info['exe']) == os.path.normcase(str(expected_exe)):
                    args = process.info['cmdline'] or []
                    if '--vm' in args and args[args.index('--vm') + 1] == expected_vm:
                        owned.append(process)
            except (psutil.Error, IndexError):
                continue
        try:
            subprocess.run([str(manager), 'control', '-v', str(index), '--version', version, 'shutdown'],
                           timeout=30, capture_output=True)
        except subprocess.TimeoutExpired:
            pass
        _, alive = psutil.wait_procs(owned, timeout=15)
        for process in alive:
            # psutil verifies the process creation time before killing a reused PID.
            process.kill()
        _, alive = psutil.wait_procs(alive, timeout=10)
        if alive:
            raise RuntimeError('Target emulator process could not stop')
        subprocess.run([str(manager), 'control', '-v', str(index), '--version', version, 'launch'],
                       timeout=30, capture_output=True, check=True)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                out = self.adb_run(device['serial'], 'shell', 'echo pong; getprop sys.boot_completed')
                if b'pong' in out and b'1' in out:
                    self.capture(device, self.private / 'boot.png')
                    self.capture_configured(device)
                    return
            except (subprocess.SubprocessError, OSError, RuntimeError):
                pass
            time.sleep(5)
        raise RuntimeError('Emulator boot verification timed out')

    def log_tail(self, name, count=120):
        files = list((self.root / 'log').glob('*_' + name + '.txt'))
        if not files:
            return ''
        path = max(files, key=lambda p: p.stat().st_mtime)
        return '\n'.join(path.read_text(encoding='utf-8', errors='replace').splitlines()[-count:])


if __name__ == '__main__' and sys.argv[1] == '--capture-nemu':
    sys.path.insert(0, sys.argv[2])
    import cv2
    from module.device.method.nemu_ipc import NemuIpcImpl
    with NemuIpcImpl(sys.argv[3], int(sys.argv[4])) as capture:
        frame = cv2.flip(cv2.cvtColor(capture.screenshot(), cv2.COLOR_BGRA2BGR), 0)
        if frame.shape[:2] != (720, 1280):
            raise RuntimeError('Invalid configured capture dimensions')
        cv2.imwrite(sys.argv[5], frame)
