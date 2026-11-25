#!/usr/bin/env bash
# Start optional VSTHost with De-Feedback using patched Wine and the shared prefix.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: defeedback-linux vsthost start [--virtual-desktop]

Optional VSTHost alternative. Standard activation is in REAPER: open the
De-Feedback FX window, click UI, then Options > License Management.
VSTHost is not required for that workflow. Its own license terms apply.

Install this optional host first with defeedback-linux vsthost install.
Opens the installed De-Feedback VST3 in 64-bit VSTHost without an audio
driver. Close REAPER and VSTHost first. No desktop shortcut is created.

Open the De-Feedback editor, then Options > License Management. Follow
the regular De-Feedback / Alpha Labs activation steps for Windows there.
Activation has been confirmed on the reference Beelink Linux workstation.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

virtual_desktop=false
case ${1:-} in
    --help|-h) usage; exit 0 ;;
    --virtual-desktop) virtual_desktop=true; shift ;;
esac
[[ $# -eq 0 ]] || { usage >&2; exit 2; }

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Run on Ubuntu Studio (Linux x86-64).'
(( EUID != 0 )) || fail 'Run as your desktop user without sudo.'
[[ -n ${DISPLAY:-} ]] || fail 'Run in the Ubuntu desktop session with X11 or XWayland available.'
wine_bin="$HOME/.local/opt/defeedback-wine-dcomp/runtime/bin"
wine="$wine_bin/wine"
[[ -x $wine && -x $wine_bin/wineserver ]] || fail 'Patched Wine is missing. Run setup-defeedback.sh first.'
unset WINEARCH WINEDLLOVERRIDES
export WINELOADER="$wine" WINESERVER="$wine_bin/wineserver"
export PATH="$wine_bin:$PATH"
if pgrep -u "$EUID" -x reaper >/dev/null || pgrep -u "$EUID" -ix 'vsthost[.]exe' >/dev/null; then
    fail 'Close REAPER and VSTHost before starting VSTHost.'
fi

vsthost="$HOME/.local/share/defeedback/vsthostx64/vsthost.exe"
[[ -f $vsthost && -f ${vsthost%/*}/license.txt ]] || fail 'VSTHost is not installed. Run defeedback-linux vsthost install first.'
vsthost=$(realpath -- "$vsthost")

export WINEPREFIX="$HOME/.wine-defeedback"
[[ -d $WINEPREFIX/drive_c ]] || fail 'The De-Feedback Wine prefix is missing. Run setup-defeedback.sh first.'
mapfile -d '' -t plugins < <(find "$WINEPREFIX/drive_c" -iname 'defeedback.vst3' -print0 -prune)
[[ ${#plugins[@]} -eq 1 ]] ||
    fail "Expected one De-Feedback VST3 in the Wine prefix. Found: ${#plugins[@]}."
plugin_relative=${plugins[0]#"$WINEPREFIX/drive_c/"}
windows_plugin="C:\\${plugin_relative//\//\\}"

# Enable the patched JUCE renderer for VSTHost.
"$wine" reg add 'HKCU\Software\Wine\AppDefaults\'"${vsthost##*/}" \
    /v HideWineVersion /t REG_SZ /d Y /f >/dev/null

printf '%s\n' 'In the De-Feedback box, click the plug-in edit dial next to the blue info icon.' \
    'Open Options > License Management in the plug-in. Enter your credentials there and click Activate.' \
    'Follow the regular De-Feedback / Alpha Labs activation steps for Windows in that window.' \
    'Wait for the activation prompts to finish before closing the window.'
cd -- "$(dirname -- "$vsthost")"
host_args=(/noaudio /nomidi /noload /nosave "$windows_plugin")
if [[ $virtual_desktop == true ]]; then
    windows_vsthost=$("$wine" winepath -w "$vsthost")
    exec "$wine" explorer /desktop=DefeedbackLicense,1280x900 "$windows_vsthost" "${host_args[@]}"
fi
exec "$wine" "$vsthost" "${host_args[@]}"
