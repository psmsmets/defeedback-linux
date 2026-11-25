#!/usr/bin/env python3
"""Install optional VSTHost without creating shortcuts or changing audio setup."""
import argparse
import fcntl
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

DOWNLOAD_URL = 'https://www.hermannseib.com/programs/vsthostx64.zip'


def extract(archive, target):
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            path = PurePosixPath(member.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.filename
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise RuntimeError('Unsafe path or link in the VSTHost archive.')
        package.extractall(target)


def install(source, app):
    destination = app / 'vsthostx64'
    if (destination / 'vsthost.exe').is_file() and (destination / 'license.txt').is_file():
        print('VSTHost is already installed. Run defeedback-linux start vsthost.')
        return
    if destination.exists() or destination.is_symlink():
        raise RuntimeError('Incomplete VSTHost installation; move it aside before reinstalling: ' + str(destination))
    app.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vsthost-', dir=app) as temporary:
        stage = Path(temporary)
        if source is None:
            source = stage / 'vsthostx64.zip'
            print('Downloading optional VSTHost from ' + DOWNLOAD_URL, flush=True)
            with urlopen(DOWNLOAD_URL, timeout=60) as response:
                final = urlparse(response.url)
                if final.scheme != 'https' or final.hostname not in ('www.hermannseib.com', 'hermannseib.com'):
                    raise RuntimeError('Unexpected VSTHost download redirect.')
                with source.open('wb') as output:
                    shutil.copyfileobj(response, output)
        if source.is_dir():
            package = source
        else:
            unpacked = stage / 'unpacked'
            extract(source, unpacked)
            candidates = [path.parent for path in unpacked.rglob('vsthost.exe')]
            if len(candidates) != 1:
                raise RuntimeError('Expected one vsthost.exe in the complete x64 package.')
            package = candidates[0]
        if not (package / 'vsthost.exe').is_file() or not (package / 'license.txt').is_file():
            raise RuntimeError('Use the complete VSTHost x64 package, including vsthost.exe and license.txt.')
        prepared = stage / 'installed'
        shutil.copytree(package, prepared)
        prepared.rename(destination)
    print('VSTHost installed: ' + str(destination))
    print('The upstream free package is for private use only; its license excludes commercial or professional use.')
    print('Review the package terms: ' + str(destination / 'license.txt'))
    print('Run defeedback-linux start vsthost. Standard activation remains available directly in REAPER.')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='defeedback-linux install vsthost', description=__doc__,
        epilog='VSTHost has its own license terms. The upstream free package is for private use only.')
    parser.add_argument('--source', type=Path, help='complete local x64 package directory or ZIP instead of downloading')
    args = parser.parse_args(argv)
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or os.geteuid() == 0:
        raise RuntimeError('Run as your regular desktop user on Ubuntu Studio x86-64.')
    home = Path.home()
    shared = home / '.local/share'
    shared.mkdir(parents=True, exist_ok=True)
    with (shared / 'defeedback-setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Setup, another installation, or an update is running.')
        running = subprocess.run(['pgrep', '-u', str(os.getuid()), '-ix', 'vsthost[.]exe'], capture_output=True)
        if running.returncode != 1:
            raise RuntimeError('Close VSTHost before installing; could not confirm that it is stopped.')
        install(args.source.resolve() if args.source else None, shared / 'defeedback')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        print('Error: ' + str(error), file=sys.stderr)
        sys.exit(1)
