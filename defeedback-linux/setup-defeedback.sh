#!/usr/bin/env bash
# Install native Linux REAPER and use yabridge to load De-Feedback under Wine.
set -euo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

link_command() {
    local target=$1 link="$bin_dir/${1##*/}" previous=${2:-}
    if [[ -L $link && $(readlink -- "$link") == "$target" ]]; then
        return
    fi
    if [[ -n $previous && -L $link && $(readlink -- "$link") == "$previous" ]]; then
        ln -sfnT -- "$target" "$link"
        return
    fi
    if [[ -e $link || -L $link ]]; then
        printf 'Warning: Keeping existing command %s. The installed command is %s.\n' "$link" "$target" >&2
        return
    fi
    ln -sT -- "$target" "$link"
}

install_launcher() {
    local applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    local id=$1 name=$2 desktop_exec=$3 comment=$4
    local entry="$work_dir/defeedback-$id.desktop"

    # Escape the quoted Exec argument, then escape backslashes for the desktop file.
    desktop_exec=${desktop_exec//\\/\\\\}
    desktop_exec=${desktop_exec//\"/\\\"}
    desktop_exec=${desktop_exec//\$/\\\$}
    desktop_exec=${desktop_exec//\`/\\\`}
    desktop_exec=${desktop_exec//%/%%}
    desktop_exec=${desktop_exec//\\/\\\\}
    mkdir -p -- "$applications_dir"
    cat > "$entry" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Comment=$comment
Exec="$desktop_exec"
Icon=audio-x-generic
Terminal=false
Categories=AudioVideo;Audio;
EOF
    install -m 644 -- "$entry" "$applications_dir/defeedback-$id.desktop"
    install -Dm 755 -- "$entry" "$desktop_dir/defeedback-$id.desktop"
}

usage='Usage: bash setup-defeedback.sh [--offline] [--appliance] [--import-vst3] [packages-directory]'
import_vst3=false
appliance=false
offline=false
while [[ ${1:-} == -* ]]; do
    case $1 in
        --help|-h)
            printf '%s\n\n' "$usage"
            cat <<'EOF'
Install native Linux REAPER and configure yabridge and patched Wine to load
the Windows De-Feedback VST3. Run from a desktop terminal on Ubuntu Studio
(x86-64) as your regular user. Close REAPER and VSTHost first.

Default installation
  Place the official Windows installer, DefeedbackSetup.exe, in packages/.
  For a new plugin installation, setup opens that installer through Wine.
  Setup can fetch missing REAPER, yabridge, Wine, and APT resources online.
  Activate in REAPER: open De-Feedback FX, click UI, then Options > License Management.
  VSTHost is optional: use defeedback-linux install vsthost, then start vsthost.

Options
  -h, --help       Show this help and exit.
  --offline        Use prepared local resources and APT archives. Prepare
                   them with 'bash download-resources.sh --apt' on a
                   connected machine running the same Ubuntu release.
                   Supply the De-Feedback installer separately.
  --import-vst3    Import Defeedback.vst3 from the package directory for a
                   new plugin installation. Extract it beforehand using
                   the official Windows installer.
  --appliance      Configure the workstation for dedicated use, including
                   automatic login, REAPER autostart, and power settings.
                   Run as the user who should log in automatically.

Package directory
  The optional packages-directory argument points to an existing directory
  containing the installer and any prepared archives. It defaults to the
  packages/ directory next to this script. Put options before the directory.

Logs
  Each installation run saves a timestamped log under
  ${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/logs/.
  The terminal prints the exact path.

Examples
  bash setup-defeedback.sh
  bash setup-defeedback.sh --offline /path/to/prepared-packages
  bash setup-defeedback.sh --import-vst3 /path/to/packages
  bash setup-defeedback.sh --appliance
EOF
            exit 0
            ;;
        --import-vst3) import_vst3=true ;;
        --appliance) appliance=true ;;
        --offline) offline=true ;;
        *) fail "$usage" ;;
    esac
    shift
done
[[ $# -le 1 ]] || fail "$usage"
# The Windows installer opens a GUI, and the tools and plugin belong to the desktop user.
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Run this script on Ubuntu Studio (Linux x86-64).'
[[ $EUID -ne 0 ]] || fail 'Run as your regular user. The script uses sudo for APT.'
[[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || fail 'Open a terminal in the Ubuntu Studio desktop session.'
command -v apt-get >/dev/null || fail 'This script requires APT on Ubuntu Studio.'
if pgrep -u "$EUID" -ix reaper >/dev/null || pgrep -u "$EUID" -ix 'vsthost[.]exe' >/dev/null; then
    fail 'Close REAPER and VSTHost before running setup.'
fi

log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/logs"
mkdir -p -- "$log_dir"
setup_log=$(mktemp "$log_dir/setup-$(date +%Y%m%d-%H%M%S)-log.XXXXXX")
color=
reset=
if [[ -t 1 && -z ${NO_COLOR:-} && ${TERM:-dumb} != dumb ]]; then
    color=$'\e[1;36m'
    reset=$'\e[0m'
fi
exec 8>&1
exec > >(tee -a -- "$setup_log" >&8 8>&-) 2>&1
log_pid=$!

finish_setup() {
    local status=$1
    if (( status == 0 )); then
        printf '\nSetup finished. Log: %s\n' "$setup_log"
    else
        printf '\nSetup exited with status %s. See log: %s\n' "$status" "$setup_log"
    fi
    exec 1>&8 2>&8 8>&-
    wait "$log_pid" || printf 'Warning: Could not finish writing the setup log.\n' >&2
}
trap 'finish_setup "$?"' EXIT

stage() {
    printf '\n%s== %s ==%s\n' "$color" "$1" "$reset"
}

printf 'Setup log: %s\n' "$setup_log"

# Resolve the bundled packages relative to this script, regardless of where it was started.
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
package_dir=$(cd -- "${1:-$bundle_dir/packages}" && pwd) || fail 'The package directory does not exist.'
source "$bundle_dir/lib/apt-packages.sh"
# A custom archive directory can still use the bundled Windows installer.
plugin_installer="$package_dir/DefeedbackSetup.exe"
[[ -f $plugin_installer ]] || plugin_installer="$bundle_dir/packages/DefeedbackSetup.exe"
plugin_source="$package_dir/Defeedback.vst3"

reaper_dir="$HOME/.local/opt/REAPER"
yabridge_dir="$HOME/.local/share/yabridge"
prefix="$HOME/.wine-defeedback"
bin_dir="$HOME/.local/bin"
app_dir="$HOME/.local/share/defeedback"
wine_bin="$HOME/.local/opt/defeedback-wine-dcomp/runtime/bin"
wine="$wine_bin/wine"
mkdir -p -- "$HOME/.local/opt" "$HOME/.local/share" "$bin_dir"
# Hold a per-user lock on file descriptor 9 while setup runs.
exec 9>"$HOME/.local/share/defeedback-setup.lock"
flock -n 9 || fail 'Setup is already running for this user.'
# Stage downloads and extracted files here. Remove the staging area on exit.
work_dir=$(mktemp -d "$HOME/.local/share/defeedback-setup.XXXXXXXX")
wine_work_dir=
cleanup() {
    rm -rf -- "$work_dir"
    if [[ -n $wine_work_dir ]]; then
        rm -rf -- "$wine_work_dir"
    fi
}
trap 'status=$?; cleanup || true; finish_setup "$status"' EXIT

stage 'Ubuntu packages'
# PipeWire supplies the JACK interface for AES67.
install_apt_group runtime "$package_dir" "$offline"

desktop_dir=$(xdg-user-dir DESKTOP 2>/dev/null || true)
if [[ $desktop_dir != /* || $desktop_dir == "$HOME" ]]; then
    desktop_dir="$HOME/Desktop"
fi

stage 'Patched Wine'
bash "$bundle_dir/lib/install-patched-wine.sh" "$package_dir" "$offline" 9>&-
# Keep the system Wine available outside this setup and the installed launchers.
unset WINEARCH WINEPREFIX WINEDLLOVERRIDES
export WINELOADER="$wine" WINESERVER="$wine_bin/wineserver"
export PATH="$wine_bin:$PATH"

# Reuse installed REAPER. Otherwise prefer a local archive over the pinned download.
if [[ ! -x $reaper_dir/reaper ]]; then
    [[ ! -e $reaper_dir ]] || fail "Check the existing REAPER directory: $reaper_dir"
    stage 'Installing REAPER'
    # With nullglob enabled, a missing archive leaves the array empty.
    shopt -s nullglob
    reaper_archives=("$package_dir"/reaper*_linux_x86_64.tar.xz)
    shopt -u nullglob
    [[ ${#reaper_archives[@]} -le 1 ]] || fail 'Keep one REAPER x86-64 archive in the package directory.'
    IFS='|' read -r _ _ reaper_file _ reaper_checksum < <(
        awk -F'|' '$1 == "reaper" && $2 == "file" { print; exit }' "$bundle_dir/config/resources.conf"
    )
    reaper_archive=${reaper_archives[0]:-"$work_dir/$reaper_file"}
    if [[ ! -f $reaper_archive ]]; then
        [[ $offline == false ]] || fail 'Missing the local REAPER archive.'
        bash "$bundle_dir/download-resources.sh" --only reaper --output "$work_dir"
    fi
    # This checksum covers the pinned release, including a local copy with the same name.
    if [[ ${reaper_archive##*/} == "$reaper_file" && $reaper_checksum != - ]]; then
        printf '%s  %s\n' "$reaper_checksum" "$reaper_archive" | sha256sum --check
    fi
    tar -xJf "$reaper_archive" -C "$work_dir"
    [[ -x $work_dir/reaper_linux_x86_64/REAPER/reaper ]] || fail 'The REAPER archive has an unexpected layout.'
    mv -T -- "$work_dir/reaper_linux_x86_64/REAPER" "$reaper_dir"
fi
if [[ :$PATH: != *":$bin_dir:"* ]]; then
    # New Konsole tabs may inherit a PATH from before .local/bin was created.
    shell_rc_files=("$HOME/.bashrc")
    if [[ ${SHELL:-} == */zsh ]]; then
        shell_rc_files+=("${ZDOTDIR:-$HOME}/.zshrc")
    fi
    for shell_rc in "${shell_rc_files[@]}"; do
        if [[ -f $shell_rc ]] && grep -Fxq '# De-Feedback setup: local commands' "$shell_rc"; then
            continue
        fi
        cat >> "$shell_rc" <<'EOF'

# De-Feedback setup: local commands
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
EOF
    done
    printf '%s\n' 'Open a new terminal, or run: export PATH="$HOME/.local/bin:$PATH"'
fi

# Prefer an extracted local build, then local archives, then a development build.
if [[ ! -x $yabridge_dir/yabridgectl ]]; then
    [[ ! -e $yabridge_dir ]] || fail "Check the existing yabridge directory: $yabridge_dir"
    stage 'Installing yabridge'
    if [[ -x $package_dir/yabridge/yabridgectl ]]; then
        cp -a -- "$package_dir/yabridge" "$work_dir/yabridge"
    else
        shopt -s nullglob
        bridge_archives=("$package_dir"/yabridge-*.tar.gz "$package_dir"/yabridge-*.tar.gz.zip)
        ctl_archives=("$package_dir"/yabridgectl-*.tar.gz "$package_dir"/yabridgectl-*.tar.gz.zip)
        shopt -u nullglob
        [[ ${#bridge_archives[@]} -le 1 && ${#ctl_archives[@]} -le 1 ]] || fail 'Keep one yabridge build and its matching yabridgectl archive in the package directory.'
        if [[ ${#bridge_archives[@]} -eq 0 ]]; then
            [[ ${#ctl_archives[@]} -eq 0 ]] || fail 'Add the yabridge archive that matches your local yabridgectl.'
            [[ $offline == false ]] || fail 'Missing the local yabridge package.'
            bash "$bundle_dir/download-resources.sh" --only yabridge --output "$work_dir"
            shopt -s nullglob
            bridge_archives=("$work_dir"/yabridge-*.tar.gz "$work_dir"/yabridge-*.tar.gz.zip)
            ctl_archives=("$work_dir"/yabridgectl-*.tar.gz "$work_dir"/yabridgectl-*.tar.gz.zip)
            shopt -u nullglob
        fi
        [[ ${#bridge_archives[@]} -eq 1 && ${#ctl_archives[@]} -le 1 ]] ||
            fail 'Expected one yabridge archive and at most one matching yabridgectl archive.'
        if [[ ${#ctl_archives[@]} -eq 1 ]]; then
            bridge_name=${bridge_archives[0]##*/}
            ctl_name=${ctl_archives[0]##*/}
            bridge_name=${bridge_name%.zip}
            [[ ${ctl_name%.zip} == "yabridgectl-${bridge_name#yabridge-}" ]] ||
                fail 'The yabridge and yabridgectl archives must come from the same build.'
        fi
        for archive in "${bridge_archives[@]}" "${ctl_archives[@]}"; do
            # The GitHub Actions ZIP contains a tarball. Local tarballs can be unpacked directly.
            if [[ $archive == *.zip ]]; then
                tar_name=${archive##*/}
                tar_name=${tar_name%.zip}
                unzip -p "$archive" "$tar_name" > "$work_dir/$tar_name"
                archive="$work_dir/$tar_name"
            fi
            tar -xzf "$archive" -C "$work_dir"
        done
        if [[ -x $work_dir/yabridgectl/yabridgectl ]]; then
            install -m 755 "$work_dir/yabridgectl/yabridgectl" "$work_dir/yabridge/yabridgectl"
        fi
    fi
    [[ -x $work_dir/yabridge/yabridgectl && -f $work_dir/yabridge/libyabridge-vst3.so ]] || fail 'The yabridge build is incomplete. Add the matching yabridgectl archive if needed.'
    mv -T -- "$work_dir/yabridge" "$yabridge_dir"
fi
link_command "$yabridge_dir/yabridgectl"

stage 'Installing and registering De-Feedback'
# Use a dedicated Wine prefix (Windows environment) for the plugin. Close the
# lock descriptor in Wine commands so background processes cannot retain it.
if [[ $offline == true ]]; then
    # Skip the Wine Mono and Gecko bootstrap downloads in an offline install.
    WINEDLLOVERRIDES='mscoree,mshtml=' WINEPREFIX="$prefix" "$wine" wineboot -u 9>&-
else
    WINEPREFIX="$prefix" "$wine" wineboot -u 9>&-
fi
# A VST3 can be a directory bundle. Match its outer path and skip its contents.
mapfile -d '' -t plugins < <(find "$prefix/drive_c" -iname 'defeedback.vst3' -print0 -prune)
if [[ ${#plugins[@]} -eq 0 ]]; then
    vst3_dir="$prefix/drive_c/Program Files/Common Files/VST3"
    mkdir -p -- "$vst3_dir"
    wine_work_dir=$(mktemp -d "$prefix/drive_c/defeedback-setup.XXXXXXXX")
    if [[ $import_vst3 == true ]]; then
        [[ -f $plugin_source || -d $plugin_source ]] ||
            fail "Place your extracted Windows Defeedback.vst3 in $package_dir to use --import-vst3."
        # Stage the Windows plugin before moving it into the VST3 directory.
        cp -aHT -- "$plugin_source" "$wine_work_dir/Defeedback.vst3"
        mv -T -- "$wine_work_dir/Defeedback.vst3" "$vst3_dir/Defeedback.vst3"
    else
        [[ -f $plugin_installer ]] || fail "Place DefeedbackSetup.exe in $package_dir to run the official installer."
        # Keep a Desktop extraction inside the prefix so setup can find it.
        for desktop in "$prefix"/drive_c/users/*/Desktop; do
            if [[ -L $desktop ]]; then
                unlink -- "$desktop"
                mkdir -- "$desktop"
            fi
        done
        # Launch from a writable folder on C: and set the Windows temp paths
        # inside cmd.exe so they apply to the installer for this run only.
        cp -- "$plugin_installer" "$wine_work_dir/DefeedbackSetup.exe"
        printf '%s\r\n' '@echo off' 'set "TEMP=%~dp0"' 'set "TMP=%~dp0"' '"%~dp0DefeedbackSetup.exe"' > "$wine_work_dir/install.cmd"
        state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback"
        mkdir -p -- "$state_dir"
        installer_log="$state_dir/wine-installer.log"
        printf '%s\n' \
            'Click Extract in the Alpha Labs installer.' \
            'Read the license terms in the separate window and click Accept if you agree.' \
            'In Browse for Folder, select C:\Program Files\Common Files\VST3 and click OK.' \
            'When extraction succeeds, dismiss the confirmation and close the installer to continue setup.'
        if ! (cd -- "$wine_work_dir" && WINEPREFIX="$prefix" "$wine" cmd.exe /d /c "C:\\${wine_work_dir##*/}\\install.cmd" 9>&-) 2>&1 | tee "$installer_log"; then
            fail "The Wine installer failed. See $installer_log. To use your own Windows extraction, copy Defeedback.vst3 into $package_dir and rerun with --import-vst3."
        fi
    fi
    # Do not count any temporary VST3 files left by the installer.
    rm -rf -- "$wine_work_dir"
    wine_work_dir=
    mapfile -d '' -t plugins < <(find "$prefix/drive_c" -iname 'defeedback.vst3' -print0 -prune)
    if [[ ${#plugins[@]} -eq 0 && -n ${installer_log:-} ]]; then
        fail "The installer did not leave a plugin in the Wine C: drive. See $installer_log. To use your own Windows extraction, copy Defeedback.vst3 into $package_dir and rerun with --import-vst3."
    fi
fi
[[ ${#plugins[@]} -eq 1 ]] || fail "Expected exactly one Defeedback.vst3 in $prefix/drive_c. Found: ${#plugins[@]}."

# Register the Windows plugin directory, then generate the Linux VST3 wrapper.
yabridgectl="$yabridge_dir/yabridgectl"
plugin_dir=$(dirname -- "${plugins[0]}")
"$yabridgectl" add "$plugin_dir"
# Let yabridge infer the Wine prefix from the plugin path.
env -u WINEPREFIX "$yabridgectl" sync 9>&-
[[ -n $(find "$HOME/.vst3/yabridge" -type f -iname 'defeedback.so' -print -quit 2>/dev/null) ]] || fail 'Yabridge did not create a De-Feedback VST3 module in ~/.vst3/yabridge.'
"$yabridgectl" status

# JUCE can select the patched Direct2D renderer in these Windows host processes.
for host in "$yabridge_dir"/yabridge-host*.exe; do
    [[ -f $host ]] || continue
    WINEPREFIX="$prefix" "$wine" reg add 'HKCU\Software\Wine\AppDefaults\'"${host##*/}" \
        /v HideWineVersion /t REG_SZ /d Y /f 9>&-
done

stage 'Launchers and REAPER profiles'
# Share the integration installer with the bundle updater.
python3 - "$bundle_dir" "$app_dir" "$reaper_dir" "$work_dir/integration-backup" <<'PYINSTALL'
import importlib.util
from pathlib import Path
import sys
bundle, app, runtime, backup = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('defeedback_update', bundle / 'lib/update-defeedback.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.install(None, runtime, app, backup)
PYINSTALL
link_command "$app_dir/bin/reaper" "$reaper_dir/reaper"
install_launcher reaper 'De-Feedback Linux — unofficial integration' "$app_dir/bin/defeedback-linux" 'Unofficial Linux integration for the Alpha Labs De-Feedback plugin'

if command -v wpctl >/dev/null && wpctl set-volume @DEFAULT_AUDIO_SINK@ 100%; then
    printf '\nSystem output volume set to 100%%.\n'
else
    printf '\nWarning: Could not set the default system output volume to 100%%.\n' >&2
fi

printf '\nOpen REAPER from the desktop, applications menu, or run reaper in a new terminal.\n'
printf '%s\n' 'The launcher detects supported USB devices and applies 48000 Hz, 64 samples, 24-bit, and 3 periods.' \
    'It creates the mono routing project on first launch and reopens it on later launches.' \
    'To activate De-Feedback, open its FX window, click UI, then Options > License Management.' \
    'Run reaper --detect to inspect device selection. If De-Feedback is missing, scan ~/.vst3 in REAPER.'

if [[ $appliance == true ]]; then
    bash "$bundle_dir/tools/setup-appliance.sh"
else
    # Migrate the old managed service even when only reinstalling the application.
    unit="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/defeedback-reaper.service"
    if [[ -f $unit ]] && grep -Fxq 'ExecStart="%h/.local/opt/REAPER/reaper"' "$unit"; then
        sed 's|^ExecStart="%h/\.local/opt/REAPER/reaper"$|ExecStart="%h/.local/share/defeedback/bin/reaper"|' \
            "$unit" > "$work_dir/defeedback-reaper.service"
        install -m 644 -- "$work_dir/defeedback-reaper.service" "$unit"
        systemctl --user daemon-reload
    fi
fi
