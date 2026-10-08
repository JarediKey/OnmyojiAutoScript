"""Terminal worker failures must reach both notification and WebSocket state channels."""
import ast
from enum import IntEnum
import multiprocessing
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
WORKER = ast.parse((ROOT / 'module/server/script_process.py').read_text(encoding='utf-8'))
NOTIFY = ast.parse((ROOT / 'module/notify/notify.py').read_text(encoding='utf-8'))


class State(IntEnum):
    INACTIVE = 0
    RUNNING = 1
    WARNING = 2


class WorkerTerminalTests(unittest.TestCase):
    def setUp(self):
        self.queue = Mock()
        self.pipe = Mock()
        self.log = Mock()
        self.notifier_instance = Mock()
        self.read = Mock(return_value={'script': {'error': {
            'notify_enable': True, 'notify_config': 'provider: custom\ndata: {}'}}})
        class Notifier:
            terminal_sent = False
        self.Notifier = Notifier
        Notifier.__new__ = staticmethod(lambda cls, *a, **kw: self.notifier_instance)
        self.script = Mock()
        self.constructor = Mock(return_value=self.script)
        self.modules = {
            'script': SimpleNamespace(Script=self.constructor),
            'module.notify.notify': SimpleNamespace(Notifier=Notifier),
            'module.config.utils': SimpleNamespace(read_file=self.read, filepath_config=lambda n:'config/'+n+'.json'),
            'module.logger': SimpleNamespace(set_file_logger=Mock(), set_func_logger=Mock())}
        context = dict(multiprocessing=multiprocessing, signal=signal, sys=sys,
                       logger=self.log, ScriptState=State)
        nodes = [n for n in WORKER.body if isinstance(n,ast.FunctionDef)
                 and n.name in ['report_terminal_failure','func']]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<real worker boundary>','exec'),context)
        self.run = context['func']

    def invoke(self):
        with patch.dict(sys.modules,self.modules),patch('signal.signal'):
            self.run('M3',self.queue,self.pipe)

    def test_scheduler_config_save_failure_notifies_and_publishes_warning(self):
        self.script.loop.side_effect = PermissionError('[WinError 5] Access is denied')
        with self.assertRaises(PermissionError):self.invoke()
        self.queue.put.assert_called_once_with({'state':State.WARNING})
        self.read.assert_called_once_with('config/M3.json')
        message=self.notifier_instance.push_terminal.call_args.kwargs['content']
        self.assertIn('<M3> Exception occured: PermissionError',message)

    def test_early_constructor_failure_uses_raw_config_not_a_writing_model(self):
        self.constructor.side_effect=PermissionError('config initialization failed')
        with self.assertRaises(PermissionError):self.invoke()
        self.queue.put.assert_called_once_with({'state':State.WARNING})
        self.notifier_instance.push_terminal.assert_called_once()

    def test_failed_notification_still_delivers_warning_and_preserves_original_error(self):
        self.script.loop.side_effect=PermissionError('save failed')
        self.notifier_instance.push_terminal.side_effect=RuntimeError('provider unavailable')
        with self.assertRaisesRegex(PermissionError,'save failed'):self.invoke()
        self.queue.put.assert_called_once_with({'state':State.WARNING})

    def test_already_delivered_terminal_notification_is_not_duplicated(self):
        def exit_after_notify():
            self.Notifier.terminal_sent=True
            raise SystemExit(1)
        self.script.loop.side_effect=exit_after_notify
        with self.assertRaises(SystemExit):self.invoke()
        self.queue.put.assert_called_once_with({'state':State.WARNING})
        self.read.assert_not_called()
        self.notifier_instance.push_terminal.assert_not_called()

    def test_nonzero_exit_without_notification_is_reported(self):
        self.script.loop.side_effect=SystemExit(1)
        with self.assertRaises(SystemExit):self.invoke()
        self.notifier_instance.push_terminal.assert_called_once()

    def test_normal_stop_and_normal_return_do_not_alert(self):
        for result in [None,SystemExit(0),SystemExit(None)]:
            self.queue.reset_mock();self.notifier_instance.reset_mock()
            self.script.loop.side_effect=result
            self.invoke()
            self.queue.put.assert_not_called()
            self.notifier_instance.push_terminal.assert_not_called()

    def test_manual_signal_stop_is_not_classified_as_failure(self):
        callbacks={}
        def register(kind,handler):callbacks[kind]=handler
        self.script.loop.side_effect=lambda:callbacks[signal.SIGTERM](signal.SIGTERM,None)
        with patch.dict(sys.modules,self.modules),patch('signal.signal',side_effect=register):
            self.run('M3',self.queue,self.pipe)
        self.queue.put.assert_not_called()
        self.notifier_instance.push_terminal.assert_not_called()
        self.pipe.close.assert_called_once()


class TerminalMarkerTests(unittest.TestCase):
    def test_only_successful_terminal_delivery_sets_process_marker(self):
        node=next(n for n in NOTIFY.body if isinstance(n,ast.ClassDef) and n.name=='Notifier')
        context={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<real notifier>','exec'),context)
        notifier_type=context['Notifier']
        instance=notifier_type.__new__(notifier_type)
        instance.push=Mock(return_value=False)
        self.assertFalse(instance.push_terminal(title='fatal',content='error'))
        self.assertFalse(notifier_type.terminal_sent)
        instance.push.return_value=True
        self.assertTrue(instance.push_terminal(title='fatal',content='error'))
        self.assertTrue(notifier_type.terminal_sent)


class WarningBroadcastTests(unittest.TestCase):
    def test_terminal_queue_message_changes_cached_state_and_is_broadcast(self):
        import asyncio
        import queue
        node=next(n for n in WORKER.body if isinstance(n,ast.ClassDef) and n.name=='ScriptProcess')
        method=next(n for n in node.body if isinstance(n,ast.AsyncFunctionDef)
                    and n.name=='coroutine_broadcast_state')
        async def sleep(_):return
        context=dict(ScriptState=State,sleep=sleep,QueueEmpty=queue.Empty,
                     CancelledError=asyncio.CancelledError,logger=Mock())
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<real state broadcaster>','exec'),context)
        state_queue=Mock();state_queue.empty.return_value=False
        state_queue.get_nowait.return_value={'state':State.WARNING}
        script=SimpleNamespace(state=State.RUNNING,state_queue=state_queue,config_name='M3',
                               broadcast_state=AsyncMock(side_effect=asyncio.CancelledError))
        asyncio.run(context['coroutine_broadcast_state'](script))
        self.assertEqual(script.state,State.WARNING)
        script.broadcast_state.assert_awaited_once_with({'state':State.WARNING})


if __name__=='__main__':unittest.main()
