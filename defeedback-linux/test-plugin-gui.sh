#!/usr/bin/env bash
# Compare the De-Feedback editor in native REAPER and Windows VSTHost.
set -euo pipefail
umask 077

usage() {
    cat <<'EOF'
Usage: bash test-plugin-gui.sh [reaper]
       bash test-plugin-gui.sh vsthost /path/to/vsthost.exe

Run one mode at a time from the Ubuntu Studio desktop. Each run saves
host output, session details, and (in REAPER mode) yabridge editor logs
under ${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/gui-tests/.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

mode=${1:-reaper}
case "$mode" in
    --help|-h) usage; exit 0 ;;
    reaper) [[ $# -le 1 ]] || fail 'REAPER mode takes no extra arguments.' ;;
    vsthost) [[ $# -eq 2 ]] || fail 'Pass the path to the 64-bit vsthost.exe.' ;;
    *) usage >&2; exit 2 ;;
esac

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Run on Ubuntu Studio (Linux x86-64).'
(( EUID != 0 )) || fail 'Run as your desktop user without sudo.'
[[ -n ${DISPLAY:-} ]] || fail 'Open a terminal in the graphical desktop session with X11 or XWayland available.'
wine_bin="$HOME/.local/opt/defeedback-wine-dcomp/runtime/bin"
wine="$wine_bin/wine"
[[ -x $wine && -x $wine_bin/wineserver ]] || fail 'Patched Wine is missing. Run setup-defeedback.sh first.'
unset WINEARCH WINEDLLOVERRIDES
export WINELOADER="$wine" WINESERVER="$wine_bin/wineserver"
export PATH="$wine_bin:$PATH"
if pgrep -u "$EUID" -x reaper >/dev/null || pgrep -u "$EUID" -ix vsthost.exe >/dev/null; then
    fail 'Close REAPER and VSTHost before starting this test.'
fi

prefix="$HOME/.wine-defeedback"
[[ -d $prefix/drive_c ]] || fail 'The De-Feedback Wine prefix is missing. Run setup-defeedback.sh first.'
plugin=$(find "$prefix/drive_c" -iname 'defeedback.vst3' -print -quit)
[[ -n $plugin ]] || fail 'De-Feedback is missing from the Wine prefix. Run setup-defeedback.sh first.'
plugin_relative=${plugin#"$prefix/drive_c/"}
windows_plugin="C:\\${plugin_relative//\//\\}"

if [[ $mode == reaper ]]; then
    reaper="$HOME/.local/share/defeedback/bin/reaper"
    [[ -x $reaper ]] || fail 'REAPER is missing. Run setup-defeedback.sh first.'
else
    [[ -f $2 ]] || fail "Cannot find VSTHost: $2"
    vsthost=$(realpath -- "$2")
fi

logs_root="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/gui-tests"
mkdir -p -- "$logs_root"
run_dir=$(mktemp -d "$logs_root/$(date +%Y%m%d-%H%M%S)-$mode.XXXXXXXX")

# Include DirectComposition FIXME messages so unimplemented entry points appear in the log.
wine_debug='-all,err+all,fixme+dcomp,warn+dcomp,warn+d2d,warn+dwrite,warn+dxgi,warn+d3d11,warn+x11drv'
{
    printf 'Mode: %s\nStarted: %s\n' "$mode" "$(date -Is)"
    printf 'Kernel: %s\nWine: %s\n' "$(uname -sr)" "$("$wine" --version 2>&1)"
    printf 'Session type: %s\nX11 display: %s\nWayland display: %s\n' \
        "${XDG_SESSION_TYPE:-unknown}" "$DISPLAY" "${WAYLAND_DISPLAY:-unset}"
    printf 'Wine prefix: %s\nWindows plugin: %s\nWINEDEBUG: %s\n' "$prefix" "$windows_plugin" "$wine_debug"
    if [[ $mode == reaper ]]; then
        printf 'REAPER: %s\nYABRIDGE_DEBUG_LEVEL: 0+editor\n' "$reaper"
    else
        printf 'VSTHost: %s\n' "$vsthost"
    fi
} > "$run_dir/session.log"

finish() {
    local status=$?
    printf 'Finished: %s\nExit status: %s\n' "$(date -Is)" "$status" >> "$run_dir/session.log"
    printf '\nTest logs: %s\n' "$run_dir"
}
trap finish EXIT

printf 'Test logs: %s\n' "$run_dir"
printf '%s\n' 'Use a short test with one plugin instance. Note when the editor turns black or the host hangs.'
if [[ $mode == reaper ]]; then
    printf '%s\n' 'In REAPER, try the generic FX controls and then open and close the graphical editor. Keep your audio settings fixed.'
    env -u WINEPREFIX WINEDEBUG="$wine_debug" YABRIDGE_DEBUG_LEVEL=0+editor \
        YABRIDGE_DEBUG_FILE="$run_dir/yabridge.log" "$reaper" > "$run_dir/host.log" 2>&1
else
    bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    printf 'In VSTHost, open the De-Feedback editor.\n'
    WINEDEBUG="$wine_debug" bash "$bundle_dir/open-license-gui.sh" "$vsthost" > "$run_dir/host.log" 2>&1
fi
