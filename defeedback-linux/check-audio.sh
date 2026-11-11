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
    printf 'Select the Scarlett in REAPER with ALSA at 48 kHz and a block size of 16 samples.\n'
elif [[ $transport == usb ]]; then
    printf 'Select this USB interface for ALSA capture and playback in REAPER. Start at 48 kHz and 128 samples.\n'
else
    printf 'Start at 48 kHz and 128 samples.\n'
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
        exec "$reaper"
    fi
    exec env PIPEWIRE_QUANTUM=128/48000 pw-jack "$reaper"
fi
