# AES67 setup for Avantis and dLive

AES67 audio and eight simultaneous mono instances are **not yet hardware-validated**. The configured upper limit is eight mono paths. Focusrite Scarlett USB remains the default for initial setup.

## Install and configure

Run from the Linux bundle as your regular desktop user:

```bash
bash tools/install-aes67.sh
bash tools/setup-aes67.sh
```

Installation requires Internet access and installs the optional PipeWire, JACK, PTP, NetworkManager, and ACL packages. It checks for the packaged PipeWire AES67 configuration. If that configuration is missing, the distribution's PipeWire needs upgrading before setup can proceed. The optional installer has no offline-package mode.

Setup lists interfaces and prompts for the audio interface, network mode, quantum, and return multicast address. Its interface suggestion is `enp0s2`; on the reference Beelink, select **`enp2s0`**. Keep **`enp1s0`** for control and Internet. Confirm physical port identity before applying the audio profile.

| Setting | Default / choices |
| --- | --- |
| Network | Dante link-local, automatic `169.254.x.x/16`, without DHCP |
| Other network modes | `--network dhcp` or `--network existing` |
| Gateway and DNS | None for the dedicated audio profile; never a default route |
| Sample rate / format | 48000 Hz / 24-bit |
| Quantum | 48 samples by default; 32, 48, 64, 96, 128, 144, 256, 512, 1024, 8192 allowed |
| Return | One eight-channel multicast stream; suggested `239.69.150.244` |
| RTP packet time | 1 ms |
| Network buffering | 3 ms in the PipeWire base profile |
| PTP | PTPv2 domain 0, UDP IPv4, E2E delay measurement |

The return multicast group must be unused, differ from the console send group, and match the Dante receiver's AES67 prefix. The multicast address is separate from the computer's link-local address.

For explicit configuration:

```bash
bash tools/setup-aes67.sh --quantum 48 enp2s0 239.69.150.244
```

A cable is not required to prepare configuration, but the selected NIC must have hardware TX/RX timestamping and a PTP hardware clock. Setup grants the current user persistent read access to that clock via a udev rule tied to the NIC's PCI address and user UID. It applies the ACL immediately. Repeat setup if changing NIC or user.

Setup creates a dedicated NetworkManager profile without activating it immediately and prints its activation command. It does not modify the control interface or overwrite a conflicting existing profile. Connect the audio cable and activate the profile before starting PTP or audio. `--network existing` preserves the current network settings and requires an IPv4 address, including link-local.

## Apply the PipeWire clock

Setup writes:

- `~/.config/defeedback/pipewire-aes67.conf`: AES67 helper, PTP clock, and eight-channel return.
- `~/.config/pipewire/pipewire.conf.d/90-defeedback-clock.conf`: user PipeWire clock settings for JACK.
- `/etc/udev/rules.d/90-defeedback-ptp-PCI-UID.rules`: PTP access for the selected NIC and user.

`XDG_CONFIG_HOME` overrides the user configuration directory. The clock drop-in affects all PipeWire applications for this user. Direct ALSA USB profiles retain their own device settings. Rate and min/max quantum are fixed, and power-of-two rounding is disabled to allow values such as 48, 96, and 144.

With audio and the AES67 helper stopped, apply the user clock:

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

A 48-sample block at 48 kHz lasts **1 ms**; this is not total insert latency. Network buffers and plugin processing also contribute. All quantum values require target-hardware testing. To try 64 samples, rerun setup with `--quantum 64` and restart audio. Remove the managed clock drop-in and restart these services to restore desktop PipeWire defaults.

## Connect and test

1. Connect the Dante card's **Primary** port and the selected Beelink NIC to the audio network. Enable AES67 on a compatible Avantis/dLive Dante card and set it to **48 kHz**. Verify card revision and firmware support.
2. Keep console inserts bypassed. Patch unused card sockets for insert sends/returns and create the console's AES67 multicast send. Start with one test path; use one eight-channel stream in each direction for the full configuration.
3. Run the PTP command printed by setup, with sudo. Use only one PTP client on the interface. Run the printed `pmc` checks and confirm `SLAVE` state and the expected grandmaster.
4. Start the printed PipeWire helper command as your desktop user. It uses SAP for stream discovery and announcement and exports audio nodes to the existing PipeWire graph. [PipeWire AES67 profile](https://github.com/PipeWire/pipewire/blob/1.6.2/src/daemon/pipewire-aes67.conf.in)
5. Run `bash tools/check-audio.sh avantis --launch` (or `dlive`). It skips launching when an AES67 source or the return is missing; this does not verify PTP lock or subscriptions. Select JACK in REAPER.
6. Map console stream channels 1–8 to REAPER inputs 1–8 and REAPER outputs 1–8 to `defeedback-aes67-return` channels 1–8. Use the [mono template generator](reaper-projects.md) and choose `1ch` for the initial test or `8ch` for the full test. Templates enable monitoring and FX; bypass the FX for the baseline test.
7. In Dante Controller, subscribe the card inputs to the corresponding **De-Feedback Return** channels and patch them to the console insert returns. Verify each path before enabling its insert and FX.
8. Verify `RATE` and `QUANT` in `pw-top`, reset `ERR` with `c`, and monitor errors under load. Measure round-trip latency in bypass and with De-Feedback active. Test eight mono paths and repeat the chosen configuration after a cold boot.

Stop the helper and then PTP with Ctrl+C in their terminals. No AES67 autostart service is installed. Record card firmware, PTP lock, quantum, network buffers, test duration, errors, and measured latency.
