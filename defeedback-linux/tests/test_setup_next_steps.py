"""Verify post-install guidance and opt-in headless setup without system changes."""
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest

BUNDLE = Path(__file__).resolve().parents[1]


class SetupNextSteps(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.marker = self.home / 'appliance-enabled'
        self.tool = self.home / 'appliance.sh'
        self.tool.write_text('#!/bin/bash\nprintf enabled > "$TEST_MARKER"\n')
        self.environment = dict(os.environ, HOME=str(self.home),
                                XDG_CONFIG_HOME=str(self.home / 'config'), TEST_MARKER=str(self.marker))

    def run_steps(self, mode='ask', answer=None):
        command = ['/bin/bash', '-eu', '-c', 'source "$1"; show_setup_next_steps "$2" "$3"',
                   'setup-test', str(BUNDLE / 'lib/setup-next-steps.sh'), mode, str(self.tool)]
        if answer is None:
            return subprocess.run(command, env=self.environment, stdin=subprocess.DEVNULL,
                                  text=True, capture_output=True, timeout=5)
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(command, env=self.environment, stdin=slave,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            os.close(slave)
            slave = None
            os.write(master, answer.encode())
            stdout, stderr = process.communicate(timeout=5)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)

    def test_noninteractive_setup_shows_next_steps_without_enabling(self):
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('defeedback-linux appliance setup', result.stdout)
        self.assertIn('Options > License Management', result.stdout)
        self.assertIn('AES67 service startup remains manual', result.stdout)
        self.assertNotIn('[y/N]', result.stdout)
        self.assertFalse(self.marker.exists())

    def test_interactive_question_defaults_to_no(self):
        for answer in ('\n', 'n\n', 'no\n'):
            with self.subTest(answer=answer):
                result = self.run_steps(answer=answer)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('[y/N]', result.stdout)
                self.assertFalse(self.marker.exists())

    def test_interactive_yes_runs_the_appliance_step(self):
        result = self.run_steps(answer='yes\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), 'enabled')

    def test_explicit_choices_do_not_ask(self):
        skipped = self.run_steps(mode='false', answer='yes\n')
        self.assertEqual(skipped.returncode, 0, skipped.stderr)
        self.assertNotIn('[y/N]', skipped.stdout)
        self.assertFalse(self.marker.exists())
        enabled = self.run_steps(mode='true')
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        self.assertNotIn('[y/N]', enabled.stdout)
        self.assertTrue(self.marker.exists())

    def test_existing_service_is_preserved_without_prompting(self):
        unit = self.home / 'config/systemd/user/defeedback-reaper.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('Existing service')
        result = self.run_steps(answer='yes\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('[y/N]', result.stdout)
        self.assertIn('settings are kept', result.stdout)
        self.assertFalse(self.marker.exists())
        self.assertEqual(unit.read_text(), 'Existing service')

    def test_conflicting_installer_flags_fail_before_installation(self):
        result = subprocess.run(['/bin/bash', str(BUNDLE / 'setup-defeedback.sh'),
                                 '--appliance', '--no-appliance'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Choose either --appliance or --no-appliance', result.stderr)


if __name__ == '__main__':
    unittest.main()
