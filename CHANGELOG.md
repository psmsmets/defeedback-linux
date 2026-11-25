# Changelog

## 0.1.0-alpha.1 — Unreleased

First experimental prerelease of the unofficial Linux integration for Alpha Labs De-Feedback. Intended for setup experiments and hardware testing on Ubuntu Studio.

### Included

- Setup and update tools for native Linux REAPER, yabridge, and patched Wine, with De-Feedback license management through VSTHost.
- Hardware-aware USB selection and independent mono routing, with Focusrite Scarlett as the initial test profile and a maximum of eight paths.
- Optional Plasma autologin and REAPER autostart, bounded text logs, and diagnostic commands.
- Manual AES67 network/PTP/PipeWire configuration and an opt-in early REAPER fallback for testing.
- `defeedback-linux --version`, versioned installation metadata, and integration version reporting in session logs and diagnostics.

### Validation and limitations

See [validation status](docs/overview.md#validation-status) for the tested hardware, measurements, and screenshots. USB testing includes the documented Scarlett latency measurement and EVO8 appliance autostart with four mono plugin instances. Monitor-free boot has been validated on the reference Beelink.

The complete AES67 insert loop still requires hardware validation. Automatic PTP/audio-helper startup and automatic failure recovery are not implemented. Sustained stability, latency, and recovery require further testing for each intended configuration.

REAPER and Alpha Labs De-Feedback require separate vendor licenses. This release contains the integration scripts and documentation; vendor installers, activations, and Wine prefixes are excluded.
