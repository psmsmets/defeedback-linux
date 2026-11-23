# De-Feedback Linux bundle

Use an Ubuntu Studio desktop terminal as your regular user. Place the official Windows installer in `packages/DefeedbackSetup.exe`, then run:

```bash
bash setup-defeedback.sh
defeedback
```

Focusrite Scarlett USB is the default. The limit is eight mono paths; eight-mono operation and AES67 audio remain unvalidated.

## Daily use

```bash
defeedback --help
defeedback update
defeedback license-gui
defeedback check
defeedback diagnose
defeedback aes67 install
defeedback aes67 setup
defeedback ini --device evo8
```

Project updates fetch Git code and install integration files; add `--reaper` to also update REAPER. From a manually updated bundle, use `bash update-defeedback.sh --integration-only`. For downloads or offline preparation, use `bash download-resources.sh --help`.

## Layout

- `config/`: download manifest and Ubuntu packages.
- `lib/`: internal CLI, installation, and launcher components.
- `reaper/`: mono template generator and `plugin-state.RPP`.
- `tools/`: audio, AES67, diagnostics, and maintenance scripts.
- `tests/`: command, installation, and local Git update checks.
- `packages/`: local downloads and vendor installers; ignored by Git.

See [commands](../docs/commands.md) and the [documentation index](../docs/README.md). From this directory, `./defeedback` runs the wrapper before it is installed.
