#!/usr/bin/env bash
# Install optional AES67 dependencies without requiring an active audio network.
set -euo pipefail
[[ $(uname -s) == Linux ]] || { printf 'Run this on Ubuntu Studio.\n' >&2; exit 1; }
(( EUID != 0 )) || { printf 'Run as your desktop user without sudo.\n' >&2; exit 1; }
sudo apt-get update
sudo apt-get install -y iproute2 ethtool linuxptp pipewire pipewire-bin pipewire-jack libpipewire-0.3-modules wireplumber
base=/usr/share/pipewire/pipewire-aes67.conf
if [[ ! -r $base ]]; then
    printf 'Packages installed, but %s is missing. This PipeWire version needs an upgrade with AES67 support before configuration.\n' "$base" >&2
    exit 1
fi
printf 'AES67 packages installed. No network settings or startup services were changed.\n'
printf 'After connecting enp2s0 and assigning an audio-network IPv4 address, run:\n'
printf '  bash tools/setup-aes67.sh enp2s0 RETURN_MULTICAST_IP\n'
printf 'Use an unused 239.69.x.x return address matching the Dante receive prefix.\n'
