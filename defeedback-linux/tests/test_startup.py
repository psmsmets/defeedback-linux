"""Experimental AES67 selection without stream-readiness gating."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import startup_config
spec = importlib.util.spec_from_file_location('startup_launcher', Path(__file__).resolve().parents[1] / 'lib/reaper-launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class Startup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        p = patch.object(Path, 'home', return_value=self.home)
        p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / 'config'),
                                    'XDG_STATE_HOME': str(self.home / 'state')})
        p.start(); self.addCleanup(p.stop)
        for name in ('.local/opt/REAPER/reaper', '.local/opt/defeedback-wine-dcomp/runtime/bin/wine',
                     '.local/opt/defeedback-wine-dcomp/runtime/bin/wineserver'):
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(); path.chmod(0o755)
        startup_config.config_dir().mkdir(parents=True)
        (startup_config.config_dir() / 'pipewire-aes67.conf').write_text('local.ifname = enp2s0\n')
        self.seed = self.home / 'saved-jack.ini'
        self.seed.write_text('[reaper]\nlinux_audio_mode=operator_saved_jack\nlastproject=old.RPP\n')

    def enable(self):
        with patch.object(startup_config.shutil, 'which', return_value='/usr/bin/pw-jack'), contextlib.redirect_stdout(io.StringIO()):
            startup_config.configure('enable', ['--reaper-ini', str(self.seed)])

    def launch(self, cards, args=()):
        with patch.object(launcher, 'detect_cards', return_value=cards), \
                patch.object(launcher.time, 'monotonic', side_effect=[0, 11]), \
                patch.object(launcher.shutil, 'which', return_value='/usr/bin/pw-jack'), \
                patch.object(launcher, 'run_logged', return_value=0) as run, \
                patch('sys.argv', ['reaper', *args]):
            self.assertEqual(launcher.main(), 0)
            return run

    def test_default_disabled_and_disable(self):
        self.assertFalse(startup_config.enabled())
        self.assertFalse(self.launch([]).called)
        self.enable()
        self.assertTrue(startup_config.enabled())
        startup_config.configure('disable', [])
        self.assertFalse(startup_config.enabled())
        self.assertFalse(self.launch([]).called)

    def test_early_launch_four_paths_and_no_readiness_gate(self):
        self.enable()
        run = self.launch([])
        self.assertEqual(run.call_args.args[0][0], '/usr/bin/pw-jack')
        environment = run.call_args.args[2]
        self.assertEqual(environment['DEFEEDBACK_TEMPLATE_CHANNELS'], '4')
        self.assertEqual(environment['DEFEEDBACK_TRANSPORT'], 'aes67')
        self.assertIsNotNone(run.call_args.kwargs['health'])
        self.assertNotIn('lastproject=', startup_config.reaper_ini().read_text())
        self.assertIn('linux_audio_mode=operator_saved_jack', startup_config.reaper_ini().read_text())

    def test_eight_path_override_remains_available(self):
        self.enable()
        run = self.launch([], ['--channels', '8'])
        self.assertEqual(run.call_args.args[2]['DEFEEDBACK_TEMPLATE_CHANNELS'], '8')
        self.assertTrue(run.call_args.args[2]['DEFEEDBACK_TEMPLATE_OUTPUT'].endswith('8ch.RPP'))

    def test_explicit_aes67_uses_managed_profile_with_usb_and_fallback_disabled(self):
        self.enable()
        startup_config.configure('disable', [])
        global_ini = startup_config.reaper_ini().parent / 'reaper.ini'
        global_ini.write_text('[reaper]\nlinux_audio_mode=1\n')
        run = self.launch([dict(id='EVO8', family='evo8', inputs=4, outputs=4)], ['--device', 'aes67'])
        command = run.call_args.args[0]
        self.assertEqual(command[0], '/usr/bin/pw-jack')
        self.assertEqual(command[command.index('-cfgfile') + 1], str(startup_config.reaper_ini()))
        self.assertEqual(run.call_args.args[2]['DEFEEDBACK_TEMPLATE_CHANNELS'], '4')
        self.assertIn('linux_audio_mode=1', global_ini.read_text())
        self.assertFalse(startup_config.enabled())

    def test_explicit_aes67_requires_profile_and_valid_channel_count(self):
        with self.assertRaisesRegex(RuntimeError, 'profile'):
            self.launch([], ['--device', 'aes67'])
        self.enable()
        with self.assertRaisesRegex(RuntimeError, 'mono paths'):
            self.launch([], ['--device', 'aes67', '--channels', '5'])
        with patch.object(launcher.shutil, 'which', return_value=None), \
                patch('sys.argv', ['reaper', '--device', 'aes67']), self.assertRaisesRegex(RuntimeError, 'pw-jack'):
            launcher.main()

    def test_usb_priority_and_explicit_selection(self):
        self.enable()
        run = self.launch([dict(id='EVO8', family='evo8', inputs=4, outputs=4)])
        self.assertNotEqual(run.call_args.args[0][0], '/usr/bin/pw-jack')
        self.assertEqual(run.call_args.args[2]['DEFEEDBACK_TEMPLATE_CHANNELS'], '4')
        self.assertFalse(self.launch([], ['--device', 'cq']).called)

    def test_reject_alsa_and_invalid_config(self):
        self.seed.write_text('[reaper]\nlinux_audio_mode=1\n')
        with self.assertRaisesRegex(RuntimeError, 'ALSA'):
            self.enable()
        (startup_config.config_dir() / 'startup.json').write_text('{"aes67_enabled": "yes"}')
        with self.assertRaisesRegex(RuntimeError, 'Invalid'):
            startup_config.enabled()
