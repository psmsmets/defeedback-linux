# Audio inspection and diagnostics

Use `defeedback-linux audio --help` to see the available tools. These commands are separate from `defeedback-linux run`, which launches REAPER.

## Check a device

```bash
defeedback-linux audio check
defeedback-linux audio check focusrite --launch
defeedback-linux audio check cq
defeedback-linux audio check avantis --launch
defeedback-linux audio check --help
```

Focusrite Scarlett is the default. The checker also has SQ/CQ USB and Avantis/dLive AES67 profiles. It lists detected devices and PipeWire connections; hardware routing and audio quality still need a physical test. `--launch` opens REAPER for the selected profile; the AES67 check requires source and return endpoints first. See [USB device profiles](setup.md#automatic-usb-startup) and [AES67 setup](aes67.md).

## Save a diagnostic report

```bash
defeedback-linux audio diagnose
defeedback-linux audio diagnose --usb-card CQ12T
defeedback-linux audio diagnose --help
```

The report includes the integration version, OS, USB/ALSA devices, PipeWire connections, network state, and available service/kernel messages. `--usb-card` additionally opens capture and playback to test stream access; capture is discarded and playback sends silence. Close REAPER before that optional probe. See [logging and troubleshooting](logging.md).

## Print a device INI

```bash
defeedback-linux audio ini --device evo8
defeedback-linux audio ini --device hw:EVO8 --inputs 4 --outputs 4 > reaper-evo8.ini
defeedback-linux audio ini --help
```

INI generation writes only the configuration to stdout and does not launch REAPER or write settings. Without explicit port counts, the device must be connected. Offline generation needs an exact ALSA card ID and both hardware port counts. See [device INI generation](reaper-projects.md#print-a-device-ini).
