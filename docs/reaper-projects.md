# Mono routing templates

The launcher automatically creates a project for the selected USB device. For manual setup, including AES67:

1. Use **REAPER 7.43 or newer** and scan `~/.vst3` for De-Feedback.
2. Open an empty project tab.
3. Load `~/.local/share/defeedback/projects/create-template.lua` through **Actions > Show action list > New action > Load ReaScript**.
4. Run the action and choose a profile.

The script needs `defeedback-2ch.RPP` beside it as the source of plugin state. Setup installs both files.

| Profile | Inputs → outputs | Status |
| --- | --- | --- |
| `1ch` | 1 → 1 | Single mono path |
| `2ch` | 1–2 → 1–2 | Tested on Scarlett Solo 3rd Gen and UMC202HD |
| `4ch` | 1–4 → 1–4 | Tested on EVO8 |
| `cq12t-5ch` | 6–10 → 1–5 | Tested on CQ12T |
| `8ch` | 1–8 → 1–8 | Prepared for SQ, QU, and AES67; eight-mono operation unvalidated |
| `cq18t-8ch` / `cq20b-8ch` | 9–16 → 1–8 | Hardware validation pending |

Each path has one De-Feedback instance, explicitly checked for one input and one output, and one mono hardware send. Master sends are disabled. Tracks start **unmuted, with monitoring and FX enabled**. Keep console inserts bypassed until routing is verified; bypass FX for baseline latency measurements. The project rate is 48000 Hz. Audio-device selection and console/network patching are separate from the template.

The upper limit is **eight mono paths**. Four stereo instances were stable, and mono operation approximately halved CPU load. Eight-mono stability will be tested using AES67. See [test hardware and measurements](overview.md).

## CQ signal flow and channel mapping

CQ processed returns use separate mixer channels with **USB/SD** as their source. Keep dry source channels out of the listening mix while retaining their USB sends. Keep processed returns out of the USB sends feeding REAPER.

| Console | Source channels / REAPER inputs | REAPER outputs / processed return channels |
| --- | --- | --- |
| CQ12T — tested | 6, 7, 8, 9, 10 | 1, 2, 3, 4, 5 |
| CQ18T / CQ20B — unvalidated | 9, 10, 11, 12, 13, 14, 15, 16 | 1, 2, 3, 4, 5, 6, 7, 8 |

## Saved projects and preferences

Automatic projects are saved per device and channel count in `~/.local/state/defeedback/`. Subsequent launches reopen them and check mono plugin I/O. Move a saved project aside to regenerate it. Manual generation saves `templates/defeedback-PROFILE.RPP` beside the script and refuses to overwrite an existing file.

`reaper-cq12t.ini` and `reaper-evo8.ini` are generic audio preference seeds: 48000 Hz, 24-bit, 64 samples, and 3 periods. They contain no personal paths or recent history. The launcher applies detected device settings to its own INI; audio preferences are separate from `.RPP` routing and plugin state. See [automatic startup](setup.md#automatic-usb-startup).
