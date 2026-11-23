"""Verify explicit network targets and preserve the eight-channel clock configuration."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/setup-aes67.sh'


class AES67Config(unittest.TestCase):
    def test_network_targets_and_layout_validation(self):
        program = SCRIPT.read_text().split('-v latency="$network_latency" \'', 1)[1].split("' \"$base\"", 1)[0]
        fixture = '''context.properties = {
}
clock.interface = eth0
local.ifname = eth0
local.ifname = eth0
destination.ip = 239.69.1.1
ptp.management-socket = old
sess.name = old
node.name = "rtp-sink"
audio.channels = 2
node.channel-names = ["CH1", "CH2"]
sess.latency.msec = 3
sess.latency.msec = 3
'''
        for value in (1, 2, 3, 20):
            result = subprocess.run(['awk', '-v', 'iface=enp2s0', '-v', 'group=239.69.1.2',
                                     '-v', 'quantum=48', '-v', f'latency={value}', program],
                                    input=fixture, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count(f'sess.latency.msec = {value}'), 2)
            self.assertIn('audio.channels = 8', result.stdout)
            self.assertIn('default.clock.quantum = 48', result.stdout)
        result = subprocess.run(['awk', program], input=fixture.replace('sess.latency.msec = 3\n', '', 1),
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
