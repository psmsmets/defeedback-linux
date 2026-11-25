# Optional VSTHost

VSTHost is an extra host for experiments, not part of the standard installation or activation workflow. To install and start it explicitly:

```bash
defeedback-linux vsthost install
defeedback-linux vsthost start
```

Installation downloads the complete x64 package from Hermann Seib's official site and retains its license and companion files. For a local package or offline installation, use `defeedback-linux vsthost install --source /path/to/vsthostx64.zip` or pass the extracted package directory instead. It does not create a command alias or desktop shortcut.

The upstream free package permits private use only and excludes commercial or professional use. See [third-party software and redistribution](installation.md#third-party-software-and-redistribution).

Close REAPER before starting VSTHost. The command loads De-Feedback without audio or MIDI in the same permanent Wine prefix, using patched Wine. Click the plug-in edit dial to open its editor. Add `--virtual-desktop` if a Wine virtual desktop is needed. Close VSTHost before reopening REAPER.

Integration updates remove this project's old VSTHost command and shortcuts, keeping backup copies in the update directory. An existing `vsthostx64` package remains installed and can be opened with `defeedback-linux vsthost start`.

Use `defeedback-linux vsthost --help`, `defeedback-linux vsthost install --help`, or `defeedback-linux vsthost start --help` for the available actions and options.
