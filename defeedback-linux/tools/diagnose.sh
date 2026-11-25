#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: defeedback-linux audio diagnose [--usb-card CARD_ID]

Save a local report with system information, ALSA and USB device details,
PipeWire routing, and recent USB audio kernel messages.

  --usb-card CARD_ID  Also test opening device 0 for capture and playback
                      at 48 kHz, stereo, 24-bit. Playback sends silence.
                      Close REAPER first for this direct ALSA test.
  -h, --help          Show this help and exit.

Find CARD_ID in brackets in /proc/asound/cards (for example, SQ).
HELP
}

card=
case ${1:-} in
    -h|--help) usage; exit 0 ;;
    --usb-card)
        if [[ $# -ne 2 || ! $2 =~ ^[[:alnum:]_]+$ ]]; then
            usage >&2
            exit 2
        fi
        card=$2
        ;;
    '') ;;
    *) usage >&2; exit 2 ;;
esac

log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/logs"
mkdir -p -- "$log_dir"
report=$(mktemp "$log_dir/diagnostics-$(date +%Y%m%d-%H%M%S)-log.XXXXXX")
green= yellow= cyan= reset=
if [[ -t 1 && -z ${NO_COLOR:-} && ${TERM:-dumb} != dumb ]]; then
    green=$'\e[32m' yellow=$'\e[33m' cyan=$'\e[36m' reset=$'\e[0m'
fi

warnings=0
check() {
    local title=$1 status
    shift
    printf '%sChecking %s...%s ' "$cyan" "$title" "$reset"
    printf '\n== %s ==\n' "$title" >> "$report"
    if timeout --kill-after=2s 10s "$@" >> "$report" 2>&1; then
        printf '%sOK%s\n' "$green" "$reset"
    else
        status=$?
        warnings=$((warnings + 1))
        printf 'Exit status: %s\n' "$status" >> "$report"
        printf '%sSee report (exit %s)%s\n' "$yellow" "$status" "$reset"
    fi
}

printf 'Diagnostic report: %s\n' "$report"
printf 'Collected at %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" > "$report"
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
integration_cli="$integration_root/bin/defeedback-linux"
[[ -f $integration_cli ]] || integration_cli="$integration_root/defeedback-linux"
check 'integration version' python3 "$integration_cli" --version
check 'OS release' cat /etc/os-release
check 'kernel and architecture' uname -srm
check 'CPU' lscpu
check 'memory' free -h
check 'USB topology' lsusb -t
check 'ALSA cards' cat /proc/asound/cards
check 'ALSA capture devices' arecord -l
check 'ALSA playback devices' aplay -l

shopt -s nullglob
for stream in /proc/asound/card*/stream*; do
    check "USB audio stream $stream" cat "$stream"
done
for params in /proc/asound/card*/pcm*/sub*/hw_params; do
    check "ALSA stream parameters $params" cat "$params"
done

check 'PipeWire devices and streams' wpctl status
check 'PipeWire port connections' pw-link -l
check 'REAPER user service' systemctl --user status defeedback-reaper.service --no-pager
check 'recent REAPER and PipeWire journal' journalctl --user --no-pager -n 100 \
    -u defeedback-reaper.service -u pipewire.service -u wireplumber.service
check 'network interfaces' ip -brief address
check 'recent USB audio kernel messages' journalctl -kb --no-pager -n 100 --grep='usb|snd_usb_audio'

if [[ -n $card ]]; then
    check "ALSA capture from $card" arecord -D "plughw:$card,0" \
        -t raw -c 2 -r 48000 -f S24_3LE -d 2 /dev/null
    check "ALSA silent playback to $card" aplay -D "plughw:$card,0" \
        -t raw -c 2 -r 48000 -f S24_3LE -d 2 /dev/zero
    printf 'The PCM tests check stream access. Verify signal and routing separately.\n'
fi

printf '\nChecks with warnings: %s\nFull report: %s\n' "$warnings" "$report"
