#!/usr/bin/env python3
"""Read centrally indexed application logs and the optional user journal."""
import argparse
import subprocess
import time

from session_log import sources, state_dir, tail


def show_logs(arguments):
    parser = argparse.ArgumentParser(prog='defeedback-linux logs',
                                     description='Read text logs. No audio is recorded.')
    parser.add_argument('--list', action='store_true', help='list session, diagnostic, template, setup, and update logs')
    parser.add_argument('--all', action='store_true', help='show the tail of every indexed log')
    parser.add_argument('--file', help='select a listed filename or path relative to the state directory')
    parser.add_argument('--lines', type=int, default=100, help='tail lines per source (1–10000; default: 100)')
    parser.add_argument('--follow', action='store_true', help='follow one selected/latest log, including rotation')
    parser.add_argument('--journal', action='store_true', help='also show recent REAPER/PipeWire user service messages')
    args = parser.parse_args(arguments)
    if not 1 <= args.lines <= 10000:
        parser.error('--lines must be between 1 and 10000')
    if args.follow and (args.all or args.list):
        parser.error('--follow selects one log, not --all or --list')
    if args.file and args.all:
        parser.error('choose --file or --all')
    paths = sources()
    if args.file:
        paths = [path for path in paths if args.file in (path.name, str(path.relative_to(state_dir())))]
        if len(paths) != 1:
            parser.error('--file must identify exactly one entry from --list')
    if args.list:
        print('Log directory: ' + str(state_dir() / 'logs'))
        for path in paths:
            try:
                print(f'{path.stat().st_size:>10}  {path.relative_to(state_dir())}')
            except FileNotFoundError:
                continue
        return 0
    selected = paths if args.all else paths[-1:]
    if not selected:
        print('No application logs found. Run a command first, or add --journal.')
    for path in selected:
        print('== ' + str(path) + ' ==')
        try:
            print(tail(path, args.lines))
        except FileNotFoundError:
            print('Log rotated or expired while reading.')
    if args.journal:
        try:
            result = subprocess.run(['journalctl', '--user', '--no-pager', '-n', str(args.lines),
                                     '-u', 'defeedback-reaper.service', '-u', 'pipewire.service',
                                     '-u', 'wireplumber.service'], text=True, capture_output=True, timeout=5)
            print('== User service journal ==')
            print(result.stdout or result.stderr or 'No accessible journal entries.')
        except (OSError, subprocess.TimeoutExpired) as error:
            print('User service journal unavailable: ' + str(error))
    if args.follow and selected:
        path = selected[0]
        stat = path.stat()
        inode, position = stat.st_ino, stat.st_size
        while True:
            time.sleep(0.5)
            try:
                stat = path.stat()
                if stat.st_ino != inode or stat.st_size < position:
                    inode, position = stat.st_ino, 0
                with path.open('rb') as handle:
                    handle.seek(position)
                    block = handle.read(65536)
                    position = handle.tell()
                if block:
                    print(block.decode('utf-8', errors='replace'), end='', flush=True)
            except FileNotFoundError:
                continue
    return 0
