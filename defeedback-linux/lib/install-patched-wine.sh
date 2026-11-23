#!/usr/bin/env bash
# Install the DirectComposition Wine fork for this user.
set -euo pipefail
umask 077

[[ $# -le 2 ]] || { printf 'Usage: bash install-patched-wine.sh [packages-directory] [true|false]\n' >&2; exit 2; }
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
package_dir=${1:-"$bundle_dir/packages"}
offline=${2:-false}
[[ $offline == true || $offline == false ]] || exit 2
source "$bundle_dir/lib/apt-packages.sh"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 && $EUID -ne 0 ]] ||
    { printf 'Run as your regular user on Ubuntu Studio (Linux x86-64).\n' >&2; exit 1; }

wine_root="$HOME/.local/opt/defeedback-wine-dcomp"
logs_root="${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/wine-dcomp"

mkdir -p -- "$wine_root" "$logs_root"
exec 8>"$wine_root/build.lock"
flock -n 8 || { printf 'A patched Wine build is already running.\n' >&2; exit 1; }
if [[ -x $wine_root/runtime/bin/wine && -x $wine_root/runtime/bin/wineserver &&
      -s $wine_root/runtime/source-revision ]]; then
    printf 'Reusing patched Wine (source revision %s).\n' "$(cat "$wine_root/runtime/source-revision")"
    "$wine_root/runtime/bin/wine" --version
    exit
fi
printf 'Building patched Wine from source. This can take a while.\n'
sudo -v
build_log=$(mktemp "$logs_root/build.XXXXXXXX")
printf 'Build log: %s\n' "$build_log"
(
    if [[ $offline == false ]]; then sudo apt-get update; fi
    install_apt_group build "$package_dir" "$offline"

    if [[ ! -d $wine_root/source ]]; then
        # Extract to a temporary directory so an interrupted extraction can be retried.
        source_stage=$(mktemp -d "$wine_root/source.XXXXXXXX")
        trap 'rm -rf -- "$source_stage"' EXIT
        IFS='|' read -r _ _ wine_archive _ wine_checksum < <(
            awk -F'|' '$1 == "wine" && $2 == "file" { print; exit }' "$bundle_dir/config/resources.conf"
        )
        [[ $wine_archive =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
            { printf 'Invalid Wine archive filename in the manifest.\n' >&2; exit 1; }
        archive="$package_dir/$wine_archive"
        if [[ ! -f $archive ]]; then
            if [[ $offline == true ]]; then
                printf 'Missing the local Wine source archive.\n' >&2
                exit 1
            fi
            bash "$bundle_dir/download-resources.sh" --only wine --output "$source_stage"
            archive="$source_stage/$wine_archive"
        fi
        hash=$(sha256sum < "$archive")
        hash=${hash%% *}
        [[ $wine_checksum == - || $hash == "$wine_checksum" ]] ||
            { printf 'SHA-256 mismatch for the Wine source archive.\n' >&2; exit 1; }
        mkdir "$source_stage/tree"
        tar -xzf "$archive" --strip-components=1 -C "$source_stage/tree"
        [[ -x $source_stage/tree/configure ]] || { printf 'Invalid Wine source archive.\n' >&2; exit 1; }
        printf 'sha256:%s\n' "$hash" > "$source_stage/tree/.defeedback-source-revision"
        mv -T -- "$source_stage/tree" "$wine_root/source"
    fi
    cd -- "$wine_root/source"
    if [[ -f .defeedback-source-revision ]]; then
        revision=$(cat .defeedback-source-revision)
    else
        revision=$(git rev-parse HEAD)
    fi
    printf 'Wine source revision: %s\n' "$revision"
    ./configure --prefix="$wine_root/runtime" --enable-archs=i386,x86_64
    make -j "$(nproc)"
    make install
    "$wine_root/runtime/bin/wine" --version
    printf '%s\n' "$revision" > "$wine_root/runtime/source-revision"
) 2>&1 | tee "$build_log"
