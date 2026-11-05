"""Idle/relaunch handoff must close the old native socket and discard queued input."""
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from module.device.device import Device
from module.device.app_control import AppControl
from module.device.method.minitouch import Minitouch


class NativeTouchHandoffTests(unittest.TestCase):
    def test_release_sends_eof_and_discards_cached_commands(self):
        device = object.__new__(Minitouch)
        device.config = SimpleNamespace(DEVICE_OVER_HTTP=False)
        client, peer = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(peer.close)
        peer.settimeout(.5)
        device._minitouch_client = client
        device._minitouch_port = 20001
        device.minitouch_builder = object()
        device.minitouch_release()
        self.assertEqual(peer.recv(1), b'')
        self.assertEqual(client.fileno(), -1)
        self.assertNotIn('minitouch_builder', device.__dict__)
        self.assertNotIn('_minitouch_client', device.__dict__)
        self.assertEqual(device._minitouch_port, 0)
        device.minitouch_release()

    def test_unused_native_transport_is_not_initialized_by_release(self):
        device = object.__new__(Minitouch)
        device.config = SimpleNamespace(DEVICE_OVER_HTTP=False)
        with patch.object(Minitouch, 'minitouch_init', side_effect=AssertionError):
            device.minitouch_release()
        self.assertNotIn('minitouch_builder', device.__dict__)

    def test_http_transport_retains_its_own_lifecycle(self):
        device = object.__new__(Minitouch)
        device.config = SimpleNamespace(DEVICE_OVER_HTTP=True)
        client = Mock()
        device._minitouch_client = client
        builder = device.minitouch_builder = object()
        device.minitouch_release()
        client.close.assert_not_called()
        self.assertIs(device.minitouch_builder, builder)

    def test_relaunch_releases_native_control_before_starting_app(self):
        device = object.__new__(Device)
        device.config = SimpleNamespace(script=SimpleNamespace(
            desktop=SimpleNamespace(enable=False), error=SimpleNamespace(handle_error=True)))
        order = []
        device.minitouch_release = lambda: order.append('release')
        device.stuck_record_clear = Mock()
        device.click_record_clear = Mock()
        with patch.object(AppControl, 'app_start', side_effect=lambda: order.append('start')):
            device.app_start()
        self.assertEqual(order, ['release', 'start'])

    def test_idle_cleanup_releases_native_control_and_configured_capture(self):
        device = object.__new__(Device)
        device.config = SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(
            screenshot_method='nemu_ipc')), Emulator_ScreenshotMethod='nemu_ipc')
        device.minitouch_release = Mock()
        device.nemu_ipc_release = Mock()
        device.release_during_wait()
        device.minitouch_release.assert_called_once_with()
        device.nemu_ipc_release.assert_called_once_with()
