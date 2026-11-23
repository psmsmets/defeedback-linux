# Installation reference

Run the commands from the top level of the Linux bundle.

| Path | Role |
| --- | --- |
| `download-resources.sh` | Downloads or identifies resources. Writes to the selected package directory. |
| `setup-defeedback.sh` | Installs the audio workstation for the current Ubuntu Studio user. |
| `update-defeedback.sh` | Updates REAPER and the hardware-aware launcher/template resources; supports version checks and local archives. |
| `config/` | Download URLs, filenames, checksums where available, and Ubuntu package lists. |
| `defeedback` | Unified command for launching, licensing, audio tools, and Git updates. |
| `tests/` | Automated command and update checks using local Git repositories. |
| `lib/` | Internal installation and launcher components. |
| `reaper/` | Mono template generator and source plugin state. |
| `tools/` | Audio diagnostics, workstation cleanup, appliance setup, and AES67 installation/setup. |
| `packages/` | Local downloads and user-supplied files. Git ignores this directory. |

## Prepare resources

On a connected machine with Bash and curl, run:

```bash
bash download-resources.sh
```

The script reads [the resource manifest](../defeedback-linux/config/resources.conf) and collects the pinned REAPER archive, the matching yabridge development archives, and the patched Wine source. The REAPER archive is checked against its published SHA-256. The yabridge and Wine entries follow their respective branches. For repeatable deployments, keep the collected files or update the manifest to fixed artifact URLs and hashes. `--config FILE` selects a different manifest, `--output DIR` changes the package directory, and `--only RESOURCE` selects a single entry. Each line uses `resource|kind|name|https-url|sha256`. Use `-` when an upstream checksum is unavailable. A `file` entry can also point to a repository ZIP or another direct artifact you have access to.

Download the Windows De-Feedback installer and optional VSTHost x64 archive manually in your browser. On the Alpha Labs download page, read the terms, privacy policy, and FAQs. Check the three acknowledgements yourself to enable the download. Pass `--open-manual` to the downloader to open the page in your default browser. [Alpha Labs download page](https://www.alphalabsaudio.com/defeedback/)

Place the Windows installer at `packages/DefeedbackSetup.exe`. The installer also presents the license terms during setup. For private use with the supplied edition, place its complete folder in `packages/vsthostx64/`, including the executable, license and Data folder. See [Alpha Labs downloads and terms](https://alphalabsaudio.com/defeedback/) and the [REAPER distribution agreement](https://www.reaper.fm/dist-agreement.php). Keep vendor installers local and retain their license files.

## Change the selected versions

Edit `config/resources.conf` to change the defaults for downloads and new installations. For REAPER, update the Linux x86-64 archive name, URL, and published SHA-256 together. For Wine, select a source tarball from the patched fork. A commit archive and SHA-256 pin it to an exact revision. To pin yabridge, replace its `nightly` entry with one or two `file` entries under the resource name `yabridge`. Use a combined archive containing `yabridgectl` or a bridge and control archive from the same build. Keep the upstream archive names so setup can find and match them.

Prepare updated versions in an empty package directory to avoid mixing old and new archives. Pass that directory to setup as its positional argument. Setup reuses existing REAPER, yabridge, and Wine installations and cached Wine source. The manifest changes the inputs for a fresh install or build. Use `bash update-defeedback.sh` for an existing workstation, or `bash update-defeedback.sh --pinned` to apply the selected manifest REAPER version. See [workstation updates](setup.md#update-the-workstation) and [optional application cleanup](setup.md#remove-optional-applications).

## Transfer to a disconnected target

On a connected **Ubuntu amd64** machine with the same Ubuntu release and compatible package sources as the target, refresh the APT indexes and run:

```bash
sudo apt-get update
bash download-resources.sh --apt
```

This adds the runtime and Wine build APT archives, their checksums, and the Ubuntu release and architecture marker. Copy the entire Linux bundle, including `packages/` and any manually supplied files, to the target. Run setup from the target desktop:

```bash
bash setup-defeedback.sh --offline
```

Offline setup uses the prepared local archives and can build Wine from the local source tarball. License activation is a separate step. The clean-machine offline install still needs validation on Ubuntu Studio with networking disabled.

## What setup changes

| Area | Changes |
| --- | --- |
| Ubuntu packages | Uses `sudo` to install the runtime packages from [the APT package list](../defeedback-linux/config/apt-packages.conf). A new Wine build also installs the build group. |
| REAPER | Installs to `~/.local/opt/REAPER` and keeps any existing audio preferences. |
| Patched Wine | Builds or reuses `~/.local/opt/defeedback-wine-dcomp/runtime`. The Wine source and build logs stay on the machine. |
| De-Feedback and yabridge | Updates `~/.wine-defeedback`, installs the plugin when needed, and registers it with yabridge. The bridge lives in `~/.local/share/yabridge` and creates wrappers under `~/.vst3/yabridge`. |
| Launchers and routing | Installs launchers and mono template resources under `~/.local/share/defeedback`, links commands in `~/.local/bin`, and creates application menu and desktop entries. Setup adds `~/.local/bin` to the shell startup file if needed. VSTHost is installed when its local folder is present. |
| Optional `--appliance` | Configures SDDM autologin, the systemd user service for REAPER, Plasma desktop and power settings, system sleep and power-button behavior, and disables ModemManager and CUPS. See [workstation startup](setup.md#dedicated-workstation-startup). |
| Optional AES67 | Run `tools/install-aes67.sh`, then `tools/setup-aes67.sh` for network, PTP access, and PipeWire configuration. See [AES67 setup](aes67.md). |
