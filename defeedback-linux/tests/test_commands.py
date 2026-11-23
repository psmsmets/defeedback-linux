"""Exercise dispatch, Git updates, and integration installation without audio hardware."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

BUNDLE = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


cli = module('cli', BUNDLE / 'lib/cli.py')
updater = module('updater', BUNDLE / 'lib/update-defeedback.py')
launcher = module('launcher', BUNDLE / 'lib/reaper-launch.py')


class Commands(unittest.TestCase):
    def test_dispatch(self):
        for args, suffix in [([], 'reaper-launch.py'), (['--device', 'cq'], 'reaper-launch.py'),
                             (['license-gui'], 'open-license-gui.sh'),
                             (['check', 'avantis', '--launch'], 'check-audio.sh'),
                             (['diagnose', '--usb-card', 'SQ'], 'diagnose.sh'),
                             (['aes67', 'install'], 'install-aes67.sh'),
                             (['aes67', 'setup', '--quantum', '96'], 'setup-aes67.sh'),
                             (['ini', '--device', 'cq'], 'reaper-launch.py')]:
            with self.subTest(args=args), patch.object(cli, 'execute') as execute:
                self.assertEqual(cli.main(args), 0)
                command = execute.call_args.args[0]
                self.assertTrue(command[1].endswith(suffix))
                if args and args[0] == 'ini':
                    self.assertEqual(command[2:], ['--print-ini', '--device', 'cq'])
                if args and args[0] == 'check':
                    self.assertEqual(command[2:], ['avantis', '--launch'])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(['unknown'])

    def test_generated_ini_without_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'device.ini'
            launcher.prepare_ini(target, Path(directory) / 'absent.ini',
                                 dict(id='CQ12T', inputs=12, outputs=12))
            self.assertIn('alsa_indev=hw:CQ12T', target.read_text())
            self.assertIn('linux_audio_bsize=64', target.read_text())

    def test_installation_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)):
            home = Path(directory)
            app = home / '.local/share/defeedback'
            backup = home / 'backup'
            old = home / '.local/bin/defeedback'
            old.parent.mkdir(parents=True)
            old.symlink_to(app / 'bin/defeedback')
            desktop = home / 'Desktop/defeedback-reaper.desktop'
            desktop.parent.mkdir()
            desktop.write_text('[Desktop Entry]\nName=REAPER\nExec=reaper\n')
            with patch.object(updater.shutil, 'which', return_value=None):
                updater.install(None, home / 'REAPER', app, backup)
            self.assertFalse(old.is_symlink())
            self.assertIn('Name=De-Feedback Linux — unofficial integration', desktop.read_text())
            self.assertIn('Exec=reaper', desktop.read_text())
            old.symlink_to(home / 'unrelated-command')
            updater.install(None, home / 'REAPER', app, home / 'backup-unrelated')
            self.assertTrue(old.is_symlink())
            for source, target in updater.RESOURCES.items():
                self.assertEqual((app / target).read_bytes(), (BUNDLE / source).read_bytes())
            self.assertTrue((home / '.local/bin/defeedback-linux').is_symlink())
            result = subprocess.run([str(home / '.local/bin/defeedback-linux'), 'ini', '--device',
                                     'hw:EVO8', '--inputs', '4', '--outputs', '4'],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('alsa_indev=hw:EVO8', result.stdout)
            original = (app / 'bin/defeedback-linux').read_bytes()
            copy = updater.atomic_copy
            calls = 0

            def fail_once(source, target):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError('simulated install failure')
                copy(source, target)

            with patch.object(updater, 'atomic_copy', side_effect=fail_once), self.assertRaises(OSError):
                updater.install(None, home / 'REAPER', app, home / 'backup2')
            self.assertEqual((app / 'bin/defeedback-linux').read_bytes(), original)


class GitUpdates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.remote = self.base / 'upstream'
        self.remote.mkdir()
        self.git(self.remote, 'init', '-b', 'main')
        self.git(self.remote, 'config', 'user.name', 'Test')
        self.git(self.remote, 'config', 'user.email', 'test@example.invalid')
        script = self.remote / 'defeedback-linux/update-defeedback.sh'
        script.parent.mkdir()
        script.write_text('#!/bin/sh\nprintf "%s" "$*" > "$TEST_MARKER"\n')
        self.commit('initial')
        self.home = self.base / 'home'
        self.home.mkdir()
        self.marker = self.base / 'applied'
        self.checkout = self.home / '.local/share/defeedback/source'
        self.real_run = subprocess.run
        self.patches = [patch.object(Path, 'home', return_value=self.home),
                        patch.dict(os.environ, {'HOME': str(self.home),
                                                'XDG_STATE_HOME': str(self.home / 'state'),
                                                'TEST_MARKER': str(self.marker)}),
                        patch.object(cli.platform, 'system', return_value='Linux'),
                        patch.object(cli.os, 'geteuid', return_value=1000),
                        patch.object(cli.subprocess, 'run', side_effect=self.run_command)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def run_command(self, command, **kwargs):
        if command[0] == 'pgrep':
            return subprocess.CompletedProcess(command, 1)
        return self.real_run(command, **kwargs)

    @staticmethod
    def git(directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, message):
        self.git(self.remote, 'add', '.')
        self.git(self.remote, 'commit', '-m', message)

    def update(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.update(['--repo', str(self.remote), *args])

    def test_check_fast_forward_and_reaper_option(self):
        self.update('--check')
        self.assertFalse(self.marker.exists())
        old = self.git(self.checkout, 'rev-parse', 'HEAD')
        (self.remote / 'revision').write_text('two')
        self.commit('second')
        self.update('--check')
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD'), old)
        self.update()
        self.assertEqual(self.marker.read_text(), '--integration-only')
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD'), self.git(self.remote, 'rev-parse', 'HEAD'))
        self.update('--reaper')
        self.assertEqual(self.marker.read_text(), '')

    def test_dirty_checkout_and_divergence(self):
        self.update('--check')
        (self.checkout / 'local-file').write_text('keep')
        with self.assertRaisesRegex(RuntimeError, 'local changes'):
            self.update()
        self.assertFalse(self.marker.exists())
        (self.checkout / 'local-file').unlink()
        self.git(self.checkout, 'config', 'user.name', 'Test')
        self.git(self.checkout, 'config', 'user.email', 'test@example.invalid')
        (self.checkout / 'local-file').write_text('committed')
        self.git(self.checkout, 'add', '.')
        self.git(self.checkout, 'commit', '-m', 'local commit')
        with self.assertRaisesRegex(RuntimeError, 'fast-forward'):
            self.update()
        self.assertEqual((self.checkout / 'local-file').read_text(), 'committed')
        self.assertFalse(self.marker.exists())

    def test_saved_source_and_reaper_running(self):
        self.update('--check')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.update(['--check']), 0)
        with patch.object(cli.subprocess, 'run', return_value=subprocess.CompletedProcess(['pgrep'], 0)):
            with self.assertRaisesRegex(RuntimeError, 'Close REAPER'):
                self.update()
        self.assertFalse(self.marker.exists())

    def test_missing_audio_skips_without_launch(self):
        with patch.object(launcher, 'detect_cards', return_value=[]), \
                patch.object(launcher.time, 'monotonic', side_effect=[0, 11]), \
                patch.object(launcher.subprocess, 'Popen') as launch, \
                patch('sys.argv', ['reaper']):
            self.assertEqual(launcher.main(), 0)
            launch.assert_not_called()

    def test_fetch_failure_does_not_activate(self):
        self.update('--check')
        self.remote.rename(self.base / 'offline')
        with self.assertRaises(RuntimeError):
            self.update()
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
