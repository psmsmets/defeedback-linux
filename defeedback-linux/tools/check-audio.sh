#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: bash check-audio.sh [focusrite|sq|cq|avantis|dlive] [--launch]\n'
    printf 'The default profile is focusrite. Use --launch as the second argument to start REAPER.\n'
}

case ${1:-focusrite} in
    -h|--help) usage; exit 0 ;;
    focusrite) profile='Focusrite Scarlett USB'; transport=usb ;;
    sq) profile='Allen & Heath SQ USB-B'; transport=usb ;;
    cq) profile='Allen & Heath CQ USB-B'; transport=usb ;;
    avantis) profile='Allen & Heath Avantis AES67'; transport=aes67 ;;
    dlive) profile='Allen & Heath dLive AES67'; transport=aes67 ;;
    *) usage >&2; exit 2 ;;
esac

if [[ $# -gt 2 || ( $# -eq 2 && $2 != --launch ) ]]; then
    usage >&2
    exit 2
fi

printf '%s\n' "$profile"
if [[ ${1:-focusrite} == focusrite ]]; then
    printf 'Select the Scarlett in REAPER with ALSA. Use 48000 Hz, 64 samples, 24-bit, 3 periods, and RT priority 50.\n'
elif [[ ${1:-focusrite} == cq ]]; then
    printf 'Select the CQ for ALSA capture and playback in REAPER. CQ12T uses hw:CQ12T. Use 48000 Hz, 64 samples, 24-bit, and 3 periods. Confirm the device identifier on other CQ models.\n'
elif [[ $transport == usb ]]; then
    printf 'Select this USB interface for ALSA capture and playback in REAPER. Start at 48 kHz and 128 samples.\n'
else
    printf 'Use the configured PipeWire clock: 48 kHz, quantum 48 by default or 64 for testing.\n'
fi
printf 'Test one mono path in bypass first.\n'

if [[ $transport == usb ]]; then
    printf '\nALSA capture devices\n'
    arecord -l
    printf '\nALSA playback devices\n'
    aplay -l
else
    printf '\nNetwork interfaces\n'
    ip -brief link
    printf 'Check PTP lock and both AES67 streams in your AES67 stack.\n'
fi

printf '\nPipeWire sources and sinks\n'
wpctl status
printf '\nPipeWire connections\n'
pw-link -l
if [[ ${1:-focusrite} != focusrite ]]; then
    printf '\nRun pw-top during playback and check RATE, QUANT, and ERR on the active audio driver.\n'
fi

if [[ ${2:-} == --launch ]]; then
    reaper="$HOME/.local/share/defeedback/bin/reaper"
    if [[ ! -x $reaper ]]; then
        printf 'Error: REAPER was not found at %s. Run setup-defeedback.sh first.\n' "$reaper" >&2
        exit 1
    fi
    if [[ $transport == usb ]]; then
        exec "$reaper" --device "${1:-focusrite}"
    fi
    # Refuse the raw launch unless the AES67 return and a received source exist.
    if ! command -v pw-dump >/dev/null || ! command -v pw-jack >/dev/null; then
        printf 'AES67 startup skipped: PipeWire tools are not installed.\n'
        exit 0
    fi
    if ! pw-dump | python3 -c '
import json, sys
nodes = [item.get("info", {}).get("props", {}) for item in json.load(sys.stdin)]
ready = any(p.get("node.name") == "defeedback-aes67-return" for p in nodes)
ready = ready and any(p.get("device.api") == "aes67" and p.get("media.class") == "Audio/Source" for p in nodes)
sys.exit(0 if ready else 1)
'; then
        printf 'AES67 startup skipped: no AES67 source and return available. Start PTP and the AES67 helper first.\n'
        exit 0
    fi
    # Use the clock configured by setup-aes67.sh; do not override it with 128 samples.
    exec pw-jack "$reaper" --raw
fi
