"""Verify bounded, audio-free logging and manual AES67 supervision."""
import contextlib
import io
import json
import os
import select
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import session_log as logs
import log_commands
import aes67_runtime
import cli


class Logging(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.patch = patch.dict(os.environ, {'XDG_STATE_HOME': str(self.base / 'state'),
                                             'XDG_CONFIG_HOME': str(self.base / 'config'),
                                             'DEFEEDBACK_DEBUG': '0'})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_rotation_and_active_session_retention(self):
        with logs.Session('active', max_bytes=1024) as active:
            for index in range(30):
                active.logger.info('%s %s', index, 'x' * 200)
            self.assertLessEqual(len(list(active.path.parent.glob(active.path.name + '*'))), 4)
            for path in active.path.parent.glob(active.path.name + '.[0-9]*'):
                self.assertLessEqual(path.stat().st_size, 1024)
            for index in range(12):
                with logs.Session('closed'):
                    pass
            self.assertTrue(active.path.exists(), 'Active session must not be pruned')
        logs.prune_sessions(logs.log_dir())
        self.assertLessEqual(len(list(logs.log_dir().glob('session-*.log'))), logs.KEEP_SESSIONS)

    def test_process_output_and_nonzero_exit(self):
        with logs.Session('process') as session, contextlib.redirect_stdout(io.StringIO()) as console:
            result = logs.run_logged([sys.executable, '-c',
                'import sys; print("stdout test", flush=True); print("stderr test", file=sys.stderr); sys.exit(7)'], session)
        text = session.path.read_text()
        self.assertEqual(result, 7)
        self.assertIn('stdout test', text)
        self.assertIn('stderr test', text)
        self.assertIn('PROCESS exit status=7', text)
        self.assertIn('SESSION end', text)
        self.assertIn('stdout test', console.getvalue())

    def test_logs_inventory_tail_and_journal(self):
        with logs.Session('reader') as session:
            session.logger.info('unique event')
        legacy = logs.state_dir() / 'old.RPP.log'
        legacy.write_text('old template event\n')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(log_commands.show_logs(['--list']), 0)
        self.assertIn(session.path.name, output.getvalue())
        self.assertIn(legacy.name, output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            log_commands.show_logs(['--file', session.path.name, '--lines', '2'])
        self.assertIn('unique event', output.getvalue())
        self.assertNotIn('SESSION start', output.getvalue())
        with patch.object(log_commands.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'service event', '')) as run, contextlib.redirect_stdout(io.StringIO()) as output:
            log_commands.show_logs(['--all', '--journal'])
            self.assertIn('service event', output.getvalue())
            self.assertEqual(run.call_args.args[0][0], 'journalctl')
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            log_commands.show_logs(['--file', '../../outside'])

    def test_follow_rotation(self):
        with logs.Session('follow') as session:
            session.logger.info('initial')
        calls = [0]
        def rotate(_):
            calls[0] += 1
            if calls[0] == 1:
                session.path.rename(str(session.path) + '.1')
                session.path.write_text('rotated event\n')
            else:
                raise KeyboardInterrupt
        with patch.object(log_commands.time, 'sleep', side_effect=rotate), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):
                log_commands.show_logs(['--file', session.path.name, '--follow'])
        self.assertIn('rotated event', output.getvalue())

    def test_stop_signal_reaches_child(self):
        module_dir = str(Path(__file__).resolve().parents[1] / 'lib')
        child = 'import signal,time,sys; signal.signal(signal.SIGTERM, lambda *args: sys.exit(0)); print("READY", flush=True); time.sleep(20)'
        supervisor = ('import sys; sys.path.insert(0, ' + repr(module_dir) + '); '
                      'from session_log import Session,run_logged\n'
                      'with Session("signal") as session:\n'
                      '    status = run_logged([sys.executable,"-c",' + repr(child) + '], session)\n'
                      'sys.exit(status)\n')
        process = subprocess.Popen([sys.executable, '-c', supervisor], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'Child did not become ready')
            self.assertEqual(process.stdout.readline().strip(), 'READY')
            process.send_signal(signal.SIGTERM)
            _, error = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, error)
            self.assertTrue(any('PROCESS exit status=0' in path.read_text() for path in logs.log_dir().glob('session-*.log')))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_debug_snapshot_is_read_only_and_ini_stdout_clean(self):
        with logs.Session('debug', debug=True) as session, patch.object(logs.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'snapshot', '')) as run:
            logs.debug_snapshot(session)
            self.assertEqual([call.args[0][0] for call in run.call_args_list], ['ip', 'pw-metadata'])
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'defeedback-linux'),
                                 '--debug', 'ini', '--device', 'hw:EVO8', '--inputs', '4', '--outputs', '4'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('[reaper]'))
        self.assertNotIn('Session log:', result.stderr)

    def test_aes67_requires_lock_and_builds_configured_commands(self):
        config = self.base / 'config/defeedback/pipewire-aes67.conf'
        config.parent.mkdir(parents=True)
        config.write_text('local.ifname = "enp2s0"\n')
        with patch.object(aes67_runtime, 'run_logged', return_value=0) as run:
            self.assertEqual(aes67_runtime.start('ptp', []), 0)
            self.assertEqual(run.call_args.args[0][:4], ['sudo', 'ptp4l', '-i', 'enp2s0'])
        with patch.object(aes67_runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'portState LISTENING', '')):
            with self.assertRaisesRegex(RuntimeError, 'SLAVE'):
                aes67_runtime.start('audio', [])
        with patch.object(aes67_runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'portState SLAVE', '')), patch.object(aes67_runtime, 'run_logged', return_value=0) as run:
            self.assertEqual(aes67_runtime.start('audio', []), 0)
            self.assertEqual(run.call_args.args[0], ['pipewire', '-c', str(config)])
        with contextlib.redirect_stdout(io.StringIO()):
            log_commands.show_logs(['--all'])

    def test_health_reports_transitions_without_recording(self):
        config = self.base / 'config/defeedback/pipewire-aes67.conf'
        config.parent.mkdir(parents=True)
        config.write_text('local.ifname = "enp2s0"\n')
        nodes = [{'info': {'props': {'device.api': 'aes67', 'media.class': 'Audio/Source'}}},
                 {'info': {'props': {'node.name': 'defeedback-aes67-return'}}}]
        def command(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, 'portState SLAVE' if args[0] == 'pmc' else json.dumps(nodes), '')
        with logs.Session('health') as session, patch.object(logs.subprocess, 'run', side_effect=command) as run:
            check = logs.audio_health(aes67=True)
            check(session.logger)
            check(session.logger)
            text = session.path.read_text()
            self.assertEqual(text.count('ptp-port-state=SLAVE'), 1)
            self.assertEqual(text.count('aes67-return=present'), 1)
            self.assertTrue(all(call.args[0][0] in ('pmc', 'pw-dump') for call in run.call_args_list))
