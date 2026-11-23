#!/usr/bin/env bash
# Collect installation resources on a connected machine.
set -euo pipefail
export LC_ALL=C

bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$bundle_dir/lib/apt-packages.sh"

usage() {
    printf '%s\n' 'Usage: bash download-resources.sh [--config FILE] [--output DIR] [--only RESOURCE] [--apt] [--open-manual]' \
        'Defaults: config/resources.conf and packages/ beside this script.' \
        'Run --apt on a connected Ubuntu amd64 machine matching the target release.' \
        'Use --open-manual to open the vendor pages for missing manual downloads.'
}
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

config="$bundle_dir/config/resources.conf"
output="$bundle_dir/packages"
only=
with_apt=false
open_manual=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h) usage; exit 0 ;;
        --apt) with_apt=true ;;
        --open-manual) open_manual=true ;;
        --config|--output|--only)
            [[ $# -ge 2 && -n $2 && $2 != -* ]] || fail "Missing value for $1."
            case $1 in
                --config) config=$2 ;;
                --output) output=$2 ;;
                --only) only=$2 ;;
            esac
            shift
            ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done

[[ -r $config ]] || fail "Cannot read $config."
if [[ $with_apt == true ]]; then
    target_id=$(apt_target_id) || fail '--apt requires Ubuntu amd64.'
fi
mkdir -p -- "$output"
output=$(cd -- "$output" && pwd)
stage=$(mktemp -d "$output/.download.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
curl_https=(curl --fail --location --silent --show-error --retry 3 --proto '=https' --proto-redir '=https')

verify_file() {
    local path=$1 checksum=$2
    [[ -s $path ]] || fail "Empty download: ${path##*/}."
    if [[ $checksum != - ]]; then
        local digest
        if command -v sha256sum >/dev/null; then
            digest=$(sha256sum < "$path")
        else
            digest=$(shasum -a 256 < "$path")
        fi
        [[ ${digest%% *} == "$checksum" ]] || fail "SHA-256 mismatch: ${path##*/}."
    fi
}

download_file() {
    local filename=$1 url=$2 checksum=$3
    if [[ -f $output/$filename ]]; then
        verify_file "$output/$filename" "$checksum"
        printf 'Using %s\n' "$filename"
        return
    fi
    printf 'Downloading %s\n' "$filename"
    "${curl_https[@]}" -o "$stage/$filename" "$url"
    verify_file "$stage/$filename" "$checksum"
    mv -- "$stage/$filename" "$output/$filename"
}

download_nightly() {
    local url=$1 bridge ctl artifact
    local -a bridges controls
    shopt -s nullglob
    bridges=("$output"/yabridge-*.tar.gz "$output"/yabridge-*.tar.gz.zip)
    controls=("$output"/yabridgectl-*.tar.gz "$output"/yabridgectl-*.tar.gz.zip)
    shopt -u nullglob
    if [[ -x $output/yabridge/yabridgectl ]]; then
        printf 'Using the extracted yabridge package.\n'
        return
    fi
    if (( ${#bridges[@]} || ${#controls[@]} )); then
        if (( ${#bridges[@]} == 1 && ${#controls[@]} <= 1 )); then
            bridge=${bridges[0]##*/}
            ctl="yabridgectl-${bridge#yabridge-}"
            if (( ${#controls[@]} == 1 )) && [[ ${controls[0]##*/} == "$ctl" &&
                -s ${bridges[0]} && -s ${controls[0]} ]]; then
                printf 'Using the existing yabridge archive pair.\n'
                return
            fi
            if (( ${#controls[@]} == 0 )) && [[ $bridge == *.tar.gz && -s ${bridges[0]} ]] &&
                tar -tzf "${bridges[0]}" | awk '/(^|\/)yabridgectl$/ { found=1 } END { exit !found }'; then
                printf 'Using the existing combined yabridge archive.\n'
                return
            fi
        fi
        fail 'Use an empty output directory or provide a matching yabridge archive pair.'
    fi
    "${curl_https[@]}" -o "$stage/nightly.html" "$url"
    bridge=$(sed -nE 's/.*href="[^"]*\/(yabridge-[[:alnum:].-]+\.tar\.gz\.zip)".*/\1/p' "$stage/nightly.html" | sort -u)
    [[ $bridge =~ ^yabridge-[[:alnum:].-]+\.tar\.gz\.zip$ ]] || fail 'Could not identify one yabridge development artifact.'
    ctl="yabridgectl-${bridge#yabridge-}"
    for artifact in "$bridge" "$ctl"; do
        printf 'Downloading %s\n' "$artifact"
        "${curl_https[@]}" -o "$stage/$artifact" "$url/$artifact"
        verify_file "$stage/$artifact" -
    done
    mv -- "$stage/$bridge" "$stage/$ctl" "$output/"
}

found=false
while IFS='|' read -r resource kind name url checksum extra || [[ -n $resource ]]; do
    [[ -z $resource || $resource == \#* ]] && continue
    [[ -z $only || $only == "$resource" ]] || continue
    found=true
    [[ -z $extra && $url == https://* && ( $checksum == - || $checksum =~ ^[0-9a-f]{64}$ ) ]] ||
        fail "Invalid config entry for $resource."
    case $kind in
        file)
            [[ $name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail "Invalid output name for $resource."
            download_file "$name" "$url" "$checksum"
            ;;
        nightly) download_nightly "${url%/}" ;;
        manual)
            if [[ ! -f $output/$name ]]; then
                printf 'Supply %s locally. Download the package in your browser and complete any vendor confirmations at %s\n' "$name" "$url"
                printf '%s\n' "$url" >> "$stage/manual-urls"
            fi
            ;;
        *) fail "Unknown resource kind: $kind." ;;
    esac
done < "$config"
[[ $found == true ]] || fail "No matching resource in $config."

if [[ $with_apt == true ]]; then
    [[ ! -e $output/apt ]] || fail 'Use an output directory without an existing apt/ bundle.'
    # Use an empty package status so the collector also downloads dependencies
    # that happen to be installed on the preparation machine.
    : > "$stage/dpkg-status"
    for group in runtime build; do
        mkdir -p -- "$stage/apt/$group/partial"
        packages=()
        while IFS= read -r package; do packages+=("$package"); done < <(apt_package_names "$group")
        apt-get -o Debug::NoLocking=true -o "Dir::State::status=$stage/dpkg-status" \
            -o "Dir::Cache::archives=$stage/apt/$group/" -o Dir::Cache::pkgcache= \
            -o Dir::Cache::srcpkgcache= --download-only --no-install-recommends install -y "${packages[@]}"
        rmdir -- "$stage/apt/$group/partial"
    done
    printf '%s\n' "$target_id" > "$stage/apt/target"
    for group in runtime build; do
        (cd -- "$stage/apt/$group" && sha256sum -- *.deb > SHA256SUMS)
    done
    mv -- "$stage/apt" "$output/apt"
fi
if [[ $open_manual == true && -s $stage/manual-urls ]]; then
    opener=xdg-open
    if [[ $OSTYPE == darwin* ]]; then opener=open; fi
    while IFS= read -r url; do
        if ! command -v "$opener" >/dev/null || ! "$opener" "$url"; then
            printf 'Open this page in your browser: %s\n' "$url" >&2
        fi
    done < <(sort -u "$stage/manual-urls")
fi
printf 'Resources: %s\n' "$output"
