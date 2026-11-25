# Workstation command

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. REAPER and Alpha Labs De-Feedback are separately licensed products. This project includes neither license. Obtain and activate each product according to its vendor's terms.

Products and licensing: [REAPER](https://www.reaper.fm/purchase.php) · [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

After installing or updating the integration, use `defeedback-linux` from any directory. It uses Python's standard library; no Typer or pip installation is required.

For a new workstation, first run `bash setup-defeedback.sh` from the Linux bundle directory. After installation, optionally run `defeedback-linux appliance setup` to enable desktop autologin and REAPER autostart. To do both in one step, run `bash setup-defeedback.sh --appliance`. Updating an existing installation does not require repeating setup and does not enable autostart.

| Command | Purpose |
| --- | --- |
| `defeedback-linux` | Start REAPER with the connected USB device |
| `defeedback-linux --device cq` | Select a USB device explicitly |
| `defeedback-linux --device aes67` | Start with the managed JACK profile; defaults to four mono paths |
| `defeedback-linux run --help` | Show launcher options |
| `defeedback-linux update` | Fetch project code and install the integration |
| `defeedback-linux update --check` | Fetch and compare revisions without activating an update |
| `defeedback-linux update --reaper` | Also update the REAPER runtime |
| `defeedback-linux install vsthost` | Install optional VSTHost from its official x64 package |
| `defeedback-linux install vsthost --source /path/to/vsthostx64.zip` | Install the complete optional package from a local ZIP or extracted directory |
| `defeedback-linux start vsthost` | Open De-Feedback in optional VSTHost using patched Wine |
| `defeedback-linux aes67 install` | Install optional AES67 packages |
| `defeedback-linux aes67 setup` | Configure the AES67 network, PTP access, and PipeWire |
| `defeedback-linux aes67 enable --reaper-ini PATH` | Enable experimental early fallback using saved JACK preferences |
| `defeedback-linux aes67 disable` | Disable AES67 fallback for future launches |
| `defeedback-linux aes67 status` | Show the activation setting |
| `defeedback-linux aes67 ptp` | Run the configured PTP client with session logging |
| `defeedback-linux aes67 ptp-status` | Query PTP port state and grandmaster information without sudo |
| `defeedback-linux aes67 audio` | Run the AES67 helper after checking PTP SLAVE state |
| `defeedback-linux appliance setup` | Enable desktop autologin, REAPER autostart, and appliance power settings |
| `defeedback-linux trim --check` | Preview optional application removal |
| `defeedback-linux trim --apply --autoremove` | Apply cleanup including unused automatic dependencies |
| `defeedback-linux check` | Check the default Focusrite profile |
| `defeedback-linux check avantis --launch` | Check AES67 endpoints and launch REAPER if available |
| `defeedback-linux diagnose` | Collect a diagnostic report |
| `defeedback-linux ini --device evo8` | Print a connected device's minimal INI to stdout |
| `defeedback-linux logs` | Read the latest indexed log |
| `defeedback-linux logs --list` | List all available log sources |
| `defeedback-linux logs --all --journal` | Read log tails and user service messages |
| `defeedback-linux --debug` | Start REAPER with additional text diagnostics |
| `defeedback-linux --version` | Show the integration version and installed Git revision, when available |
| `defeedback-linux --help` | Show commands |

When reporting an issue, include `defeedback-linux --version` and the relevant logs. This version identifies the Linux integration, independently of REAPER, Wine, yabridge, and De-Feedback. Git-based installations also show the installed revision; release archives retain the version without requiring Git. Existing workstations need an integration update to gain this option.

To activate the plugin, start REAPER with `defeedback-linux`, open the De-Feedback FX window, and click **UI** to show its editor. Select **Options → License Management** and follow the regular De-Feedback / Alpha Labs activation steps for Windows. See [activation in REAPER](setup.md#license-management-in-reaper). VSTHost is [an optional extra](setup.md#optional-vsthost); close REAPER before using it. The previous `open-license-gui` and `license-gui` commands have been removed.

Subcommand arguments are forwarded to the underlying launcher or tool. For example:

```bash
defeedback-linux aes67 setup --quantum 64 enp2s0
defeedback-linux diagnose --usb-card CQ12T
defeedback-linux ini --device hw:EVO8 --inputs 4 --outputs 4 > reaper-evo8.ini
```

AES67 remains a manual network/PTP/audio startup; `aes67 setup` prepares configuration, not a running audio service. See [AES67 setup](aes67.md).

## Unattended operation and maintenance

The goal is a headless appliance: power on and load the correct settings and mono routing for the connected USB interface or AES67 on the second NIC (`enp2s0` on the reference Beelink). The control/Internet NIC remains separate.

`defeedback-linux appliance setup` enables Plasma desktop autologin, REAPER autostart, and power settings. It is opt-in; normal installation does not enable it. USB detection and per-device configuration already run at launch. REAPER and the plugin still require a graphical session even when the intended deployment has no attached screen or keyboard. Boot without a monitor has been validated on the reference Beelink. EVO8 appliance autostart with four mono instances of the activated plugin has also been confirmed; see [validation status](overview.md#validation-status). Failure recovery remains unvalidated. This is not a console-only audio service.

Startup selects USB first. An opt-in AES67 fallback now attempts REAPER with four mono paths by default (maximum eight) before readiness tests finish; the supervisor logs link, PTP, and endpoint state in parallel. It is disabled by default and remains a hardware test facility. See [activation](aes67.md#enable-experimental-startup-fallback) and [startup selection](setup.md#startup-selection). Automatic PTP/audio service startup, routing, and recovery are not implemented. No audio hotplug switching is implemented while REAPER is running.

`defeedback-linux trim` previews cleanup by default. Use `--check --autoremove` to preview dependency cleanup and `--apply --autoremove` to apply it. Cleanup is never automatic during installation or appliance setup. See [startup settings](setup.md#dedicated-workstation-startup) and [application cleanup](setup.md#remove-optional-applications).

## Logs and debugging

Use `defeedback-linux logs` for the latest log, `--list` to select a source, and `--follow` to watch one log. `--debug` adds text context to a command without recording audio. See [logging and troubleshooting](logging.md) for retention, health checks, and AES67 usage.

## Git updates on the device

`defeedback-linux update` manages a dedicated checkout at `~/.local/share/defeedback/source`, using `https://github.com/psmsmets/defeedback-linux.git`, branch `main`, by default. The first update clones it automatically, including after an initial rsync or offline installation. Your original checkout or transferred bundle is not modified. Git and Internet access are required for this operation; existing audio operation remains available offline.

Close REAPER before applying an update. The command rejects local modifications, untracked files, branch/origin mismatches, and changes that cannot be applied as a fast-forward. It does not reset, stash, rebase, or switch branches. A failed fetch does not change installed files.

`--check` fetches metadata and may create the managed checkout on first use. It prints installed and checkout revisions without applying code or updating REAPER. An installation made outside Git has an unknown revision. To select a different repository or branch on the first run, pass `--repo URL --branch NAME`; the selection is recorded in `~/.local/state/defeedback/update-source.json`. Private repositories require working Git authentication. An existing managed checkout is not repointed automatically.

The default update installs the wrapper, launcher, tools, and templates through the same integration installer used by setup and `update-defeedback.sh`. `--reaper` also downloads and verifies the selected stable REAPER 7 runtime. Wine, yabridge, and the De-Feedback plugin are not updated by this command.

The update process backs up existing integration files, preferences, and generated projects and restores changed installation files on failure. The managed Git checkout can already have advanced when installation fails; rerun the command after resolving the error. Installation locks prevent concurrent application of setup or updates. Updates do not restart AES67 services or reapply its generated network/audio configuration; run `defeedback-linux aes67 setup` when configuration changes are needed.

## Install the command on an existing workstation

From an updated Linux bundle, with REAPER closed:

```bash
bash update-defeedback.sh --integration-only
```

This installs `~/.local/bin/defeedback-linux` and its supporting files. Open a new terminal if that directory was not already on PATH. If Git is missing on an existing workstation, install it with `sudo apt-get install git` before the first device-side update. Fresh setup installs Git as a runtime dependency.

`bash update-defeedback.sh` remains available for updating REAPER and integration from a manually updated bundle. `--integration-only` applies local code without a network fetch; `--archive` supports a local REAPER archive. See [updates](setup.md#update-the-workstation).

## Development checks

From the repository root, run `python3 -m unittest discover -s defeedback-linux/tests -v`. Tests use temporary local Git repositories and simulated command execution; they do not install packages or open audio devices.
