# De-Feedback Linux bundle

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. REAPER and Alpha Labs De-Feedback are separately licensed products. This project includes neither license. Obtain and activate each product according to its vendor's terms.

Products and licensing: [REAPER](https://www.reaper.fm/purchase.php) · [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

Use an Ubuntu Studio desktop terminal as your regular user and run these commands from this bundle directory. Download the [official Windows De-Feedback installer](https://www.alphalabsaudio.com/defeedback/), create `packages/` if needed, and place the installer at `packages/DefeedbackSetup.exe`:

```bash
mkdir -p packages
```

Once the installer is in place, run:

```bash
bash setup-defeedback.sh
defeedback-linux
```

Setup installs REAPER, yabridge, and patched Wine, downloading missing resources when connected. In REAPER, open a track's FX window, select De-Feedback, and click **UI** to display the plugin editor. Use **Options → License Management** there to activate De-Feedback. REAPER requires its own license. See [activation in REAPER](../docs/setup.md#license-management-in-reaper).

## Headless USB operation

After activation and an initial audio test, close REAPER and enable automatic Plasma login and REAPER startup:

```bash
defeedback-linux appliance setup
```

Reboot when ready and test the audio path. The installer also offers this step at the end of an interactive installation, defaulting to no. Use `bash setup-defeedback.sh --appliance` to select it in advance or `--no-appliance` to skip the question. Noninteractive setup only prints the next steps unless `--appliance` was supplied. Existing startup configuration is retained. See [headless operation](../docs/appliance.md).

**VSTHost is optional and is not needed for the standard installation or activation.** Use `defeedback-linux vsthost install` and `defeedback-linux vsthost start` if you want this [extra host](../docs/setup.md#optional-vsthost), subject to its own license terms. No VSTHost shortcut is created. For a disconnected workstation, first [prepare the offline resources](../docs/installation.md#transfer-to-a-disconnected-target).

Focusrite Scarlett USB is the default. The limit is eight mono paths; eight-mono operation and AES67 audio remain unvalidated.

The goal is headless operation with the correct settings loaded at boot for USB or AES67 on the second network port. USB selection is implemented; an experimental AES67 fallback can be enabled, while automatic PTP/audio service startup remains planned. With appliance setup enabled, REAPER runs in an automatically logged-in Plasma session; monitor-free boot has been validated on the reference Beelink. Planned startup selection is USB first, otherwise a ready AES67 connection on the second port with four mono paths by default (maximum eight); see [startup selection](../docs/setup.md#startup-selection).

## Daily use

```bash
defeedback-linux
defeedback-linux audio check
defeedback-linux logs --journal
defeedback-linux update
defeedback-linux --help
```

For licensing, AES67, appliance setup, cleanup, and INI generation, see the [command reference](../docs/commands.md).

For extra text diagnostics, add `--debug` to a command. Logs are bounded; no audio is recorded. See [logging](../docs/logging.md).

Project updates fetch Git code and install integration files; add `--reaper` to also update REAPER. From a manually updated bundle, use `bash update-defeedback.sh --integration-only`. For downloads or offline preparation, use `bash download-resources.sh --help`.

## Layout

- `config/`: download manifest and Ubuntu packages.
- `lib/`: internal CLI, installation, and launcher components.
- `reaper/`: mono template generator and `plugin-state.RPP`.
- `tools/`: audio, AES67, diagnostics, and maintenance scripts.
- `tests/`: command, installation, and local Git update checks.
- `packages/`: local downloads and vendor installers; ignored by Git.

See [commands](../docs/commands.md) and the [documentation index](../docs/README.md). From this directory, `./defeedback-linux` runs the wrapper before it is installed.
