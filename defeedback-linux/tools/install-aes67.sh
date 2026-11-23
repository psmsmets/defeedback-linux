#!/usr/bin/env bash
# Install optional AES67 dependencies without requiring an active audio network.
set -euo pipefail
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf 'Usage: defeedback-linux aes67 install\nInstall optional AES67 packages on Ubuntu Studio.\n'
    exit 0
fi
[[ $# == 0 ]] || { printf 'No arguments expected.\n' >&2; exit 2; }
[[ $(uname -s) == Linux ]] || { printf 'Run this on Ubuntu Studio.\n' >&2; exit 1; }
(( EUID != 0 )) || { printf 'Run as your desktop user without sudo.\n' >&2; exit 1; }
sudo apt-get update
sudo apt-get install -y acl udev network-manager iproute2 ethtool linuxptp pipewire pipewire-bin pipewire-jack libpipewire-0.3-modules wireplumber
base=/usr/share/pipewire/pipewire-aes67.conf
if [[ ! -r $base ]]; then
    printf 'Packages installed, but %s is missing. This PipeWire version needs an upgrade with AES67 support before configuration.\n' "$base" >&2
    exit 1
fi
printf 'AES67 packages installed. No network settings or startup services were changed.\n'
printf 'Run interactive setup as your desktop user (the audio cable may remain disconnected):\n'
printf '  bash tools/setup-aes67.sh\n'
printf 'Use an unused 239.69.x.x return address matching the Dante receive prefix.\n'
