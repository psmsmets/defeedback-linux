# Workstation commands

Unofficial Linux integration for Alpha Labs De-Feedback, with separate [REAPER](https://www.reaper.fm/purchase.php) and [De-Feedback](https://www.alphalabsaudio.com/defeedback/) licenses. See [third-party terms](installation.md#third-party-software-and-redistribution).

Use `defeedback-linux` from any directory after installation. With no command, it starts REAPER using the detected audio device. First-time installation uses `bash setup-defeedback.sh` from the Linux bundle; see [setup](setup.md).

## Choose a topic

| Command | Purpose | Guide |
| --- | --- | --- |
| `defeedback-linux run` | Start REAPER; add `--device` for an explicit selection | [Startup and device profiles](setup.md#automatic-usb-startup) |
| `defeedback-linux update` | Fetch and apply integration updates; `--reaper` also updates REAPER | [Updates](updates.md) |
| `defeedback-linux logs` | Read, list, or follow saved text logs | [Logs and troubleshooting](logging.md) |
| `defeedback-linux audio` | Check devices, collect diagnostics, or print a device INI | [Audio tools](audio.md) |
| `defeedback-linux aes67` | Configure and manually run experimental AES67 | [AES67](aes67.md) |
| `defeedback-linux appliance` | Enable headless startup or preview application cleanup | [Headless appliance](appliance.md) |
| `defeedback-linux vsthost` | Install or start optional VSTHost | [VSTHost](vsthost.md) |

## Help at each level

```bash
defeedback-linux --help
defeedback-linux audio --help
defeedback-linux aes67 --help
defeedback-linux appliance --help
defeedback-linux vsthost --help
defeedback-linux vsthost install --help
defeedback-linux aes67 setup --help
```

The general help lists topics. Group help lists actions, and action help shows the relevant options. `run`, `update`, and `logs` have their own option help directly.

## Headless startup

Install, activate through REAPER's **UI → Options → License Management**, and test the audio path. Close REAPER, then enable automatic login and REAPER startup:

```bash
defeedback-linux appliance setup
```

The installer shows these next steps and offers headless startup in an interactive terminal, defaulting to no. `bash setup-defeedback.sh --appliance` selects it in advance; `--no-appliance` skips the question. Updates do not enable headless settings. See [the appliance guide](appliance.md).

## Support and compatibility

Include `defeedback-linux --version` and relevant logs in an issue report. The integration version is independent of REAPER, Wine, yabridge, and De-Feedback; Git installations also report the installed revision. Add `--debug` for bounded text diagnostics without recording audio.

Existing `check`, `diagnose`, `ini`, and `trim` spellings remain compatible, as do `install vsthost` and `start vsthost`. They are omitted from the general help; use the topic-first forms in new scripts. The old `open-license-gui` and `license-gui` commands are removed.

Development checks: run `python3 -m unittest discover -s defeedback-linux/tests -v` from the repository root. Tests use temporary files and simulated system commands without installing packages or opening audio devices.
