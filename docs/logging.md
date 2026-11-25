# Logging and troubleshooting

All logging is text-only. Normal operation records startup, selected audio device/settings, process output, failures, exit status, and one process-alive message per minute. No audio files are created by logging or debug mode. The optional `diagnose --usb-card` probe opens PCM capture but discards it to `/dev/null`; it is never run automatically and requires REAPER to be closed.

## Check the autostart service

Run these commands as the workstation user, without sudo. The REAPER user service is installed by `defeedback-linux appliance setup`; a normal installation does not enable autostart.

| Command | What it shows |
| --- | --- |
| `systemctl --user status defeedback-reaper.service` | Service state, process details, and a few recent messages; press `q` to leave the pager |
| `systemctl --user is-active defeedback-reaper.service` | Only the state, such as `active`, `inactive`, or `failed`; a non-active state returns a nonzero exit code |
| `defeedback-linux logs --journal` | The newest application log plus recent REAPER, PipeWire, and WirePlumber user-service messages |

Start with service status if audio did not start automatically. An active service confirms that its process is running, not that audio or routing is correct. A disabled unit may still be running if started manually; an inactive unit is not necessarily a crash. If the unit is not found, appliance setup may not have been run. With no matching USB device, the launcher intentionally exits successfully, so the service can become inactive without failing.

`logs --journal` does not dump the entire history: it shows up to 100 lines from the newest application log and up to 100 journal lines across the selected services combined. Use `defeedback-linux logs --journal --lines 30` for a shorter view. For only this service's messages from the current boot, use:

```bash
journalctl --user -u defeedback-reaper.service -b -n 100 --no-pager
```

## Read logs

```bash
defeedback-linux logs
defeedback-linux logs --list
defeedback-linux logs --lines 200
defeedback-linux logs --file FILENAME --follow
defeedback-linux logs --all --journal > troubleshooting.txt
```

The default shows the newest indexed file. `--file` accepts a filename or relative path shown by `--list`. `--follow` follows that file through rotation; it does not automatically switch to a new session. `--all` prints the tail of each indexed source, not a time-merged event stream. `--lines` applies per source. No files are uploaded.

New sessions are stored in `${XDG_STATE_HOME:-$HOME/.local/state}/defeedback/logs/`, with UTC timestamps and a unique filename per REAPER/tool/update/PTP/audio run. The directory is private to the user. `logs` also indexes diagnostic/setup/cleanup reports, template logs, older launcher/project logs, Wine installer/build logs, and update logs in backup directories. `--journal` additionally reads recent REAPER, PipeWire, and WirePlumber user-service messages; journal access and cross-boot retention depend on the system settings.

Sessions rotate at **2 MiB with two backups** and retain the **10 newest sessions**, plus any older session still active. This keeps ordinary session history around 60 MiB, with extra space possible for active sessions and individual output chunks. Each template log rotates at 256 KiB with one backup. Existing setup/build/diagnostic reports and update backups are not deleted by session retention.

## Debug a problem

Include the output of `defeedback-linux --version` when reporting an issue. New sessions record the integration version alongside the kernel and installed revision; diagnostic reports include it too.

Use a controlled test with additional context:

```bash
defeedback-linux --debug
defeedback-linux diagnose --debug
defeedback-linux check avantis --launch --debug
```

`--debug` can appear before or after a subcommand. It adds bounded, read-only OS, ALSA-device, network, and PipeWire-settings snapshots. REAPER sessions also enable extra Wine/PipeWire text messages. No environment-variable dump or PCM/audio recording is performed. INI output remains clean on stdout, including when `--debug` is supplied.

For service/desktop startup, `DEFEEDBACK_DEBUG=1` enables the same mode. Do not change a running live configuration solely to collect debug output; reproduce the issue during a controlled test. Text logs can contain device names, local paths, network addresses, or process messages: review the report before sharing it.

## USB and AES67 health

While REAPER is running, the selected USB card's presence is checked every 15 seconds. Changes are logged, with no automatic device switching.

For manual AES67 operation, use separate terminals:

```bash
defeedback-linux aes67 ptp
defeedback-linux aes67 audio
defeedback-linux check avantis --launch
```

The PTP command uses the configured NIC and asks sudo to run `ptp4l`. Use only one PTP client per NIC. Confirm the expected grandmaster before starting audio. The audio command refuses startup without PTP SLAVE state. The audio helper and AES67-launched REAPER monitor link, PTP port state, and AES67 source/return endpoint presence every 15 seconds; only changes are logged. External checks have short timeouts. `--debug` is available for these foreground helpers too.

Use `defeedback-linux aes67 ptp-status` without sudo to inspect port state and grandmaster information. Process-alive messages and health checks continue when a supervised process closes its text output but remains running.

## Limits

Logs establish process and device/network state, not audible audio quality, plugin responsiveness, PTP offset accuracy, correct subscriptions, or complete detection of xruns/packet loss. A live validation still needs signal-path, latency, stability, and failure/recovery tests. No automatic restart, bypass, USB/AES67 hot switching, or PTP/audio-helper autostart is implemented. The optional early REAPER fallback is described in [startup selection](setup.md#startup-selection).

Output capture uses a bounded queue and rotating text files, outside the audio process. During an extreme output burst it can discard log chunks and records the drop count. Logging has not yet been performance-validated on the Beelink. Hard power loss or killing the supervisor can leave a session without its normal end marker; files already written are available subject to filesystem durability.
