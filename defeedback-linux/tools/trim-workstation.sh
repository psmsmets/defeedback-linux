#!/usr/bin/env bash
# Remove optional desktop applications from a dedicated De-Feedback workstation.
set -euo pipefail
apply=false
autoremove=false
mode=
for option in "$@"; do
    case $option in
        --check|--apply)
            [[ -z $mode ]] || { printf 'Choose either --check or --apply once.\n' >&2; exit 2; }
            mode=$option
            [[ $option != --apply ]] || apply=true ;;
        --autoremove) autoremove=true ;;
        -h|--help)
            printf '%s\n' 'Usage: defeedback-linux trim [--check|--apply] [--autoremove]' \
                'Preview removal by default. --apply removes the listed applications.' \
                '--autoremove also removes unused automatic dependencies, with the same runtime protection.' \
                'Run on Ubuntu Studio as the regular workstation user.'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$option" >&2; exit 2 ;;
    esac
done
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
apt_action=(remove)
if $autoremove; then
    # Resolve application removal and orphan cleanup in the same transaction.
    apt_action=(autoremove)
fi
if (( ${#packages[@]} > 0 )) || $autoremove; then
    # Validate the full dependency resolution, including implicit removals.
    LC_ALL=C apt-get --simulate "${apt_action[@]}" -- ${packages[@]+"${packages[@]}"} > "$report"
    cat -- "$report"
    while read -r action package _; do
        [[ $action == Remv ]] || continue
        name=${package%%:*}
        case $name in
            plasma-desktop|plasma-workspace*|sddm*|pipewire*|wireplumber*|\
            libpipewire*|libspa-*|jackd*|libjack*|alsa-*|libasound*|\
            wine*|libwine*|yabridge*|reaper*|linux-*|systemd*|udev|\
            network-manager*|linuxptp|ethtool|iproute2|acl|sudo|apt|dpkg|python3*|libpython3*|bash|\
            kwin*|xserver-xorg*|libgl*|libegl*|libvulkan*|libx11*|\
            libgtk*|openssh*|libc6*|libstdc++*|libgcc*|libqt*|polkit*)
                printf 'Removal would affect a workstation runtime package: %s. See %s\n' "$package" "$report" >&2
                exit 1 ;;
        esac
    done < "$report"
fi
for name in ${snaps[@]+"${snaps[@]}"}; do
    printf 'Snap application to remove: %s\n' "$name" | tee -a "$report"
done
printf 'Removal plan: %s\n' "$report"
if ! $apply; then
    printf 'Preview complete. Run with --apply and the same optional --autoremove flag to apply this plan.\n'
    exit 0
fi
if (( ${#packages[@]} > 0 )) || $autoremove; then
    sudo apt-get "${apt_action[@]}" -y -- ${packages[@]+"${packages[@]}"}
fi
for name in ${snaps[@]+"${snaps[@]}"}; do
    # Snap normally saves a recoverable data snapshot when removing an app.
    sudo snap remove "$name"
done
printf 'Application cleanup completed.\n'
