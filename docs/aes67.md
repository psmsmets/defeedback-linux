# AES67 setup for Avantis and dLive

The reference console is an **Allen & Heath Avantis Solo** with an **Allen & Heath Dante 64 V3** card.

AES67 audio and eight simultaneous mono instances are **not yet hardware-validated**. The configured upper limit is eight mono paths. Focusrite Scarlett USB remains the default for initial setup.

## Current test plan

Keep **PipeWire/JACK** as the backend. Begin with **four mono plugin instances**, retaining eight transport channels and an eight-instance upper limit. First establish a working send/return loop, then measure bypass and active-plugin round-trip latency, and only then optimize buffering. The default quantum remains 48 and both RTP latency targets remain 3 ms; use 64 samples if needed for stability. Do not lower network buffers before the baseline works.

The enabled automatic fallback defaults to four plugin paths. For controlled capacity tests, `defeedback-linux --channels 8` explicitly requests eight; 1, 2, and 4 are also available. USB profiles keep their device-specific defaults. Network ports and plugin instance counts are separate: the eight-channel return stream does not require eight active plugins.

## Install and configure

After base installation, run as your regular desktop user:

```bash
defeedback-linux aes67 install
defeedback-linux aes67 setup
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
| RTP latency targets | 3 ms each for receive and transmit; `--network-latency MS` accepts integers 1–20 |
| PTP | PTPv2 domain 0, UDP IPv4, E2E delay measurement |

The return multicast group must be unused, differ from the console send group, and match the Dante receiver's AES67 prefix. The multicast address is separate from the computer's link-local address.

For explicit configuration:

```bash
defeedback-linux aes67 setup --quantum 48 enp2s0 239.69.150.244
```

A cable is not required to prepare configuration, but the selected NIC must have hardware TX/RX timestamping and a PTP hardware clock. Setup grants the current user persistent read access to that clock via a udev rule tied to the NIC's PCI address and user UID. It applies the ACL immediately. Repeat setup if changing NIC or user.

Setup creates a dedicated NetworkManager profile without activating it immediately and prints its activation command. It does not modify the control interface or overwrite a conflicting existing profile. Connect the audio cable and activate the profile before starting PTP or audio. `--network existing` preserves the current network settings and requires an IPv4 address, including link-local.

## Enable experimental startup fallback

AES67 uses the following path:

`Console AES67 ↔ PipeWire AES67 helper ↔ PipeWire JACK interface ↔ REAPER`

JACK is REAPER's local audio interface, not the network transport. `pw-jack` redirects JACK applications to PipeWire. [PipeWire pw-jack](https://docs.pipewire.org/page_man_pw-jack_1.html)

Fallback is disabled by default. For a controlled early-start test, select **JACK** in REAPER, configure eight input/output ports, and close REAPER so its preferences are saved. Then run:

```bash
defeedback-linux aes67 enable --reaper-ini ~/.config/REAPER/reaper.ini
defeedback-linux aes67 status
```

This requires the AES67 configuration and `pw-jack`. It copies the saved preferences to `~/.config/REAPER/reaper-defeedback-aes67.ini`, removes project restore paths, and requests eight ports. The operator-selected backend settings are preserved; the command rejects the known ALSA mode but does not fully validate the saved JACK settings. Confirm JACK in the GUI before enabling. USB settings are separate.

Manual AES67 launches use this same managed JACK profile and default to four mono paths. For manual operation only, run `defeedback-linux aes67 disable` after preparing the profile; disabling the automatic fallback preserves it. `defeedback-linux --device aes67` explicitly selects AES67 even with USB connected and does not wait for readiness. Use `defeedback-linux audio check avantis --launch` to check endpoint presence first.

On the next automatic launch, an available supported USB profile wins. Without USB, the launcher attempts REAPER with the AES67 profile and four mono paths by default (maximum eight), **without waiting for link, PTP, or stream tests**. State checks run in the supervisor alongside REAPER and are logged. Use this to investigate whether REAPER and the template tolerate endpoints appearing later. If REAPER exits, supervision also ends; consult its exit status and repeat the test after resolving the failure.

```bash
defeedback-linux aes67 disable
```

Enable/disable changes `~/.config/defeedback/startup.json` for future launches only. It does not start/stop PTP, PipeWire, or a running REAPER session. Automatic PTP/audio services and stream routing remain planned; start the helpers separately for this experiment. This test does not establish live-use readiness.

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
3. Run `defeedback-linux aes67 ptp` in its own terminal; it uses sudo for the configured PTP client and keeps a text session log. Use only one PTP client on the interface. Run `defeedback-linux aes67 ptp-status` as your desktop user and confirm `SLAVE` state and the expected grandmaster. Queries use a private temporary client socket and remove it afterwards.
4. In another terminal, run `defeedback-linux aes67 audio` as your desktop user. It checks PTP SLAVE state before starting the helper and keeps a text session log. It uses SAP for stream discovery and announcement and exports audio nodes to the existing PipeWire graph. [PipeWire AES67 profile](https://github.com/PipeWire/pipewire/blob/1.6.2/src/daemon/pipewire-aes67.conf.in)
5. Prepare the managed JACK profile as described above, then run `defeedback-linux audio check avantis --launch` (or `dlive`). It skips launching when an AES67 source or the return is missing; this does not verify PTP lock or subscriptions. It launches through `pw-jack` with the managed profile and four mono paths, independent of the general REAPER preferences and automatic fallback setting.
6. Map console stream channels 1–8 to REAPER inputs 1–8 and REAPER outputs 1–8 to `defeedback-aes67-return` channels 1–8. Use the [mono template generator](reaper-projects.md) and choose `1ch` to verify the first path, then `4ch` for the initial plugin test; reserve `8ch` for later capacity validation. Templates enable monitoring and FX; bypass the FX for the baseline test.
7. In Dante Controller, subscribe the card inputs to the corresponding **De-Feedback Return** channels and patch them to the console insert returns. Verify each path before enabling its insert and FX.
8. Verify `RATE` and `QUANT` in `pw-top`, reset `ERR` with `c`, and monitor errors under load. Measure round-trip latency in bypass and with De-Feedback active. Validate the four-mono configuration and repeat it after a cold boot. Test eight mono paths only after the baseline is stable.

Stop the helper and then PTP with Ctrl+C in their terminals. No AES67 autostart service is installed. The opt-in early-start experiment is documented in [startup selection](setup.md#startup-selection); full automatic PTP/audio service startup remains planned. Record card firmware, PTP lock, quantum, network buffers, test duration, errors, and measured latency.


## Logs

PTP and audio helpers remain foreground commands, not automatic services. Start them through the commands above so their output is captured. Add `--debug` for a controlled troubleshooting run, for example `defeedback-linux aes67 audio --debug`. Use `defeedback-linux logs --list` or `defeedback-linux logs --all --journal` to inspect results. While the audio helper or an AES67 REAPER session is active, lightweight 15-second checks log changes in link state, PTP port state, and source/return endpoint availability. These checks do not prove correct subscriptions, clock accuracy, or clean audio; see [logging limits](logging.md).


## Latency budget and tuning

The [USB measurement summary](overview.md#reported-results) separates confirmed round-trip results from the unmeasured 32-sample Behringer estimate. Lower AES67 latency is a theoretical tuning goal, not an established result. Validate the complete loop and compare measured bypass and active-plugin paths before claiming an improvement over USB.

The current backend is PipeWire AES67 with a JACK client interface for REAPER, not `aes67-linux-daemon` with a RAVENNA ALSA driver. The latter project's PulseAudio restrictions do not describe this backend. Keep `pipewire-pulse` available for desktop compatibility; it is not in the REAPER/JACK signal path.

At 48 kHz, graph blocks of 32/48/64/96 samples last 0.667/1/1.333/2 ms. Eight channels run in parallel; do not multiply block duration by eight. More instances can increase CPU load and cause missed deadlines.

| Component | Current setting / unknown |
| --- | --- |
| PipeWire receive target | 3 ms |
| PipeWire transmit node target | 3 ms |
| Graph block duration | 1 ms at quantum 48 |
| RTP packet duration | 1 ms; not necessarily an extra independent delay per direction |
| Dante card receive latency | Record the actual configured value |
| Console insert/SRC path and plugin | Must be measured |

These are not independent fixed delays. The receive setting is a network/buffer target; the transmit setting is a node latency target. Timestamp mode and graph scheduling affect how they combine. Do not claim a measured 1 ms insert or blindly sum all settings. See [PipeWire RTP source](https://docs.pipewire.org/page_module_rtp_source.html) and [RTP sink](https://docs.pipewire.org/page_module_rtp_sink.html).

As an **illustrative budget only**, if receive and transmit contribute 3 ms each, processing one further 1 ms block, and the card return adds 1 ms, the subtotal is **8 ms before other console/plugin costs**. This is not a prediction: buffers/scheduling can overlap, and the card setting is not yet known. The initial 3 ms targets do not justify expecting lower latency than the measured USB paths.

Start with 48 kHz, quantum 48, 3 ms targets, one bypassed mono path, and the console insert loop. Measure bypass and active processing separately using the external impulse-response setup. Record endpoints: a console digital-insert measurement is not directly comparable to an analog USB round trip unless the converter/console contributions match.

Change one setting per controlled test. After a stable baseline, try 2 ms targets, then 1 ms if supported and stable:

```bash
defeedback-linux aes67 setup --network existing --quantum 48 --network-latency 2 enp2s0
```

The command sets both receive and transmit targets; it does not change the Dante card's receive latency. Stop audio before reconfiguration, restart the PipeWire helper and user graph as described above, and verify actual values. Use the selected return multicast group explicitly if it differs from the default. Test with quantum 64 as a stability alternative, repeat with four mono instances and after a cold boot, and finally validate eight instances as a separate capacity test. Keep the lowest measured configuration that remains stable, not the smallest configured block.
