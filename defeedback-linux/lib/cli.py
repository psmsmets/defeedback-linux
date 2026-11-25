#!/usr/bin/env python3
"""Operate and update the De-Feedback workstation."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from session_log import Session, debug_snapshot, run_logged
from log_commands import show_logs
from aes67_runtime import start as start_aes67
from startup_config import configure as configure_startup
from project_version import describe_version

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = 'https://github.com/psmsmets/defeedback-linux.git'
DEFAULT_BRANCH = 'main'

GROUPS = {
    'audio': (
        'Inspect audio devices, collect diagnostics, or print REAPER settings.',
        {'check': 'Check a device profile; Focusrite Scarlett is the default',
         'diagnose': 'Save a local system and audio diagnostic report',
         'ini': 'Print a minimal REAPER audio INI to stdout'},
        'Example: defeedback-linux audio check focusrite\n'
        'Use logs --help for saved logs and run --help for REAPER launch options.'),
    'aes67': (
        'Configure and manually operate experimental AES67 audio.',
        {'install': 'Install optional network/PTP/PipeWire packages',
         'setup': 'Prepare the audio NIC, PTP access, and PipeWire configuration',
         'enable': 'Opt into experimental REAPER fallback using saved JACK preferences',
         'disable': 'Disable the experimental startup fallback',
         'status': 'Show the startup fallback setting',
         'ptp': 'Run the PTP client in the foreground',
         'ptp-status': 'Query PTP port state and grandmaster',
         'audio': 'Run the PipeWire helper after verifying PTP SLAVE state'},
        'Setup does not start PTP/audio services. End-to-end hardware validation is pending.\n'
        'Example: defeedback-linux aes67 setup --help'),
    'appliance': (
        'Configure an installed workstation for headless USB operation.',
        {'setup': 'Enable Plasma autologin, REAPER autostart, and workstation settings',
         'trim': 'Preview optional application removal; --apply performs cleanup'},
        'First install from the Linux bundle: bash setup-defeedback.sh\n'
        'Then enable headless startup: defeedback-linux appliance setup\n'
        'Or combine installation and startup: bash setup-defeedback.sh --appliance\n'
        'A graphical Plasma session is required. AES67 service startup remains manual.'),
    'vsthost': (
        'Install or start the optional VSTHost application.',
        {'install': 'Download the official x64 package, or use --source for a local package',
         'start': 'Open De-Feedback in VSTHost with patched Wine'},
        'Standard activation is in REAPER: De-Feedback FX > UI > Options > License Management.\n'
        'VSTHost is optional and has its own license; the upstream free package is for private use only.\n'
        'Example: defeedback-linux vsthost install --help'),
}


def grouped_command(name, arguments):
    description, actions, note = GROUPS[name]
    parser = argparse.ArgumentParser(prog='defeedback-linux ' + name,
        usage='%(prog)s [-h] ACTION [ARGS ...]', description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Actions:\n' + '\n'.join(f'  {action:<12}{text}' for action, text in actions.items())
               + '\n\n' + note + '\nUse defeedback-linux ' + name + ' ACTION --help for options.')
    if not arguments or arguments[0] in ('-h', '--help'):
        parser.print_help()
        return 0
    action, *options = arguments
    if action not in actions:
        parser.error('unknown action: ' + action + '; choose ' + ', '.join(actions))
    if name == 'aes67':
        if action in ('enable', 'disable', 'status'):
            return configure_startup(action, options)
        if action in ('ptp', 'ptp-status', 'audio'):
            return start_aes67(action, options, os.environ.get('DEFEEDBACK_DEBUG') == '1')
    route = {'audio': {'check': 'check', 'diagnose': 'diagnose', 'ini': 'ini'},
             'appliance': {'setup': 'appliance-setup', 'trim': 'trim'},
             'vsthost': {'install': 'install-vsthost', 'start': 'start-vsthost'},
             'aes67': {'install': 'aes67-install', 'setup': 'aes67-setup'}}[name][action]
    return execute(dispatch(route, options))


def execute(command):
    """The launcher supervises REAPER; other tools get a bounded command session."""
    if command[1].endswith('reaper-launch.py') or any(arg in ('--help', '-h') for arg in command[2:]):
        os.execv(command[0], command)
    with Session(Path(command[1]).stem, os.environ.get('DEFEEDBACK_DEBUG') == '1') as session:
        if session.debug:
            debug_snapshot(session)
        return run_logged(command, session)


def dispatch(name, arguments):
    if name in ('run', 'ini'):
        launcher = ROOT / 'bin/reaper-launch.py'
        if not launcher.is_file():
            launcher = ROOT / 'lib/reaper-launch.py'
        return [sys.executable, str(launcher)] + (['--print-ini'] if name == 'ini' else []) + arguments
    if name == 'install-vsthost':
        return [sys.executable, str(ROOT / 'tools/install-vsthost.py')] + arguments
    script = ROOT / 'tools' / {
        'start-vsthost': 'start-vsthost.sh',
        'check': 'check-audio.sh', 'diagnose': 'diagnose.sh',
        'aes67-install': 'install-aes67.sh', 'aes67-setup': 'setup-aes67.sh',
        'appliance-setup': 'setup-appliance.sh', 'trim': 'trim-workstation.sh',
    }[name]
    return ['/bin/bash', str(script)] + arguments


def git(directory, *arguments):
    result = subprocess.run(['git', '-C', str(directory), *arguments],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Git command failed.')
    return result.stdout.strip()


def read_source(config):
    if not config.exists():
        return {'repo': DEFAULT_REPO, 'branch': DEFAULT_BRANCH}
    value = json.loads(config.read_text())
    if not isinstance(value, dict) or not all(isinstance(value.get(k), str) and value[k]
                                             for k in ('repo', 'branch')):
        raise RuntimeError('Invalid update source configuration: ' + str(config))
    return value


def update(arguments, session=None):
    parser = argparse.ArgumentParser(prog='defeedback-linux update',
                                     description='Fetch project code and install workstation integration.')
    parser.add_argument('--check', action='store_true', help='fetch and compare without activating an update')
    parser.add_argument('--reaper', action='store_true', help='also update the REAPER runtime')
    parser.add_argument('--repo', help='Git repository for the first managed checkout')
    parser.add_argument('--branch', help='Git branch for the first managed checkout (default: main)')
    args = parser.parse_args(arguments)
    if platform.system() != 'Linux' or os.geteuid() == 0:
        raise RuntimeError('Run as your regular desktop user on Ubuntu Studio.')
    home = Path.home()
    app = home / '.local/share/defeedback'
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'defeedback'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'source-update.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another project update is running.')
        # Check before fetching; the bundle updater rechecks with the installation locks.
        if not args.check:
            result = subprocess.run(['pgrep', '-u', str(os.getuid()), '-ix', 'reaper'],
                                    stdout=subprocess.DEVNULL)
            if result.returncode == 0:
                raise RuntimeError('Close REAPER before updating.')
            if result.returncode != 1:
                raise RuntimeError('Could not check whether REAPER is running.')
        config = state / 'update-source.json'
        source = read_source(config)
        repo = args.repo or source['repo']
        branch = args.branch or source['branch']
        if repo.startswith('-') or '\n' in repo or not repo:
            raise RuntimeError('Invalid repository URL.')
        subprocess.run(['git', 'check-ref-format', '--branch', branch],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        checkout = app / 'source'
        if not checkout.exists():
            app.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.source-', dir=app) as temporary:
                stage = Path(temporary) / 'checkout'
                subprocess.run(['git', 'clone', '--single-branch', '--branch', branch,
                                '--', repo, str(stage)], check=True)
                stage.rename(checkout)
            config.write_text(json.dumps({'repo': repo, 'branch': branch}, indent=2) + '\n')
        if git(checkout, 'remote', 'get-url', 'origin') != repo:
            raise RuntimeError('Managed checkout has a different origin. Its source was not changed.')
        if git(checkout, 'branch', '--show-current') != branch:
            raise RuntimeError('Managed checkout is on a different branch. No branch switch was made.')
        if git(checkout, 'status', '--porcelain', '--untracked-files=all'):
            raise RuntimeError('Managed checkout has local changes. Resolve them before updating: ' + str(checkout))
        git(checkout, 'fetch', 'origin', 'refs/heads/' + branch)
        current = git(checkout, 'rev-parse', 'HEAD')
        target = git(checkout, 'rev-parse', 'FETCH_HEAD')
        ancestor = subprocess.run(['git', '-C', str(checkout), 'merge-base', '--is-ancestor',
                                   current, target], stdout=subprocess.DEVNULL)
        if ancestor.returncode:
            raise RuntimeError('Update is not a fast-forward. No reset, merge, or rebase was performed.')
        print('Project source: ' + repo + ' (' + branch + ')', flush=True)
        metadata = app / 'installation.json'
        active = json.loads(metadata.read_text()).get('revision') if metadata.exists() else None
        print('Installed revision: ' + (active or 'unknown (install from a Git checkout to record it)'), flush=True)
        print('Checkout revision: ' + current[:12] + ' -> ' + target[:12], flush=True)
        if args.check:
            print('No installed files changed. The managed checkout may have been created or fetched.')
            return 0
        git(checkout, 'merge', '--ff-only', target)
        updater = checkout / 'defeedback-linux/update-defeedback.sh'
        if not updater.is_file():
            raise RuntimeError('Updated repository has no defeedback-linux/update-defeedback.sh.')
        command = ['/bin/bash', str(updater)] + ([] if args.reaper else ['--integration-only'])
        if session is None:
            subprocess.run(command, check=True)
        elif run_logged(command, session) != 0:
            raise RuntimeError('Integration update failed; see session log.')
        if session:
            session.logger.info('UPDATE installed target=%s reaper=%s', target, args.reaper)
        print('Project update completed. Wine, yabridge, and the plugin were not changed.')
    return 0


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    debug = '--debug' in arguments or os.environ.get('DEFEEDBACK_DEBUG') == '1'
    arguments = [value for value in arguments if value != '--debug']
    if debug:
        os.environ['DEFEEDBACK_DEBUG'] = '1'
    # Keep existing scripts working while the public help uses topic-first commands.
    aliases = {'check': ('audio', 'check'), 'diagnose': ('audio', 'diagnose'),
               'ini': ('audio', 'ini'), 'trim': ('appliance', 'trim')}
    if arguments and arguments[0] in aliases:
        arguments = [*aliases[arguments[0]], *arguments[1:]]
    elif len(arguments) >= 2 and arguments[0] in ('install', 'start') and arguments[1] == 'vsthost':
        arguments = ['vsthost', arguments[0], *arguments[2:]]
    commands = {
        'run': 'Start REAPER with the connected audio device (default)',
        'update': 'Install project updates; add --reaper to update REAPER too',
        'logs': 'Read workstation logs',
        'audio': 'Check devices, collect diagnostics, or print audio settings',
        'aes67': 'Install, configure, or manually start AES67 audio',
        'appliance': 'Configure headless startup or preview application cleanup',
        'vsthost': 'Install or start the optional VSTHost application',
    }
    command_width = max(map(len, commands)) + 2
    parser = argparse.ArgumentParser(prog='defeedback-linux',
        usage='%(prog)s [-h] [--version] [--debug] [COMMAND] [ARGS ...]',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Unofficial Linux integration for the Alpha Labs De-Feedback plugin.\n'
                    'Not affiliated with or endorsed by Alpha Labs.\n'
                    'REAPER and De-Feedback require separate licenses; neither is included.',
        epilog='Commands:\n' + '\n'.join(f'  {name:<{command_width}}{description}' for name, description in commands.items()) + '\n\n'
               'Without a command, start REAPER.\n'
               'Use defeedback-linux COMMAND --help, then COMMAND ACTION --help for details.\n\n'
               'Examples:\n'
               '  defeedback-linux\n'
               '  defeedback-linux appliance setup\n'
               '  defeedback-linux aes67 --help\n\n'
               'First installation: bash setup-defeedback.sh (from the Linux bundle).\n'
               'Plugin activation: open De-Feedback FX in REAPER and click UI.\n\n'
               'Products and licensing:\n'
               '  REAPER: https://www.reaper.fm/purchase.php\n'
               '  De-Feedback: https://www.alphalabsaudio.com/defeedback/')
    parser.add_argument('--debug', action='store_true', help='extra text diagnostics; never records audio')
    parser.add_argument('--version', action='store_true', help='show the integration version and installed Git revision, when available')
    try:
        if arguments and arguments[0] == '--version':
            parser.parse_args(arguments)
            print(describe_version(ROOT))
            return 0
        if not arguments or (arguments[0].startswith('-') and arguments[0] not in ('-h', '--help')):
            return execute(dispatch('run', arguments))
        if arguments[0] in ('-h', '--help'):
            parser.print_help()
            return 0
        command = arguments.pop(0)
        if command not in commands:
            parser.error('unknown command: ' + command)
        if command in GROUPS:
            return grouped_command(command, arguments)
        if command == 'logs':
            return show_logs(arguments)
        if command == 'update':
            if any(arg in ('--help', '-h') for arg in arguments):
                return update(arguments)
            with Session('update', debug) as session:
                return update(arguments, session)
        return execute(dispatch(command, arguments))
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1
