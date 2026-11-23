# Shared APT package groups for installation and offline preparation.
apt_package_names() {
    awk -v group="$1" '$1 == group { for (i = 2; i <= NF; i++) print $i }' "$bundle_dir/config/apt-packages.conf"
}

apt_target_id() {
    [[ -r /etc/os-release ]] || return 1
    (
        . /etc/os-release
        [[ ${ID:-} == ubuntu && -n ${VERSION_CODENAME:-} && $(dpkg --print-architecture) == amd64 ]] || return 1
        printf '%s %s\n' "$VERSION_CODENAME" amd64
    )
}

install_apt_group() {
    local group=$1 package_dir=$2 offline=$3
    local -a packages
    mapfile -t packages < <(apt_package_names "$group")
    if [[ $offline == true ]]; then
        local target_id
        target_id=$(apt_target_id) || { printf 'Offline APT install requires Ubuntu amd64.\n' >&2; return 1; }
        if [[ ! -f $package_dir/apt/target || $(cat "$package_dir/apt/target") != "$target_id" ]]; then
            printf 'Prepare APT packages for %s with download-resources.sh --apt.\n' "$target_id" >&2
            return 1
        fi
        local LC_ALL=C
        shopt -s nullglob
        local -a archives=("$package_dir/apt/$group/"*.deb)
        shopt -u nullglob
        if (( ${#archives[@]} == 0 )); then
            printf 'Missing offline APT archives for %s.\n' "$group" >&2
            return 1
        fi
        if [[ ! -s $package_dir/apt/$group/SHA256SUMS ]]; then
            printf 'Missing offline APT checksums for %s.\n' "$group" >&2
            return 1
        fi
        # Verify every archive that will be passed to APT, including any extra files.
        local archive
        local -a archive_names=()
        for archive in "${archives[@]}"; do archive_names+=("${archive##*/}"); done
        if ! (cd -- "$package_dir/apt/$group" &&
              sha256sum -- "${archive_names[@]}" | cmp -s - SHA256SUMS); then
            printf 'Offline APT archives do not match the prepared %s checksums.\n' "$group" >&2
            return 1
        fi
        sudo apt-get -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- \
            --no-download --no-install-recommends install -y "${archives[@]}"
    else
        sudo apt-get install -y "${packages[@]}"
    fi
}
