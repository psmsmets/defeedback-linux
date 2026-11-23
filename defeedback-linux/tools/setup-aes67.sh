#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

usage() {
    cat <<'EOF'
Usage: bash setup-aes67.sh [--network link-local|dhcp|existing] [--quantum 48|64] [INTERFACE [RETURN_MULTICAST_IP]]

Prepare an optional PipeWire AES67 test for Avantis or dLive at 48 kHz.
Use a wired interface with a PTP hardware clock and an unused 239.69.x.x
return group that matches the Dante card's AES67 receive prefix.
Run as your desktop user. The script writes a per-user config and prints
the commands to start the test; it does not start or restart audio services.
Without INTERFACE, prompt interactively (suggested interface: enp0s2).
The default network mode creates a NetworkManager link-local profile without
DHCP, gateway or DNS. Use dhcp for an audio network with a DHCP server, or
existing to preserve the current network configuration. Profiles activate on
connection; this script does not activate them immediately.
PipeWire defaults to 48000 Hz and a fixed quantum of 48 samples (1 ms block).
Use --quantum 64 for a 1.333 ms block. Both settings require hardware testing.
A user PipeWire clock drop-in is also written; restart PipeWire to apply it.
The return defaults to 239.69.150.244; verify that this group is unused.
EOF
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

quantum=48
quantum_explicit=false
network=link-local
network_explicit=false
while [[ ${1:-} == --* || ${1:-} == -h ]]; do
    case $1 in
        --help|-h) usage; exit 0 ;;
        --quantum)
            [[ $# -ge 2 ]] || fail "--quantum requires 48 or 64."
            quantum=$2; quantum_explicit=true; shift 2 ;;
        --network)
            [[ $# -ge 2 ]] || fail "--network requires a mode."
            network=$2; network_explicit=true; shift 2 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
[[ $# -le 2 ]] || { usage >&2; exit 2; }
iface=${1:-}
group=${2:-239.69.150.244}
if [[ -z $iface ]]; then
    [[ -t 0 ]] || fail "Specify INTERFACE when running non-interactively."
    printf 'Available network interfaces:\n'
    ip -brief link
    read -r -p 'AES67 interface [enp0s2]: ' iface || fail "Input cancelled."
    iface=${iface:-enp0s2}
    if [[ $network_explicit == false ]]; then
        read -r -p 'Network mode (link-local/dhcp/existing) [link-local]: ' network || fail "Input cancelled."
        network=${network:-link-local}
    fi
    if [[ $quantum_explicit == false ]]; then
        read -r -p 'PipeWire quantum (48/64 samples) [48]: ' quantum || fail "Input cancelled."
        quantum=${quantum:-48}
    fi
    read -r -p 'Unused return multicast IP [239.69.150.244]: ' group || fail "Input cancelled."
    group=${group:-239.69.150.244}
fi
[[ $quantum == 48 || $quantum == 64 ]] || fail "Quantum must be 48 or 64 samples."
case $network in link-local|dhcp|existing) ;; *) fail "Invalid network mode: $network" ;; esac
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
ip link show dev "$iface" >/dev/null || fail "Interface $iface does not exist. Check ip -brief link."
[[ -d /sys/class/net/$iface/device && ! -d /sys/class/net/$iface/wireless ]] ||
    fail "Select a physical wired interface."
addresses=$(ip -4 -o addr show dev "$iface") || fail "Could not query IPv4 addresses."
if [[ $network == existing && $addresses != *' inet '* ]]; then
    fail "$iface needs an IPv4 address when using --network existing."
fi
caps=$(ethtool -T "$iface") || fail "Could not query timestamping on $iface."
[[ $caps == *hardware-transmit* && $caps == *hardware-receive* &&
   $caps == *hardware-raw-clock* ]] ||
    fail "$iface needs hardware TX/RX timestamping and a PTP hardware clock."
# Resolve the clock through sysfs; ethtool output differs between versions.
clocks=(/sys/class/net/"$iface"/device/ptp/ptp[0-9]*)
[[ ${#clocks[@]} == 1 && -e ${clocks[0]} ]] || fail "Cannot resolve a unique PTP hardware clock."
phc="/dev/${clocks[0]##*/}"
# Grant only this desktop user read access, scoped to the selected PCI NIC.
# Match the stable PCI parent rather than the boot-dependent ptpN number.
command -v setfacl >/dev/null || fail "Missing setfacl. Run tools/install-aes67.sh first."
command -v udevadm >/dev/null || fail "Missing udevadm. Run tools/install-aes67.sh first."
pci=$(basename "$(readlink -f "/sys/class/net/$iface/device")")
[[ $pci =~ ^[[:xdigit:]]{4}:[[:xdigit:]]{2}:[[:xdigit:]]{2}\.[0-7]$ ]] ||
    fail "Cannot resolve the selected NIC PCI address for persistent PTP permissions."
user_id=$(id -u)
rule="/etc/udev/rules.d/90-defeedback-ptp-$pci-$user_id.rules"
rule_tmp=$(mktemp)
trap 'rm -f -- "$rule_tmp"' EXIT
printf 'SUBSYSTEM=="ptp", KERNEL=="ptp[0-9]*", KERNELS=="%s", ACTION=="add|change", RUN+="/usr/bin/setfacl -m u:%s:r /dev/%%k"\n' "$pci" "$user_id" > "$rule_tmp"
if ! cmp -s -- "$rule_tmp" "$rule"; then
    sudo install -m 644 -- "$rule_tmp" "$rule"
    sudo udevadm control --reload-rules
fi
# Apply immediately too; no logout, reboot, or device retrigger is required.
sudo setfacl -m "u:$user_id:r" "$phc"
rm -f -- "$rule_tmp"
trap - EXIT
[[ -r $phc ]] || fail "PTP read access could not be established for $phc."
printf 'Persistent PTP read access configured for user %s on PCI device %s.\n' "$user_id" "$pci"

base=/usr/share/pipewire/pipewire-aes67.conf
[[ -r $base ]] || fail "PipeWire's packaged AES67 config is missing: $base"

if [[ $network != existing ]]; then
    command -v nmcli >/dev/null || fail "NetworkManager (nmcli) is required; use --network existing for another network manager."
    profile="defeedback-aes67-$iface"
    # Never overwrite an existing profile: fail rather than silently changing its settings.
    # The inventory uses column names; setting paths apply only to a named profile.
    profiles=$(nmcli -g NAME connection show) || fail "Could not query NetworkManager."
    if printf '%s\n' "$profiles" | grep -Fxq "$profile"; then
        bound=$(nmcli -g connection.interface-name connection show "$profile")
        method=$(nmcli -g ipv4.method connection show "$profile")
        expected=link-local
        [[ $network != dhcp ]] || expected=auto
        [[ $bound == "$iface" && $method == "$expected" &&
           $(nmcli -g ipv4.never-default connection show "$profile") == yes &&
           -z $(nmcli -g ipv4.gateway connection show "$profile") &&
           -z $(nmcli -g ipv4.dns connection show "$profile") ]] ||
            fail "Existing profile $profile differs; review it in NetworkManager or use --network existing."
    else
        method=link-local
        [[ $network != dhcp ]] || method=auto
        sudo nmcli connection add type ethernet con-name "$profile" ifname "$iface" \
            ipv4.method "$method" ipv4.never-default yes ipv4.ignore-auto-dns yes \
            ipv6.method disabled connection.autoconnect yes
    fi
    printf 'Prepared %s (%s); activate after connecting the audio cable:\n' "$profile" "$network"
    printf '  sudo nmcli connection up %q\n' "$profile"
fi
if [[ $addresses != *' inet '* ]]; then
    printf 'No IPv4 address yet. Configuration can be prepared offline; connect the cable and activate the network profile before starting PTP/audio.\n'
fi

conf_dir="${XDG_CONFIG_HOME:-$HOME/.config}/defeedback"
conf="$conf_dir/pipewire-aes67.conf"
mkdir -p -- "$conf_dir"
tmp=$(mktemp "$conf_dir/.aes67.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT

# Patch only active keys and refuse an unfamiliar upstream layout.
awk -v iface="$iface" -v group="$group" -v quantum="$quantum" '
    /^[[:space:]]*context.properties[[:space:]]*=[[:space:]]*\{/ {
        print
        print "    default.clock.rate = 48000"
        print "    default.clock.allowed-rates = [ 48000 ]"
        print "    default.clock.quantum = " quantum
        print "    default.clock.min-quantum = " quantum
        print "    default.clock.max-quantum = " quantum
        print "    clock.power-of-two-quantum = false"
        properties++
        next
    }
    /^[[:space:]]*(default\.clock\.(rate|allowed-rates|quantum|min-quantum|max-quantum)|clock\.power-of-two-quantum)[[:space:]]*=/ { next }
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
    /^[[:space:]]*audio\.channels[[:space:]]*=/ { sub(/=.*/, "= 8"); channels++ }
    /^[[:space:]]*node\.channel-names[[:space:]]*=/ {
        sub(/=.*/, "= [\"CH1\", \"CH2\", \"CH3\", \"CH4\", \"CH5\", \"CH6\", \"CH7\", \"CH8\"]"); names++
    }
    { print }
    END { if (properties != 1 || clock != 1 || nic != 2 || dst != 1 || socket != 1 || sess != 1 || sink != 1 || channels != 1 || names != 1) exit 1 }
' "$base" > "$tmp" || fail "Unexpected layout in $base; no config was replaced."

mv -- "$tmp" "$conf"
# The JACK client connects to the regular PipeWire server, so set its clock too.
clock_dir="${XDG_CONFIG_HOME:-$HOME/.config}/pipewire/pipewire.conf.d"
mkdir -p -- "$clock_dir"
tmp=$(mktemp "$clock_dir/.defeedback-clock.XXXXXX")
cat > "$tmp" <<EOF
# Managed by setup-aes67.sh. Experimental; validate on the target hardware.
context.properties = {
    default.clock.rate = 48000
    default.clock.allowed-rates = [ 48000 ]
    default.clock.quantum = $quantum
    default.clock.min-quantum = $quantum
    default.clock.max-quantum = $quantum
    clock.power-of-two-quantum = false
}
EOF
mv -- "$tmp" "$clock_dir/90-defeedback-clock.conf"
printf 'PipeWire clock: 48000 Hz, quantum %s. After stopping audio, apply with:\n' "$quantum"
printf '  systemctl --user restart pipewire pipewire-pulse wireplumber\n'
printf 'Verify RATE=48000 and QUANT=%s in pw-top; other local overrides may take precedence.\n' "$quantum"
printf 'Wrote %s. PTP hardware clock: %s.\n\n' "$conf" "$phc"
printf 'Terminal 1 (PTP client, domain 0; use only one ptp4l on this interface):\n'
printf '  sudo ptp4l -i %q -H -4 -E -s -m --domainNumber=0 --uds_address=/run/ptp4l-defeedback --uds_ro_address=/run/ptp4l-defeedbackro\n\n' "$iface"
printf 'Terminal 2 (confirm the port is SLAVE and the expected grandmaster is present):\n'
printf "  pmc -u -b 0 -s /run/ptp4l-defeedbackro 'GET PORT_DATA_SET' 'GET TIME_STATUS_NP'\n\n"
printf 'Terminal 3 (as your desktop user, after PTP lock):\n'
printf '  pipewire -c %q\n' "$conf"
