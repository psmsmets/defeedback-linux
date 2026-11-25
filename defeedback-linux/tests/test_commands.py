"""Exercise dispatch, Git updates, and integration installation without audio hardware."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

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
    def test_version_from_source_without_starting_audio_or_creating_logs(self):
        expected = 'defeedback-linux ' + (BUNDLE / 'VERSION').read_text().strip() + '\n'
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            environment = dict(os.environ, HOME=directory, XDG_STATE_HOME=str(home / 'state'))
            for arguments in (['--version'], ['--debug', '--version']):
                result = subprocess.run([sys.executable, str(BUNDLE / 'defeedback-linux'), *arguments],
                                        cwd=directory, env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, '')
            self.assertFalse((home / 'state').exists())
            self.assertFalse((home / '.local/share/defeedback').exists())

    def test_manual_aes67_check_launches_managed_device_only_with_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binaries = home / 'bin'
            binaries.mkdir()
            for name in ('ip', 'wpctl', 'pw-link', 'pw-jack'):
                path = binaries / name
                path.write_text('#!/bin/sh\nexit 0\n')
                path.chmod(0o755)
            dump = binaries / 'pw-dump'
            dump.write_text('#!/bin/sh\ncat "$HOME/nodes.json"\n')
            dump.chmod(0o755)
            reaper = home / '.local/share/defeedback/bin/reaper'
            reaper.parent.mkdir(parents=True)
            reaper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/launch-args"\n')
            reaper.chmod(0o755)
            environment = dict(os.environ, HOME=str(home), PATH=str(binaries) + os.pathsep + os.environ['PATH'])
            for nodes, expected in [('[]', False),
                    ('[{"info":{"props":{"node.name":"defeedback-aes67-return"}}}]', False),
                    ('[{"info":{"props":{"node.name":"defeedback-aes67-return"}}},'
                     '{"info":{"props":{"device.api":"aes67","media.class":"Audio/Source"}}}]', True)]:
                (home / 'nodes.json').write_text(nodes)
                result = subprocess.run(['/bin/bash', str(BUNDLE / 'tools/check-audio.sh'), 'avantis', '--launch'],
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((home / 'launch-args').exists(), expected)
            self.assertEqual((home / 'launch-args').read_text().splitlines(), ['--device', 'aes67'])

    def test_dispatch(self):
        for args, suffix in [([], 'reaper-launch.py'), (['--device', 'cq'], 'reaper-launch.py'),
                             (['vsthost', 'install'], 'install-vsthost.py'),
                             (['vsthost', 'install', '--source', '/path with spaces/package.zip'], 'install-vsthost.py'),
                             (['vsthost', 'start'], 'start-vsthost.sh'),
                             (['vsthost', 'start', '--virtual-desktop'], 'start-vsthost.sh'),
                             (['install', 'vsthost'], 'install-vsthost.py'),
                             (['install', 'vsthost', '--source', '/path with spaces/package.zip'], 'install-vsthost.py'),
                             (['start', 'vsthost'], 'start-vsthost.sh'),
                             (['start', 'vsthost', '--virtual-desktop'], 'start-vsthost.sh'),
                             (['check', 'avantis', '--launch'], 'check-audio.sh'),
                             (['audio', 'check', 'avantis', '--launch'], 'check-audio.sh'),
                             (['diagnose', '--usb-card', 'SQ'], 'diagnose.sh'),
                             (['audio', 'diagnose', '--usb-card', 'SQ'], 'diagnose.sh'),
                             (['aes67', 'install'], 'install-aes67.sh'),
                             (['aes67', 'setup', '--quantum', '96'], 'setup-aes67.sh'),
                             (['appliance', 'setup'], 'setup-appliance.sh'),
                             (['appliance', 'trim', '--apply', '--autoremove'], 'trim-workstation.sh'),
                             (['trim', '--apply', '--autoremove'], 'trim-workstation.sh'),
                             (['audio', 'ini', '--device', 'cq'], 'reaper-launch.py'),
                             (['ini', '--device', 'cq'], 'reaper-launch.py')]:
            with self.subTest(args=args), patch.object(cli, 'execute', return_value=0) as execute:
                self.assertEqual(cli.main(args), 0)
                command = execute.call_args.args[0]
                self.assertTrue(command[1].endswith(suffix))
                if args and args[0] == 'ini':
                    self.assertEqual(command[2:], ['--print-ini', '--device', 'cq'])
                if args and args[0] == 'trim':
                    self.assertEqual(command[2:], ['--apply', '--autoremove'])
                if args and args[0] == 'check':
                    self.assertEqual(command[2:], ['avantis', '--launch'])
                if args and args[0] in ('install', 'start'):
                    self.assertEqual(command[2:], args[2:])
                if args and args[0] in ('vsthost', 'appliance', 'aes67', 'audio'):
                    self.assertEqual(command[2:], (['--print-ini'] if args[:2] == ['audio', 'ini'] else []) + args[2:])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(['unknown'])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(['appliance', 'install'])
        for args in (['open-license-gui'], ['license-gui'], ['install', 'unknown'], ['start', 'unknown']):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                cli.main(args)
        with patch.object(cli, 'execute', return_value=0) as execute, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['appliance', '--help']), 0)
            execute.assert_not_called()

    def test_group_help_does_not_execute_tools_or_create_logs(self):
        for group, actions in [('audio', ('check', 'diagnose', 'ini')),
                               ('vsthost', ('install', 'start')),
                               ('appliance', ('setup', 'trim')),
                               ('aes67', ('install', 'setup', 'ptp', 'ptp-status', 'audio', 'enable', 'disable', 'status'))]:
            with self.subTest(group=group), patch.object(cli, 'execute') as execute, \
                    patch.object(cli, 'Session') as session, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main([group, '--help']), 0)
                self.assertIn('defeedback-linux ' + group, output.getvalue())
                for action in actions:
                    self.assertIn(action, output.getvalue())
                execute.assert_not_called()
                session.assert_not_called()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            cli.main(['--help'])
        commands = output.getvalue().split('Commands:\n')[1].split('\n\n')[0]
        self.assertEqual(len(commands.splitlines()), 7)
        for hidden in ('install', 'start', 'check', 'diagnose', 'ini', 'trim'):
            self.assertNotIn('  ' + hidden + ' ', commands)

    def test_action_help_uses_the_public_path_without_launching_audio(self):
        for group, action in [('audio', 'check'), ('audio', 'diagnose'), ('audio', 'ini'),
                              ('vsthost', 'install'), ('vsthost', 'start'),
                              ('appliance', 'setup'), ('appliance', 'trim'),
                              ('aes67', 'install'), ('aes67', 'setup'), ('aes67', 'enable'),
                              ('aes67', 'disable'), ('aes67', 'status'), ('aes67', 'ptp'),
                              ('aes67', 'ptp-status'), ('aes67', 'audio')]:
            with self.subTest(group=group, action=action), tempfile.TemporaryDirectory() as directory:
                environment = dict(os.environ, HOME=directory, XDG_STATE_HOME=str(Path(directory) / 'state'))
                result = subprocess.run([sys.executable, str(BUNDLE / 'defeedback-linux'), group, action, '--help'],
                                        text=True, capture_output=True, env=environment)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('defeedback-linux ' + group + ' ' + action, result.stdout)
                self.assertFalse((Path(directory) / 'state').exists())
                if (group, action) == ('audio', 'ini'):
                    self.assertNotIn('--raw', result.stdout)

    def test_generated_ini_without_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'device.ini'
            launcher.prepare_ini(target, Path(directory) / 'absent.ini',
                                 dict(id='CQ12T', inputs=12, outputs=12))
            self.assertIn('alsa_indev=hw:CQ12T', target.read_text())
            self.assertIn('linux_audio_bsize=64', target.read_text())

    def test_detect_prints_selection_without_launching(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)), \
                patch.dict(os.environ, {'XDG_STATE_HOME': directory}), \
                patch.object(launcher, 'detect_cards', return_value=[dict(id='EVO8', family='evo8', inputs=4, outputs=4)]), \
                patch.object(launcher.subprocess, 'Popen') as launch, \
                patch('sys.argv', ['reaper', '--detect']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launcher.main(), 0)
            self.assertIn('Selected hw:EVO8 (evo8): 4 mono paths', output.getvalue())
            launch.assert_not_called()

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
            legacy = app / 'bin/vsthost'
            legacy.parent.mkdir(parents=True)
            legacy.write_text('#!/bin/bash\n# Usage: defeedback-linux open-license-gui\n')
            legacy_link = home / '.local/bin/vsthost'
            legacy_link.symlink_to(legacy)
            legacy_helper = app / 'lib/open-license-gui.sh'
            legacy_helper.parent.mkdir()
            legacy_helper.write_text(legacy.read_text())
            shortcut = desktop.parent / 'defeedback-vsthost.desktop'
            shortcut.write_text('[Desktop Entry]\nName=VSTHost (De-Feedback License)\nExec="' + str(legacy) + '"\n')
            unrelated = home / '.local/share/applications/defeedback-vsthost.desktop'
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text('[Desktop Entry]\nName=My VSTHost\nExec=custom-vsthost\n')
            package = app / 'vsthostx64/vsthost.exe'
            package.parent.mkdir()
            package.write_bytes(b'preserve optional package')
            with patch.object(updater.shutil, 'which', return_value=None):
                updater.install(None, home / 'REAPER', app, backup)
            self.assertFalse(shortcut.exists())
            self.assertFalse(legacy.exists())
            self.assertFalse(legacy_link.is_symlink())
            self.assertFalse(legacy_helper.exists())
            self.assertEqual(package.read_bytes(), b'preserve optional package')
            self.assertIn('Exec=custom-vsthost', unrelated.read_text())
            self.assertTrue((backup / 'legacy-vsthost/desktop/defeedback-vsthost.desktop').exists())
            self.assertTrue((backup / 'legacy-vsthost/bin/vsthost').exists())
            metadata = json.loads((app / 'installation.json').read_text())
            self.assertEqual(metadata['version'], (BUNDLE / 'VERSION').read_text().strip())
            self.assertIsNone(metadata['revision'])
            executable = home / '.local/bin/defeedback-linux'
            for metadata_text, suffix in [((app / 'installation.json').read_text(), ''),
                                          (json.dumps({'revision': 'abcdef1234567890'}), ' (revision abcdef123456)'),
                                          ('invalid JSON', '')]:
                (app / 'installation.json').write_text(metadata_text)
                result = subprocess.run([str(executable), '--version'], cwd=directory,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'defeedback-linux ' + metadata['version'] + suffix + '\n')
            self.assertFalse(old.is_symlink())
            self.assertIn('Name=De-Feedback Linux — unofficial integration', desktop.read_text())
            self.assertIn('Exec=reaper', desktop.read_text())
            old.symlink_to(home / 'unrelated-command')
            updater.install(None, home / 'REAPER', app, home / 'backup-unrelated')
            self.assertTrue(old.is_symlink())
            for source, target in updater.RESOURCES.items():
                self.assertEqual((app / target).read_bytes(), (BUNDLE / source).read_bytes())
            self.assertTrue((home / '.local/bin/defeedback-linux').is_symlink())
            for action in ('install', 'start'):
                result = subprocess.run([str(home / '.local/bin/defeedback-linux'), 'vsthost', action, '--help'],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('defeedback-linux vsthost ' + action, result.stdout)
            result = subprocess.run([str(home / '.local/bin/defeedback-linux'), 'audio', 'ini', '--device',
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
