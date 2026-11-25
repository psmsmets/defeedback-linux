"""Verify opt-in VSTHost installation without downloading or running vendor software."""
import contextlib
import fcntl
import importlib.util
import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_vsthost', BUNDLE / 'tools/install-vsthost.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class VSTHost(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.app = self.home / '.local/share/defeedback'
        self.archive = self.home / 'package.zip'
        with zipfile.ZipFile(self.archive, 'w') as package:
            package.writestr('vsthostx64/vsthost.exe', b'test executable')
            package.writestr('vsthostx64/license.txt', 'Test license')
            package.writestr('vsthostx64/Data/test.ini', 'Companion data')

    def test_local_zip_and_directory_preserve_complete_package_without_shortcuts(self):
        for source in (self.archive, self.home / 'extracted/vsthostx64'):
            with self.subTest(source=source), contextlib.redirect_stdout(io.StringIO()):
                if source.is_dir():
                    target = self.home / 'directory-install'
                else:
                    target = self.app
                    installer.extract(self.archive, self.home / 'extracted')
                installer.install(source, target)
                self.assertEqual((target / 'vsthostx64/license.txt').read_text(), 'Test license')
                self.assertEqual((target / 'vsthostx64/Data/test.ini').read_text(), 'Companion data')
                self.assertFalse((target / 'bin').exists())
        self.assertFalse((self.home / 'Desktop').exists())
        self.assertFalse((self.home / '.local/bin').exists())

    def test_default_download_and_repeated_install_does_not_replace_package(self):
        response = io.BytesIO(self.archive.read_bytes())
        response.url = installer.DOWNLOAD_URL
        with patch.object(installer, 'urlopen', return_value=response) as download, \
                contextlib.redirect_stdout(io.StringIO()):
            installer.install(None, self.app)
            download.assert_called_once_with(installer.DOWNLOAD_URL, timeout=60)
        with patch.object(installer, 'urlopen') as download, contextlib.redirect_stdout(io.StringIO()):
            installer.install(None, self.app)
            download.assert_not_called()
        self.assertEqual((self.app / 'vsthostx64/vsthost.exe').read_bytes(), b'test executable')

    def test_rejects_unexpected_download_redirect(self):
        response = io.BytesIO(self.archive.read_bytes())
        response.url = 'https://example.invalid/package.zip'
        with patch.object(installer, 'urlopen', return_value=response), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, 'redirect'):
            installer.install(None, self.app)
        self.assertFalse((self.app / 'vsthostx64').exists())

    def test_rejects_unsafe_archives_and_missing_license_without_partial_install(self):
        for name in ('../outside', '/absolute', 'folder\\outside', 'symlink', 'no-license'):
            with self.subTest(name=name):
                archive = self.home / 'unsafe.zip'
                with zipfile.ZipFile(archive, 'w') as package:
                    package.writestr('vsthost.exe', b'test executable')
                    if name == 'symlink':
                        member = zipfile.ZipInfo('link')
                        member.external_attr = (stat.S_IFLNK | 0o777) << 16
                        package.writestr(member, '../outside')
                    elif name != 'no-license':
                        package.writestr(name, 'invalid')
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                    installer.install(archive, self.app)
                self.assertFalse((self.app / 'vsthostx64').exists())
                self.assertEqual(list(self.app.glob('.vsthost-*')), [])
        self.assertFalse((self.home / 'outside').exists())

    def test_main_honors_setup_lock_and_installs_local_package(self):
        shared = self.home / '.local/share'
        shared.mkdir(parents=True)
        with patch.object(installer.Path, 'home', return_value=self.home), \
                patch.object(installer.platform, 'system', return_value='Linux'), \
                patch.object(installer.platform, 'machine', return_value='x86_64'), \
                patch.object(installer.os, 'geteuid', return_value=1000), \
                patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                contextlib.redirect_stdout(io.StringIO()):
            with (shared / 'defeedback-setup.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                with self.assertRaisesRegex(RuntimeError, 'running'):
                    installer.main(['--source', str(self.archive)])
            self.assertFalse((self.app / 'vsthostx64').exists())
            self.assertEqual(installer.main(['--source', str(self.archive)]), 0)
        self.assertTrue((self.app / 'vsthostx64/vsthost.exe').exists())

    def test_resource_preparation_skips_optional_package_unless_selected(self):
        config = self.home / 'resources.conf'
        config.write_text('vsthost|optional-manual|vsthostx64/vsthost.exe|https://www.hermannseib.com/english/vsthost.htm|-\n')
        for arguments, requested in (([], False), (['--only', 'vsthost'], True)):
            result = subprocess.run(['/bin/bash', str(BUNDLE / 'download-resources.sh'),
                '--config', str(config), '--output', str(self.home / 'packages'), *arguments],
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual('Supply vsthostx64/vsthost.exe' in result.stdout, requested)


if __name__ == '__main__':
    unittest.main()
