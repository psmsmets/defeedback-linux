#!/usr/bin/env bash
# Remove optional desktop applications from a dedicated De-Feedback workstation.
set -euo pipefail
apply=false
case ${1:---check} in
    --check) ;;
    --apply) apply=true ;;
    -h|--help)
        printf '%s\n' 'Usage: bash tools/trim-workstation.sh [--check|--apply]' \
            'Preview removal by default. --apply removes the listed applications.' \
            'Run on Ubuntu Studio as the regular workstation user.'
        exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { printf 'Too many arguments.\n' >&2; exit 2; }
[[ $(uname -s) == Linux && $EUID -ne 0 ]] || {
    printf 'Run as the regular user on Ubuntu Studio.\n' >&2; exit 1;
}
command -v apt-get >/dev/null
command -v dpkg-query >/dev/null
# Resolve only installed application packages for the dedicated workstation.
installed=$(dpkg-query -W -f='${db:Status-Status} ${binary:Package}\n')
packages=()
while read -r status package; do
    [[ $status == installed ]] || continue
    name=${package%%:*}
    case $name in
        firefox|firefox-*|thunderbird|thunderbird-*|libreoffice|libreoffice-*|\
        blender|gimp|gimp-*|krita|inkscape|scribus|kdenlive|kdenlive-*|\
        darktable|digikam|digikam-*|rawtherapee|shotwell|pitivi|\
        transmission-gtk|transmission-qt|ktorrent|kdeconnect|\
        ardour|ardour-*|audacity|audacity-*|carla|carla-*|hydrogen|hydrogen-*|\
        qtractor|rosegarden|muse|musescore|musescore-*|lmms|lmms-*|\
        yoshimi|yoshimi-*|qsynth)
            packages+=("$package") ;;
    esac
done <<< "$installed"
snaps=()
if command -v snap >/dev/null; then
    if snap_list=$(snap list 2>/dev/null); then
        while read -r name _; do
            case $name in firefox|thunderbird) snaps+=("$name") ;; esac
        done <<< "$snap_list"
    else
        printf 'Snap inventory is unavailable. Check snap list separately.\n' >&2
        if $apply; then exit 1; fi
    fi
fi
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/logs"
mkdir -p -- "$state_dir"
report=$(mktemp "$state_dir/trim-$(date +%Y%m%d-%H%M%S).XXXXXX")
if (( ${#packages[@]} > 0 )); then
    # Validate the full dependency resolution, including implicit removals.
    LC_ALL=C apt-get --simulate remove -- "${packages[@]}" > "$report"
    cat -- "$report"
    while read -r action package _; do
        [[ $action == Remv ]] || continue
        name=${package%%:*}
        case $name in
            plasma-desktop|plasma-workspace*|sddm*|pipewire*|wireplumber*|\
            libpipewire*|libspa-*|jackd*|libjack*|alsa-*|libasound*|\
            wine*|libwine*|yabridge*|reaper*|linux-*|systemd*|udev|\
            network-manager*|sudo|apt|dpkg|python3*|libpython3*|bash|\
            kwin*|xserver-xorg*|libgl*|libegl*|libvulkan*|libx11*|\
            libgtk*|openssh*|libc6*|libstdc++*|libgcc*|libqt*|polkit*)
                printf 'Removal would affect a workstation runtime package: %s. See %s\n' "$package" "$report" >&2
                exit 1 ;;
        esac
    done < "$report"
fi
for name in "${snaps[@]}"; do
    printf 'Snap application to remove: %s\n' "$name" | tee -a "$report"
done
printf 'Removal plan: %s\n' "$report"
if ! $apply; then
    printf 'Preview complete. Run with --apply to remove these applications.\n'
    exit 0
fi
if (( ${#packages[@]} > 0 )); then
    sudo apt-get remove -y -- "${packages[@]}"
fi
for name in "${snaps[@]}"; do
    # Snap normally saves a recoverable data snapshot when removing an app.
    sudo snap remove "$name"
done
printf 'Application cleanup completed.\n'
