# Workstation command

After installing or updating the integration, use `defeedback` from any directory. It uses Python's standard library; no Typer or pip installation is required.

| Command | Purpose |
| --- | --- |
| `defeedback` | Start REAPER with the connected USB device |
| `defeedback --device cq` | Select a USB device explicitly |
| `defeedback run --help` | Show launcher options |
| `defeedback update` | Fetch project code and install the integration |
| `defeedback update --check` | Fetch and compare revisions without activating an update |
| `defeedback update --reaper` | Also update the REAPER runtime |
| `defeedback license-gui` | Open license management in VSTHost |
| `defeedback aes67 install` | Install optional AES67 packages |
| `defeedback aes67 setup` | Configure the AES67 network, PTP access, and PipeWire |
| `defeedback check` | Check the default Focusrite profile |
| `defeedback check avantis --launch` | Check AES67 endpoints and launch REAPER if available |
| `defeedback diagnose` | Collect a diagnostic report |
| `defeedback ini --device evo8` | Print a connected device's minimal INI to stdout |
| `defeedback --help` | Show commands |

Subcommand arguments are forwarded to the underlying launcher or tool. For example:

```bash
defeedback aes67 setup --quantum 64 enp2s0
defeedback diagnose --usb-card CQ12T
defeedback ini --device hw:EVO8 --inputs 4 --outputs 4 > reaper-evo8.ini
```

AES67 remains a manual network/PTP/audio startup; `aes67 setup` prepares configuration, not a running audio service. See [AES67 setup](aes67.md).

## Git updates on the device

`defeedback update` manages a dedicated checkout at `~/.local/share/defeedback/source`, using `https://github.com/psmsmets/defeedback-linux.git`, branch `main`, by default. The first update clones it automatically, including after an initial rsync or offline installation. Your original checkout or transferred bundle is not modified. Git and Internet access are required for this operation; existing audio operation remains available offline.

Close REAPER before applying an update. The command rejects local modifications, untracked files, branch/origin mismatches, and changes that cannot be applied as a fast-forward. It does not reset, stash, rebase, or switch branches. A failed fetch does not change installed files.

`--check` fetches metadata and may create the managed checkout on first use. It prints installed and checkout revisions without applying code or updating REAPER. An installation made outside Git has an unknown revision. To select a different repository or branch on the first run, pass `--repo URL --branch NAME`; the selection is recorded in `~/.local/state/defeedback/update-source.json`. Private repositories require working Git authentication. An existing managed checkout is not repointed automatically.

The default update installs the wrapper, launcher, tools, and templates through the same integration installer used by setup and `update-defeedback.sh`. `--reaper` also downloads and verifies the selected stable REAPER 7 runtime. Wine, yabridge, and the De-Feedback plugin are not updated by this command.

The update process backs up existing integration files, preferences, and generated projects and restores changed installation files on failure. The managed Git checkout can already have advanced when installation fails; rerun the command after resolving the error. Installation locks prevent concurrent application of setup or updates. Updates do not restart AES67 services or reapply its generated network/audio configuration; run `defeedback aes67 setup` when configuration changes are needed.

## Install the command on an existing workstation

From an updated Linux bundle, with REAPER closed:

```bash
bash update-defeedback.sh --integration-only
```

This installs `~/.local/bin/defeedback` and its supporting files. Open a new terminal if that directory was not already on PATH. If Git is missing on an existing workstation, install it with `sudo apt-get install git` before the first device-side update. Fresh setup installs Git as a runtime dependency.

`bash update-defeedback.sh` remains available for updating REAPER and integration from a manually updated bundle. `--integration-only` applies local code without a network fetch; `--archive` supports a local REAPER archive. See [updates](setup.md#update-the-workstation).

## Development checks

From the repository root, run `python3 -m unittest discover -s defeedback-linux/tests -v`. Tests use temporary local Git repositories and simulated command execution; they do not install packages or open audio devices.
