#!/usr/bin/env bash
# Build the DirectComposition Wine fork and test the De-Feedback editor in VSTHost.
set -euo pipefail
umask 077

usage() {
    cat <<'HELP'
Usage: bash test-patched-wine.sh build
       bash test-patched-wine.sh {stock|patched} /path/to/vsthost.exe

Build reuses a completed runtime or installs Ubuntu build dependencies
with sudo and builds Wine as
your user under ~/.local/opt/defeedback-wine-dcomp/. The stock and patched
tests each create a fresh Wine prefix and copy the already installed
De-Feedback VST3 from ~/.wine-defeedback. Compare both runs in the same desktop
session with the same 64-bit VSTHost executable. Test the license window without
entering credentials or clicking Activate.
HELP
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

case ${1:-} in
    --help|-h) usage; exit 0 ;;
    build) [[ $# -eq 1 ]] || fail 'Build takes no arguments.' ;;
    stock|patched) [[ $# -eq 2 ]] || fail 'Pass the path to the 64-bit vsthost.exe.' ;;
    *) usage >&2; exit 2 ;;
esac

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Run on Ubuntu Studio (Linux x86-64).'
(( EUID != 0 )) || fail 'Run as your desktop user without sudo.'

wine_root="$HOME/.local/opt/defeedback-wine-dcomp"
logs_root="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/wine-dcomp"

if [[ $1 == build ]]; then
    bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    exec bash "$bundle_dir/../src/install-patched-wine.sh"
fi

mode=$1
[[ -n ${DISPLAY:-} ]] || fail 'Run in a graphical desktop session with X11 or XWayland available.'
[[ -f $2 ]] || fail "Cannot find VSTHost: $2"
host=$(realpath -- "$2")
if [[ $mode == patched ]]; then
    wine="$wine_root/runtime/bin/wine"
    [[ -x $wine && -s $wine_root/runtime/source-revision ]] || fail 'Run the build command first.'
else
    wine=$(type -P wine) || fail 'Wine is missing from PATH.'
fi

original_prefix="$HOME/.wine-defeedback"
[[ -d $original_prefix/drive_c ]] || fail 'The existing De-Feedback Wine prefix is missing.'
plugins=()
while IFS= read -r -d '' plugin; do
    plugins+=("$plugin")
done < <(find "$original_prefix/drive_c" -iname 'defeedback.vst3' -print0 -prune)
[[ ${#plugins[@]} -eq 1 ]] || fail "Expected one installed De-Feedback VST3. Found: ${#plugins[@]}."

mkdir -p -- "$logs_root"
run_dir=$(mktemp -d "$logs_root/$mode.XXXXXXXX")
export WINEPREFIX="$run_dir/prefix"
unset WINEARCH WINELOADER WINESERVER WINEDLLOVERRIDES
export WINEDEBUG='-all,err+all,fixme+dcomp,warn+dcomp,warn+d2d,warn+dwrite,warn+dxgi,warn+d3d11'
printf 'Test logs: %s\n' "$run_dir"
{
    printf 'Mode: %s\nWine: %s\nWine version: %s\n' "$mode" "$wine" "$("$wine" --version)"
    printf 'Session: %s\nDisplay: %s\nVSTHost: %s\n' "${XDG_SESSION_TYPE:-unknown}" "$DISPLAY" "$host"
    if [[ $mode == patched ]]; then
        printf 'Wine source revision: %s\n' "$(cat "$wine_root/runtime/source-revision")"
    fi
} > "$run_dir/session.log"

# Keep the plugin bundle intact and use the same install path for both builds.
plugin_dir='Program Files/Common Files/VST3'
plugin_name=${plugins[0]##*/}
{
    "$wine" wineboot -u
    mkdir -p -- "$WINEPREFIX/drive_c/$plugin_dir"
    cp -R -- "${plugins[0]}" "$WINEPREFIX/drive_c/$plugin_dir/"
    if [[ $mode == patched ]]; then
        # Opt VSTHost into the fork's Direct2D path for JUCE.
        "$wine" reg add 'HKCU\Software\Wine\AppDefaults\'"${host##*/}" \
            /v HideWineVersion /t REG_SZ /d Y /f
    fi
} > "$run_dir/setup.log" 2>&1

printf '%s\n' 'Open the plug-in editor, then Options > License Management.' \
    'Check if the window draws and responds. Close it without activating the license.'
if [[ $mode == patched ]]; then
    wineserver="$wine_root/runtime/bin/wineserver"
else
    wineserver="$(dirname -- "$wine")/wineserver"
fi
printf 'If VSTHost hangs, stop this test from another terminal:\n  WINEPREFIX=%q %q -k\n' "$WINEPREFIX" "$wineserver"

windows_plugin="C:\\${plugin_dir//\//\\}\\$plugin_name"
cd -- "$(dirname -- "$host")"
"$wine" "$host" /noaudio /nomidi /noload /nosave "$windows_plugin" > "$run_dir/host.log" 2>&1
