#!/usr/bin/env python3
"""Run the manually configured AES67 helpers with bounded text logging."""
import argparse
import os
from pathlib import Path
import re
import subprocess

from session_log import Session, audio_health, debug_snapshot, run_logged


def start(action, arguments, debug=False):
    parser = argparse.ArgumentParser(prog='defeedback-linux aes67 ' + action,
        description='Run the configured helper in the foreground with persistent text logs. Stop with Ctrl+C.')
    parser.parse_args(arguments)
    with Session('aes67-' + action, debug) as session:
        config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'defeedback/pipewire-aes67.conf'
        if not config.is_file():
            raise RuntimeError('Run defeedback-linux aes67 setup first.')
        match = re.search(r'^\s*local\.ifname\s*=\s*"?([a-zA-Z0-9_.-]+)', config.read_text(), re.M)
        if not match:
            raise RuntimeError('No valid AES67 interface in ' + str(config))
        iface = match[1]
        if action == 'ptp':
            command = ['sudo', 'ptp4l', '-i', iface, '-H', '-4', '-E', '-s', '-m', '--domainNumber=0',
                       '--uds_address=/run/ptp4l-defeedback', '--uds_ro_address=/run/ptp4l-defeedbackro']
        else:
            result = subprocess.run(['pmc', '-u', '-b', '0', '-s', '/run/ptp4l-defeedbackro',
                                     'GET PORT_DATA_SET'], text=True, capture_output=True, timeout=3)
            states = re.findall(r'portState\s+(\w+)', result.stdout)
            if result.returncode or not states or any(state != 'SLAVE' for state in states):
                raise RuntimeError('PTP is not in SLAVE state. Start the PTP helper and confirm the expected grandmaster first.')
            command = ['pipewire', '-c', str(config)]
        session.logger.info('AES67 interface=%s config=%s action=%s', iface, config, action)
        if debug:
            debug_snapshot(session)
        environment = os.environ.copy()
        if debug:
            environment['PIPEWIRE_DEBUG'] = '3'
        return run_logged(command, session, environment,
                          health=audio_health(aes67=True) if action == 'audio' else None)
