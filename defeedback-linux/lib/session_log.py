#!/usr/bin/env python3
"""Bounded text logs and process supervision; never records audio."""
from datetime import datetime, timezone
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time

MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 2
KEEP_SESSIONS = 10


def state_dir():
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'defeedback'


def log_dir():
    return state_dir() / 'logs'


def prune_sessions(directory, keep=KEEP_SESSIONS):
    bases = sorted(directory.glob('session-*.log'), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in bases[keep:]:
        lock_path = Path(str(path) + '.lock')
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            for member in [path, *directory.glob(path.name + '.[0-9]*')]:
                member.unlink(missing_ok=True)
            lock_path.unlink(missing_ok=True)


class Session:
    def __init__(self, label, debug=False, max_bytes=MAX_BYTES):
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        label = re.sub(r'[^a-zA-Z0-9_-]', '-', label)[:40]
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        fd, name = tempfile.mkstemp(prefix=f'session-{stamp}-{label}-', suffix='.log', dir=directory)
        os.close(fd)
        self.path = Path(name)
        self.lock_path = Path(name + '.lock')
        self.lock = self.lock_path.open('a')
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        self.debug = debug
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        self.logger.propagate = False
        handler = RotatingFileHandler(name, maxBytes=max_bytes, backupCount=BACKUPS, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)sZ %(levelname)s %(message)s')
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info('SESSION start label=%s pid=%s debug=%s', label, os.getpid(), debug)
        try:
            metadata = Path.home() / '.local/share/defeedback/installation.json'
            revision = json.loads(metadata.read_text()).get('revision') if metadata.exists() else None
            self.logger.info('SYSTEM kernel=%s revision=%s', os.uname().release, revision or 'unknown')
            prune_sessions(directory)
        except (OSError, ValueError) as error:
            self.logger.warning('Metadata/retention check failed: %s', error)

    def __enter__(self):
        print('Session log: ' + str(self.path), file=sys.stderr)
        return self

    def __exit__(self, kind, error, traceback):
        if error:
            self.logger.error('SESSION failed: %s', error, exc_info=self.debug and kind is not KeyboardInterrupt)
        self.logger.info('SESSION end')
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
        self.lock_path.unlink(missing_ok=True)
        self.lock.close()


def debug_snapshot(session):
    """Read-only, bounded startup context; no environment dump or PCM opening."""
    for path in (Path('/proc/asound/cards'), Path('/proc/version'), Path('/etc/os-release')):
        try:
            session.logger.debug('%s: %s', path, path.read_text()[:16384])
        except OSError as error:
            session.logger.debug('%s: %s', path, error)
    for command in (['ip', '-brief', 'address'], ['pw-metadata', '-n', 'settings']):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
            session.logger.debug('%s exit=%s: %s', command[0], result.returncode,
                                 (result.stdout + result.stderr)[:32768])
        except (OSError, subprocess.TimeoutExpired) as error:
            session.logger.debug('%s: %s', command[0], error)


def run_logged(command, session, environment=None, health=None):
    """Drain child text output separately from audio; bound queued output and disk usage."""
    output = queue.Queue(maxsize=256)
    dropped = [0]
    child = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, bufsize=0)
    session.logger.info('PROCESS start executable=%s pid=%s', Path(command[0]).name, child.pid)

    def offer(item):
        try:
            output.put_nowait(item)
        except queue.Full:
            try:
                output.get_nowait()
                dropped[0] += 1
            except queue.Empty:
                pass
            try:
                output.put_nowait(item)
            except queue.Full:
                dropped[0] += 1

    def drain():
        try:
            while True:
                block = child.stdout.read(4096)
                if not block:
                    break
                offer(block)
        finally:
            child.stdout.close()
            offer(None)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    handlers = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        handlers[number] = signal.getsignal(number)
        signal.signal(number, lambda signum, frame: child.send_signal(signum) if child.poll() is None else None)
    next_health = time.monotonic()
    exited_at = None
    next_heartbeat = time.monotonic() + 60
    try:
        while True:
            try:
                block = output.get(timeout=1)
            except queue.Empty:
                block = b''
                if child.poll() is not None:
                    exited_at = exited_at or time.monotonic()
                    if time.monotonic() - exited_at >= 2:
                        session.logger.warning('Output pipe still open after process exit; stopping capture.')
                        break
            if block is None:
                break
            if block:
                text = block.decode('utf-8', errors='replace')
                session.logger.info('OUTPUT %s', text.rstrip())
                try:
                    sys.stdout.write(text)
                    sys.stdout.flush()
                except (BrokenPipeError, OSError):
                    pass
            if time.monotonic() >= next_heartbeat and child.poll() is None:
                session.logger.info('PROCESS alive pid=%s', child.pid)
                next_heartbeat = time.monotonic() + 60
            if health and time.monotonic() >= next_health:
                try:
                    health(session.logger)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    session.logger.warning('Health check unavailable: %s', error)
                next_health = time.monotonic() + 15
        status = child.wait()
        if dropped[0]:
            session.logger.warning('OUTPUT dropped %s chunks during output burst', dropped[0])
        session.logger.log(logging.INFO if status == 0 else logging.ERROR, 'PROCESS exit status=%s', status)
        return status if status >= 0 else 128 - status
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


def audio_health(card_id=None, aes67=False):
    """Report state transitions only; no hot switching, audio capture, or automatic recovery."""
    previous = {}

    def report(logger, key, value, healthy):
        if previous.get(key) != value:
            logger.log(logging.INFO if healthy else logging.WARNING, 'HEALTH %s=%s', key, value)
            previous[key] = value

    def check(logger):
        if card_id:
            identifiers = []
            for path in Path('/proc/asound').glob('card*/id'):
                try:
                    identifiers.append(path.read_text().strip())
                except OSError:
                    pass
            present = card_id in identifiers
            report(logger, 'usb-device', 'present' if present else 'missing', present)
        if aes67:
            config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'defeedback/pipewire-aes67.conf'
            text = config.read_text()
            match = re.search(r'^\s*local\.ifname\s*=\s*"?([a-zA-Z0-9_.-]+)', text, re.M)
            if not match:
                raise RuntimeError('No configured AES67 interface')
            iface = match[1]
            try:
                link = (Path('/sys/class/net') / iface / 'carrier').read_text().strip() == '1'
            except OSError:
                link = False
            report(logger, 'aes67-link:' + iface, 'up' if link else 'down', link)
            try:
                result = subprocess.run(['pmc', '-u', '-b', '0', '-s', '/run/ptp4l-defeedbackro',
                                         'GET PORT_DATA_SET'], capture_output=True, text=True, timeout=2)
                states = re.findall(r'portState\s+(\w+)', result.stdout) if result.returncode == 0 else []
            except (OSError, subprocess.TimeoutExpired):
                states = []
            locked = bool(states) and all(state == 'SLAVE' for state in states)
            report(logger, 'ptp-port-state', ','.join(states) if states else 'unavailable', locked)
            try:
                result = subprocess.run(['pw-dump'], capture_output=True, text=True, timeout=2)
                if result.returncode:
                    raise ValueError('PipeWire unavailable')
                report(logger, 'aes67-endpoints', 'available', True)
                nodes = [item.get('info', {}).get('props', {}) for item in json.loads(result.stdout)]
                source = any(node.get('device.api') == 'aes67' and node.get('media.class') == 'Audio/Source' for node in nodes)
                sink = any(node.get('node.name') == 'defeedback-aes67-return' for node in nodes)
                report(logger, 'aes67-source', 'present' if source else 'missing', source)
                report(logger, 'aes67-return', 'present' if sink else 'missing', sink)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                report(logger, 'aes67-endpoints', 'unavailable', False)
    return check


def sources():
    state = state_dir()
    paths = set()
    for pattern in ('*.log', '*.log.[0-9]*', 'setup-*', 'diagnostics-*', 'trim-*'):
        paths.update(path for path in log_dir().glob(pattern) if path.is_file())
    paths.update(path for path in state.glob('*.RPP.log*') if path.is_file())
    paths.update(path for path in state.glob('*/update.log') if path.is_file())
    paths.update(path for path in (state / 'wine-dcomp').glob('build.*') if path.is_file())
    for legacy in (state / 'reaper-launch.log', state / 'wine-installer.log'):
        if legacy.is_file():
            paths.add(legacy)
    def modified(path):
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0
    return sorted((path for path in paths if path.is_file()), key=modified)


def tail(path, count):
    # Read backwards so a legacy unbounded file does not have to fit in memory.
    with path.open('rb') as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        data = b''
        while position > 0 and data.count(b'\n') <= count and len(data) < 1024 * 1024:
            size = min(position, 65536)
            position -= size
            handle.seek(position)
            data = handle.read(size) + data
    return '\n'.join(data.decode('utf-8', errors='replace').splitlines()[-count:])
