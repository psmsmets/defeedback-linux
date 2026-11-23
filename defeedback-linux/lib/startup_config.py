#!/usr/bin/env python3
"""Opt-in early AES67 fallback; no network services are started here."""
import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import tempfile


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'defeedback'


def enabled():
    path = config_dir() / 'startup.json'
    if not path.exists():
        return False
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or type(value.get('aes67_enabled')) is not bool:
        raise RuntimeError('Invalid AES67 startup setting: ' + str(path))
    return value['aes67_enabled']


def reaper_ini():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'REAPER/reaper-defeedback-aes67.ini'


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.startup-')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def configure(action, arguments):
    parser = argparse.ArgumentParser(prog='defeedback-linux aes67 ' + action,
        description='Opt into experimental REAPER startup before AES67 readiness. USB retains priority.')
    if action == 'enable':
        parser.add_argument('--reaper-ini', type=Path,
                            help='REAPER preferences saved with JACK selected; required for first activation')
    args = parser.parse_args(arguments)
    if action == 'status':
        print('AES67 fallback: ' + ('enabled (experimental early launch)' if enabled() else 'disabled'))
        print('Default processing: 4 mono paths; maximum: 8. Network ports: 8 per direction.')
        print('REAPER profile: ' + str(reaper_ini()))
        print('PTP/audio services are not activated by this setting.')
        return 0
    if action == 'enable':
        if not (config_dir() / 'pipewire-aes67.conf').is_file():
            raise RuntimeError('Run defeedback-linux aes67 install and setup first.')
        if not shutil.which('pw-jack'):
            raise RuntimeError('pw-jack is missing; install the AES67 packages first.')
        source = args.reaper_ini or reaper_ini()
        if not source.is_file():
            raise RuntimeError('Select JACK in REAPER, close REAPER, then enable with --reaper-ini PATH to its saved preferences.')
        ini = configparser.ConfigParser(interpolation=None, strict=False)
        ini.optionxform = str
        ini.read(source)
        if not ini.has_section('reaper') or not ini['reaper'].get('linux_audio_mode'):
            raise RuntimeError('The source must contain saved REAPER audio preferences with JACK selected.')
        # Preserve the operator-selected backend; do not guess REAPER backend enum values.
        section = ini['reaper']
        if section.get('linux_audio_mode') == '1':
            raise RuntimeError('The supplied profile still selects ALSA. Select JACK in REAPER and save it first.')
        for key in list(section):
            if key in ('lastproject', 'lastprojuiref') or key.startswith('projecttab'):
                del section[key]
        section.update(projecttabs='0', linux_audio_nch_in='8', linux_audio_nch_out='8',
                       linux_audio_srate='48000', linux_audio_srateor='0')
        import io
        output = io.StringIO()
        ini.write(output, space_around_delimiters=False)
        atomic_text(reaper_ini(), output.getvalue())
        print('Using operator-saved backend settings; verify JACK was selected in REAPER.')
    atomic_text(config_dir() / 'startup.json', json.dumps({'aes67_enabled': action == 'enable'}) + '\n')
    print('AES67 fallback ' + ('enabled for the next launch.' if action == 'enable' else 'disabled for the next launch.'))
    print('Running audio, PTP, and PipeWire processes are not changed.')
    return 0
