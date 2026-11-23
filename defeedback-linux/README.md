# De-Feedback Linux bundle

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. REAPER and Alpha Labs De-Feedback are separately licensed products. This project includes neither license. Obtain and activate each product according to its vendor's terms.

Products and licensing: [REAPER](https://www.reaper.fm/purchase.php) · [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

Use an Ubuntu Studio desktop terminal as your regular user. Place the official Windows installer in `packages/DefeedbackSetup.exe`, then run:

```bash
bash setup-defeedback.sh
defeedback-linux
```

Focusrite Scarlett USB is the default. The limit is eight mono paths; eight-mono operation and AES67 audio remain unvalidated.

The goal is headless operation with the correct settings loaded at boot for USB or AES67 on the second network port. USB selection is implemented; an experimental AES67 fallback can be enabled, while automatic PTP/audio service startup remains planned. With appliance setup enabled, REAPER runs in an automatically logged-in Plasma session; monitor-free boot has been validated on the reference Beelink. Planned startup selection is USB first, otherwise a ready AES67 connection on the second port with four mono paths by default (maximum eight); see [startup selection](../docs/setup.md#startup-selection).

## Daily use

```bash
defeedback-linux
defeedback-linux check
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
