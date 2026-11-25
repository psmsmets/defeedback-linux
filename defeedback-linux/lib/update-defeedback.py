#!/usr/bin/env python3
"""Update Linux REAPER and the De-Feedback launcher resources for the current user."""
import argparse
from datetime import datetime
import fcntl
import hashlib
import html
import json
import logging
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

BUNDLE = Path(__file__).resolve().parent.parent
RESOURCES = {
    'VERSION': 'VERSION',
    'defeedback-linux': 'bin/defeedback-linux',
    'lib/cli.py': 'lib/cli.py',
    'lib/project_version.py': 'lib/project_version.py',
    'lib/startup_config.py': 'lib/startup_config.py',
    'lib/session_log.py': 'lib/session_log.py',
    'lib/log_commands.py': 'lib/log_commands.py',
    'lib/aes67_runtime.py': 'lib/aes67_runtime.py',
    'config/resources.conf': 'config/resources.conf',
    'lib/reaper': 'bin/reaper',
    'lib/reaper-launch.py': 'bin/reaper-launch.py',
    'reaper/create-template.lua': 'reaper/create-template.lua',
    'reaper/plugin-state.RPP': 'reaper/plugin-state.RPP',
}
for tool in ('check-audio.sh', 'diagnose.sh', 'install-aes67.sh', 'setup-aes67.sh',
             'setup-appliance.sh', 'trim-workstation.sh', 'install-vsthost.py', 'start-vsthost.sh'):
    RESOURCES['tools/' + tool] = 'tools/' + tool


def version(filename):
    match = re.fullmatch(r'reaper(\d)(\d+)_linux_x86_64.tar.xz', filename)
    if not match:
        raise RuntimeError('Expected an official REAPER Linux x86-64 archive filename.')
    return int(match[1]), int(match[2])


def pinned_resource():
    for line in (BUNDLE / 'config/resources.conf').read_text().splitlines():
        fields = line.split('|')
        if fields[:2] == ['reaper', 'file'] and len(fields) == 5:
            return tuple(fields[2:])
    raise RuntimeError('Missing REAPER entry in config/resources.conf.')


def latest_resource(page):
    links = re.findall(r'href=[\"\']([^\"\']*reaper\d+_linux_x86_64\.tar\.xz)[\"\']', page)
    if not links:
        raise RuntimeError('The official download page has no Linux x86-64 archive link.')
    url = urljoin('https://www.reaper.fm/download.php', html.unescape(links[0]))
    filename = urlparse(url).path.rsplit('/', 1)[-1]
    text = html.unescape(re.sub(r'<[^>]+>', ' ', page))
    checksum = re.search(r'sha256sum\s+' + re.escape(filename) + r'\s+([a-fA-F0-9]{64})\b', text)
    if not checksum:
        raise RuntimeError('Could not find the published SHA-256 for the current REAPER archive.')
    return filename, url, checksum[1].lower()


def fetch(url, destination=None):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ('www.reaper.fm', 'reaper.fm'):
        raise RuntimeError('REAPER downloads must use the official HTTPS website.')
    with urlopen(url, timeout=60) as response:
        final = urlparse(response.url)
        if final.scheme != 'https' or not (final.hostname == 'reaper.fm' or
                                           (final.hostname or '').endswith('.reaper.fm')):
            raise RuntimeError('Unexpected download redirect.')
        if destination:
            with destination.open('wb') as output:
                shutil.copyfileobj(response, output)
        else:
            return response.read().decode('utf-8')


def verify_archive(path, checksum):
    if not re.fullmatch(r'[a-fA-F0-9]{64}', checksum):
        raise RuntimeError('A SHA-256 checksum is required for the REAPER archive.')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != checksum.lower():
        raise RuntimeError('REAPER archive SHA-256 mismatch.')


def extract_runtime(archive, directory):
    prefix = ('reaper_linux_x86_64', 'REAPER')
    with tarfile.open(archive, 'r:xz') as source:
        members = []
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unsafe archive path.')
            if path.parts[:2] != prefix:
                continue
            if not (member.isfile() or member.isdir()):
                raise RuntimeError('Unexpected link or special file in the REAPER runtime.')
            members.append(member)
        source.extractall(directory, members=members)
    runtime = directory / 'reaper_linux_x86_64/REAPER'
    if not (runtime / 'reaper').is_file() or not os.access(runtime / 'reaper', os.X_OK):
        raise RuntimeError('The REAPER archive has an unexpected layout.')
    return runtime


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.defeedback-update-', dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        shutil.copy2(source, temporary)
        if target.name == 'reaper':
            temporary.chmod(0o755)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def install(runtime, installed, app, backup):
    # Snapshot integration files before changing either component.
    originals = {}
    for target in [*RESOURCES.values(), 'installation.json']:
        destination = app / target
        if destination.exists():
            original = backup / 'integration' / target
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, original)
            originals[target] = original
        else:
            originals[target] = None
    old_runtime = installed.with_name('REAPER.before-update-' + backup.name)
    moved_old = False
    installed_new = False
    changed = []
    link = Path.home() / ".local/bin/defeedback-linux"
    link_created = False
    try:
        if runtime:
            installed.rename(old_runtime)
            moved_old = True
            runtime.rename(installed)
            installed_new = True
        for relative, target in RESOURCES.items():
            atomic_copy(BUNDLE / relative, app / target)
            changed.append(target)
        revision = None
        if shutil.which('git'):
            result = subprocess.run(['git', '-C', str(BUNDLE), 'rev-parse', 'HEAD'],
                                    text=True, capture_output=True)
            if result.returncode == 0:
                revision = result.stdout.strip()
        with tempfile.TemporaryDirectory(prefix='.metadata-', dir=app) as temporary:
            metadata = Path(temporary) / 'installation.json'
            metadata.write_text(json.dumps({'version': (app / 'VERSION').read_text().strip(),
                                            'revision': revision}) + '\n')
            atomic_copy(metadata, app / 'installation.json')
            changed.append('installation.json')
        link = Path.home() / '.local/bin/defeedback-linux'
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.exists() and not link.is_symlink():
            link.symlink_to(app / 'bin/defeedback-linux')
            link_created = True
        elif not link.is_symlink() or link.resolve() != (app / 'bin/defeedback-linux').resolve():
            logging.warning('Keeping existing command %s; use %s.', link, app / 'bin/defeedback-linux')
    except BaseException:
        if link_created:
            link.unlink(missing_ok=True)
        for target in reversed(changed):
            if originals[target]:
                atomic_copy(originals[target], app / target)
            else:
                (app / target).unlink(missing_ok=True)
        if installed_new:
            shutil.rmtree(installed)
        if moved_old:
            old_runtime.rename(installed)
        raise
    # Remove only the old command symlink installed by this project.
    old_command = Path.home() / '.local/bin/defeedback'
    try:
        if old_command.is_symlink() and old_command.resolve() == (app / 'bin/defeedback').resolve():
            old_command.unlink()
        refresh_desktop_names(app, backup)
    except OSError as error:
        logging.warning('Integration installed, but command/desktop cleanup failed: %s', error)
    if moved_old:
        logging.info('Previous REAPER runtime: %s', old_runtime)


def refresh_desktop_names(app, backup):
    home = Path.home()
    applications = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'applications'
    desktop = home / 'Desktop'
    if shutil.which('xdg-user-dir'):
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], text=True, capture_output=True)
        candidate = Path(result.stdout.strip())
        if result.returncode == 0 and candidate.is_absolute() and candidate != home:
            desktop = candidate
    def retire(path, category):
        target = backup / 'legacy-vsthost' / category / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target, follow_symlinks=False)
        path.unlink()

    command = home / '.local/bin/vsthost'
    if command.is_symlink() and command.resolve() == (app / 'bin/vsthost').resolve():
        retire(command, 'commands')
    for relative in ('bin/vsthost', 'lib/open-license-gui.sh'):
        script = app / relative
        if (script.is_file() and not script.is_symlink()
                and 'Usage: defeedback-linux open-license-gui' in script.read_text()):
            retire(script, Path(relative).parent.name)
    for category, directory in (('applications', applications), ('desktop', desktop)):
        shortcut = directory / 'defeedback-vsthost.desktop'
        if shortcut.is_file() and not shortcut.is_symlink():
            text = shortcut.read_text()
            if ('Name=VSTHost (De-Feedback License)' in text
                    and str(app / 'bin/vsthost') in text):
                retire(shortcut, category)
        entry = directory / 'defeedback-reaper.desktop'
        if not entry.is_file():
            continue
        lines = entry.read_text().splitlines()
        lines = ['Name=De-Feedback Linux — unofficial integration' if line.startswith('Name=') else
                 'Comment=Unofficial Linux integration for the Alpha Labs De-Feedback plugin' if line.startswith('Comment=') else
                 line for line in lines]
        entry.write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--latest', action='store_true', help='download the current stable REAPER 7 release from the official website')
    selection.add_argument('--pinned', action='store_true', help='use the version and checksum in config/resources.conf')
    selection.add_argument('--archive', type=Path, help='use a local REAPER Linux x86-64 archive')
    selection.add_argument('--integration-only', action='store_true', help='update the launcher and template resources without replacing REAPER')
    parser.add_argument('--sha256', help='published SHA-256 for a local archive whose name differs from the manifest')
    parser.add_argument('--check', action='store_true', help='show the selected update without installing')
    args = parser.parse_args()
    if args.sha256 and not args.archive:
        parser.error('--sha256 requires --archive')
    filename, url, checksum = pinned_resource()
    if args.latest or not (args.pinned or args.archive or args.integration_only):
        filename, url, checksum = latest_resource(fetch('https://www.reaper.fm/download.php?hashes=1'))
    if args.archive:
        if args.archive.name != filename and not args.sha256:
            raise RuntimeError('Supply --sha256 for this local archive.')
        filename = args.archive.name
        checksum = args.sha256 or checksum
    selected_version = version(filename)
    if not args.integration_only and not ((7, 43) <= selected_version < (8, 0)):
        raise RuntimeError('Automatic mono templates require REAPER 7.43 or newer. This updater targets REAPER 7.x.')
    print('Selected update: ' + ('launcher and templates only' if args.integration_only else
          f'REAPER {selected_version[0]}.{selected_version[1]:02d}, launcher and templates'), flush=True)
    if args.check:
        return
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64') or os.geteuid() == 0:
        raise RuntimeError('Run as the regular De-Feedback user on Linux x86-64.')
    home = Path.home()
    app = home / '.local/share/defeedback'
    installed = home / '.local/opt/REAPER'
    if not (installed / 'reaper').is_file():
        raise RuntimeError('REAPER is not installed. Run setup-defeedback.sh first.')
    for relative in RESOURCES:
        if not (BUNDLE / relative).is_file():
            raise RuntimeError('Missing bundle resource: ' + relative)
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'defeedback'
    state.mkdir(parents=True, exist_ok=True)
    # Use the same locks as setup and the runtime launcher.
    locks = []
    for path in (home / '.local/share/defeedback-setup.lock', state / 'reaper.lock'):
        handle = path.open('a')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Setup, another update, or REAPER is running. Close it before updating.')
        locks.append(handle)
    result = subprocess.run(['pgrep', '-u', str(os.getuid()), '-ix', 'reaper'], capture_output=True)
    if result.returncode == 0:
        raise RuntimeError('Close REAPER before updating.')
    if result.returncode != 1:
        raise RuntimeError('Could not check whether REAPER is running.')
    backup = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=state))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(backup / 'update.log')])
    configuration = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'REAPER'
    if configuration.exists():
        shutil.copytree(configuration, backup / 'REAPER-config', symlinks=True)
    for project in state.glob('*.RPP'):
        shutil.copy2(project, backup / project.name)
    logging.info('Update backup and log: %s', backup)
    with tempfile.TemporaryDirectory(prefix='.defeedback-update-', dir=installed.parent) as temporary:
        stage = Path(temporary)
        runtime = None
        if not args.integration_only:
            archive = args.archive
            if archive is None:
                archive = stage / filename
                logging.info('Downloading %s', url)
                fetch(url, archive)
            verify_archive(archive, checksum)
            runtime = extract_runtime(archive, stage)
        install(runtime, installed, app, backup)
    logging.info('Update completed. Launch REAPER through the desktop shortcut or reaper command.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, tarfile.TarError) as error:
        logging.error('%s', error)
        sys.exit(1)
