#!/usr/bin/env python3
"""Select a USB audio device, prepare REAPER preferences, and launch REAPER."""
import argparse
import configparser
import fcntl
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from session_log import Session, audio_health, debug_snapshot, run_logged


def detect_cards(asound=Path('/proc/asound')):
    cards = []
    for directory in sorted(asound.glob('card[0-9]*')):
        streams = list(directory.glob('stream[0-9]*'))
        if not streams or not (directory / 'id').is_file():
            continue
        identifier = (directory / 'id').read_text().strip()
        text = '\n'.join(path.read_text() for path in streams)
        description = identifier + ' ' + text.split('\n', 1)[0]
        lower = description.lower()
        family = None
        if 'scarlett' in lower or 'focusrite' in lower:
            family = 'focusrite'
        elif identifier.lower().startswith('evo8'):
            family = 'evo8'
        elif identifier.lower().startswith('u192k'):
            family = 'behringer'
        elif identifier.lower().startswith('cq'):
            family = 'cq'
        elif identifier.lower().startswith('sq'):
            family = 'sq'
        elif identifier.lower().startswith('qu'):
            family = 'qu'
        if not family:
            continue
        # USB stream descriptors report capture and playback capabilities separately.
        counts = {'Capture': [], 'Playback': []}
        for direction, section in re.findall(
                r'(?m)^(Capture|Playback):\s*\n(.*?)(?=^(?:Capture|Playback):|\Z)',
                text, re.S):
            counts[direction].extend(int(value) for value in re.findall(r'Channels:\s*(\d+)', section))
        if not all(counts.values()):
            continue
        cards.append(dict(id=identifier, family=family,
                          inputs=max(counts['Capture']), outputs=max(counts['Playback'])))
    return cards


def select_card(cards, requested):
    matches = cards
    if requested != 'auto':
        matches = [card for card in cards if requested in
                   (card['family'], card['id'], 'hw:' + card['id'])]
    elif any(card['family'] == 'focusrite' for card in cards):
        matches = [card for card in cards if card['family'] == 'focusrite']
    if not matches:
        raise LookupError('No matching USB capture/playback device found. AES67 uses the explicit manual launcher.')
    if len(matches) != 1:
        names = ', '.join('hw:' + card['id'] for card in matches)
        raise RuntimeError('Multiple matching USB devices: ' + names + '. Select one with --device or DEFEEDBACK_DEVICE.')
    return matches[0]


def routing(card, requested_count):
    family = card['family']
    first_input = 1
    if family == 'cq':
        model = card['id'].upper()
        if model.startswith('CQ12T'):
            maximum, first_input = 5, 6
        elif model.startswith(('CQ18T', 'CQ20B')):
            maximum, first_input = 8, 9
        else:
            raise RuntimeError('Unknown CQ model: ' + card['id'] + '. Its return mapping must be configured first.')
    else:
        maximum = {'focusrite': 4, 'evo8': 4, 'behringer': 2, 'sq': 8, 'qu': 8}[family]
    available = min(card['inputs'] - first_input + 1, card['outputs'], maximum)
    count = requested_count
    if count is None:
        choices = (5,) if family == 'cq' and maximum == 5 else (8, 4, 2, 1)
        count = next((value for value in choices if value <= available), None)
    if count is None or not 1 <= count <= available:
        raise RuntimeError('Requested routing exceeds the USB device channel capacity.')
    return count, first_input


def ini_config(card, seed=None):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if seed is not None:
        parser.read(seed)
    if not parser.has_section('reaper'):
        parser.add_section('reaper')
    section = parser['reaper']
    defaults = {
        'linux_auto_pasuspend': '1', 'linux_disable_pm': '1', 'linux_mlockall': '0',
        'projsmpterateuseproj': '1', 'projsrate': '48000',
        'vstpath': '~/.vst;~/.vst3', 'workthreads': '4',
    }
    for key, value in defaults.items():
        section.setdefault(key, value)
    # Prevent captured machine-specific projects from being restored at startup.
    for key in list(section):
        if key in ('lastproject', 'lastprojuiref') or key.startswith('projecttab'):
            del section[key]
    section.update({
        'alsa_indev': 'hw:' + card['id'], 'alsa_outdev': 'hw:' + card['id'],
        'alsa_rtprio': '50', 'linux_audio_mode': '1',
        'linux_audio_bits': '24', 'linux_audio_bsize': '64', 'linux_audio_bufs': '3',
        'linux_audio_srate': '48000', 'linux_audio_srateor': '0',
        'linux_audio_nch_in': str(card['inputs']),
        'linux_audio_nch_out': str(card['outputs']), 'projecttabs': '0',
    })
    return parser


def prepare_ini(path, seed, card):
    parser = ini_config(card, path if path.exists() else seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.defeedback-ini-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            parser.write(handle, space_around_delimiters=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true', default=os.environ.get('DEFEEDBACK_DEBUG') == '1',
                        help='extra text diagnostics without recording audio')
    parser.add_argument('--device', default=os.environ.get('DEFEEDBACK_DEVICE', 'auto'),
                        help='auto, focusrite, evo8, behringer, cq, sq, qu, or an exact ALSA card ID')
    parser.add_argument('--channels', type=int, choices=(1, 2, 4, 5, 8),
                        default=os.environ.get('DEFEEDBACK_CHANNELS'), help='override the default path count')
    parser.add_argument('--print-ini', action='store_true',
                        help='print a minimal device INI to stdout without writing files or launching')
    parser.add_argument('--inputs', type=int, help='capture port count for offline --print-ini')
    parser.add_argument('--outputs', type=int, help='playback port count for offline --print-ini')
    parser.add_argument('--detect', action='store_true', help='print the selected device and routing without launching')
    parser.add_argument('--missing-audio', choices=('skip', 'error'),
                        default=os.environ.get('DEFEEDBACK_MISSING_AUDIO', 'skip'),
                        help='skip startup successfully (default) or report an error when USB audio is absent')
    parser.add_argument('--raw', action='store_true', help='launch with saved REAPER preferences and the supplied arguments')
    args, reaper_args = parser.parse_known_args()
    if args.inputs is not None or args.outputs is not None:
        if not args.print_ini or args.inputs is None or args.outputs is None:
            parser.error('--inputs and --outputs require --print-ini and must be supplied together')
        if min(args.inputs, args.outputs) < 1:
            parser.error('Input and output port counts must be positive')
        if not re.fullmatch(r'hw:[a-zA-Z0-9_-]+', args.device):
            parser.error('Offline INI generation requires an exact --device hw:CARD_ID')
    if args.print_ini:
        if args.raw or args.detect or reaper_args or args.channels is not None:
            parser.error('--print-ini cannot be combined with --raw, --detect, --channels, or REAPER arguments')
        if args.inputs is not None:
            card = dict(id=args.device[3:], inputs=args.inputs, outputs=args.outputs)
        else:
            try:
                card = select_card(detect_cards(), args.device)
            except LookupError as error:
                raise RuntimeError(str(error)) from error
        ini_config(card).write(sys.stdout, space_around_delimiters=False)
        return 0
    home = Path.home()
    app = home / '.local/share/defeedback'
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'defeedback'
    state.mkdir(parents=True, exist_ok=True)
    with Session('reaper', args.debug) as session:
        logger = session.logger
        with open(state / 'reaper.lock', 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logger.info('De-Feedback REAPER is already running.')
                return 0
            environment = os.environ.copy()
            selected_id = None
            if args.debug:
                debug_snapshot(session)
            if not args.raw:
                deadline = time.monotonic() + (0 if args.detect else 10)
                cards = detect_cards()
                while not cards and time.monotonic() < deadline:
                    time.sleep(0.5)
                    cards = detect_cards()
                try:
                    card = select_card(cards, args.device)
                except LookupError as error:
                    logger.warning('%s', error)
                    if args.missing_audio == 'skip' and not args.detect:
                        logger.info('REAPER startup skipped safely. Connect USB audio and launch again, or use the explicit AES67 test after PTP lock.')
                        return 0
                    raise RuntimeError(str(error)) from error
                selected_id = card['id']
                count, first_input = routing(card, args.channels)
                logger.info('Selected hw:%s (%s), %s mono paths, inputs %s–%s to outputs 1–%s; 48000 Hz, 24-bit, 64 samples, 3 periods.',
                             card['id'], card['family'], count, first_input, first_input + count - 1, count)
                if args.detect:
                    print(('Selected hw:%s (%s): %s mono paths, inputs %s–%s to outputs 1–%s; '
                           '48000 Hz, 24-bit, 64 samples, 3 periods.') %
                          (card['id'], card['family'], count, first_input, first_input + count - 1, count))
                    return 0
                resource = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'REAPER'
                source = app / 'reaper'
                seed = resource / 'reaper.ini'
                safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', card['id'])
                ini = resource / ('reaper-defeedback-' + safe_id + '.ini')
                prepare_ini(ini, seed, card)
                if not reaper_args:
                    project = state / ('defeedback-' + safe_id + '-' + str(count) + 'ch.RPP')
                    environment.update(DEFEEDBACK_TEMPLATE_PROFILE='automatic',
                                       DEFEEDBACK_TEMPLATE_CHANNELS=str(count),
                                       DEFEEDBACK_TEMPLATE_FIRST_INPUT=str(first_input),
                                       DEFEEDBACK_TEMPLATE_OUTPUT=str(project),
                                       DEFEEDBACK_TEMPLATE_LOG=str(state / 'logs' / ('template-' + safe_id + '-' + str(count) + 'ch.log')))
                    reaper_args = ['-new', str(source / 'create-template.lua')]
                reaper_args = ['-newinst', '-cfgfile', str(ini)] + reaper_args
            wine = home / '.local/opt/defeedback-wine-dcomp/runtime/bin'
            executable = home / '.local/opt/REAPER/reaper'
            if not all(path.is_file() and os.access(path, os.X_OK)
                       for path in (wine / 'wine', wine / 'wineserver', executable)):
                raise RuntimeError('Patched Wine or REAPER is missing. Run setup-defeedback.sh first.')
            for key in ('WINEPREFIX', 'WINEARCH', 'WINEDLLOVERRIDES'):
                environment.pop(key, None)
            environment.update(WINELOADER=str(wine / 'wine'), WINESERVER=str(wine / 'wineserver'),
                               PATH=str(wine) + os.pathsep + environment.get('PATH', ''))
            logger.info('LAUNCH transport=%s executable=%s project=%s',
                        environment.get('DEFEEDBACK_TRANSPORT', 'manual' if args.raw else 'usb'),
                        executable, environment.get('DEFEEDBACK_TEMPLATE_OUTPUT', 'explicit/saved'))
            environment.setdefault('WINEDEBUG', '-all,err+all')
            if args.debug:
                environment['WINEDEBUG'] = '+timestamp,+pid,+tid,err+all,warn+all'
                environment['PIPEWIRE_DEBUG'] = '3'
                logger.debug('REAPER arguments=%s', reaper_args)
            return run_logged([str(executable)] + reaper_args, session, environment,
                              health=audio_health(selected_id, environment.get('DEFEEDBACK_TRANSPORT') == 'aes67'))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, configparser.Error) as error:
        logging.error('%s', error)
        sys.exit(1)
