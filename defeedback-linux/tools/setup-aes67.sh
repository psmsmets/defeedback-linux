#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

usage() {
    cat <<'EOF'
Usage: bash setup-aes67.sh INTERFACE RETURN_MULTICAST_IP

Prepare an optional PipeWire AES67 test for Avantis or dLive at 48 kHz.
Use a wired interface with a PTP hardware clock and an unused 239.69.x.x
return group that matches the Dante card's AES67 receive prefix.
Run as your desktop user. The script writes a per-user config and prints
the commands to start the test; it does not start or restart services.
EOF
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
[[ $# == 2 ]] || { usage >&2; exit 2; }

iface=$1
group=$2
[[ $iface =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,14}$ ]] || fail "Invalid interface name."
[[ $group =~ ^239\.69\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})$ ]] ||
    fail "Expected a return multicast address in 239.69.0.0/16."
(( BASH_REMATCH[1] <= 255 && BASH_REMATCH[2] <= 255 )) || fail "Invalid IPv4 address."
[[ $(uname -s) == Linux ]] || fail "Run this script on the Ubuntu Studio machine."
(( EUID != 0 )) || fail "Run as your desktop user without sudo."

for cmd in ip ethtool ptp4l pmc pipewire; do
    command -v "$cmd" >/dev/null ||
        fail "Missing $cmd. On Ubuntu, install iproute2 ethtool linuxptp pipewire pipewire-bin."
done
addresses=$(ip -4 -o addr show dev "$iface" scope global) ||
    fail "Could not query IPv4 addresses on $iface."
[[ $addresses == *' inet '* ]] ||
    fail "$iface needs an IPv4 address on the audio network."
caps=$(ethtool -T "$iface") || fail "Could not query timestamping on $iface."
[[ $caps == *hardware-transmit* && $caps == *hardware-receive* &&
   $caps =~ PTP[[:space:]]Hardware[[:space:]]Clock:[[:space:]]+([0-9]+) ]] ||
    fail "$iface needs hardware TX/RX timestamping and a PTP hardware clock."
phc="/dev/ptp${BASH_REMATCH[1]}"
[[ -r $phc ]] || fail "Your desktop user cannot read $phc."

base=/usr/share/pipewire/pipewire-aes67.conf
[[ -r $base ]] || fail "PipeWire's packaged AES67 config is missing: $base"

conf_dir="${XDG_CONFIG_HOME:-$HOME/.config}/defeedback"
conf="$conf_dir/pipewire-aes67.conf"
mkdir -p -- "$conf_dir"
tmp=$(mktemp "$conf_dir/.aes67.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT

# Patch only active keys and refuse an unfamiliar upstream layout.
awk -v iface="$iface" -v group="$group" '
    /^[[:space:]]*clock\.interface[[:space:]]*=/ { sub(/=.*/, "= \"" iface "\""); clock++ }
    /^[[:space:]]*local\.ifname[[:space:]]*=/ { sub(/=.*/, "= \"" iface "\""); nic++ }
    /^[[:space:]]*destination\.ip[[:space:]]*=/ { sub(/=.*/, "= " group); dst++ }
    /^[[:space:]]*ptp\.management-socket[[:space:]]*=/ {
        sub(/=.*/, "= \"/run/ptp4l-defeedbackro\""); socket++
    }
    /^[[:space:]]*sess\.name[[:space:]]*=/ { sub(/=.*/, "= \"De-Feedback Return\""); sess++ }
    /^[[:space:]]*node\.name[[:space:]]*=[[:space:]]*"rtp-sink"/ {
        sub(/=.*/, "= \"defeedback-aes67-return\""); sink++
    }
    { print }
    END { if (clock != 1 || nic != 2 || dst != 1 || socket != 1 || sess != 1 || sink != 1) exit 1 }
' "$base" > "$tmp" || fail "Unexpected layout in $base; no config was replaced."

mv -- "$tmp" "$conf"
printf 'Wrote %s. PTP hardware clock: %s.\n\n' "$conf" "$phc"
printf 'Terminal 1 (PTP client, domain 0; use only one ptp4l on this interface):\n'
printf '  sudo ptp4l -i %q -H -4 -E -s -m --domainNumber=0 --uds_address=/run/ptp4l-defeedback --uds_ro_address=/run/ptp4l-defeedbackro\n\n' "$iface"
printf 'Terminal 2 (confirm the port is SLAVE and the expected grandmaster is present):\n'
printf "  pmc -u -b 0 -s /run/ptp4l-defeedbackro 'GET PORT_DATA_SET' 'GET TIME_STATUS_NP'\n\n"
printf 'Terminal 3 (as your desktop user, after PTP lock):\n'
printf '  pipewire -c %q\n' "$conf"
