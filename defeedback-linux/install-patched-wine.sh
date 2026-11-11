#!/usr/bin/env bash
# Install the DirectComposition Wine fork for this user.
set -euo pipefail
umask 077

[[ $# -eq 0 ]] || { printf 'Usage: bash install-patched-wine.sh\n' >&2; exit 2; }
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
    sudo apt update
    sudo apt install build-essential git flex bison pkg-config \
        gcc-mingw-w64-i686 gcc-mingw-w64-x86-64 \
        libx11-dev libxext-dev libxcursor-dev libxi-dev libxrandr-dev \
        libxrender-dev libxfixes-dev libxinerama-dev libxxf86vm-dev \
        libxdamage-dev libxcomposite-dev libxkbcommon-dev \
        libgl-dev libvulkan-dev libfreetype-dev libfontconfig-dev \
        libasound2-dev libpulse-dev libdbus-1-dev libgnutls28-dev
    if [[ ! -d $wine_root/source ]]; then
        git clone --depth 1 --branch d2d1-dcomp-11.0 \
            https://github.com/giang17/wine.git "$wine_root/source"
    fi
    cd -- "$wine_root/source"
    git rev-parse HEAD
    ./configure --prefix="$wine_root/runtime" --enable-archs=i386,x86_64
    make -j "$(nproc)"
    make install
    "$wine_root/runtime/bin/wine" --version
    git rev-parse HEAD > "$wine_root/runtime/source-revision"
) 2>&1 | tee "$build_log"
