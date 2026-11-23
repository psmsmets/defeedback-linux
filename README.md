# Alpha Labs De-Feedback on Linux

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. The plugin must be obtained and licensed separately.

Plugin and licensing: [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

Run the Windows De-Feedback VST3 on Ubuntu Studio with native Linux REAPER using yabridge and patched Wine. The hardware-aware launcher selects a supported USB device and opens its mono routing project.

- [Documentation](docs/README.md)
- [Workstation command](docs/commands.md)
- [Setup and operation](docs/setup.md)
- [Code and installation bundle](defeedback-linux/)

Use Focusrite Scarlett over USB for setup and initial audio tests. SQ and CQ USB profiles and Avantis and dLive AES67 profiles are available as explicit choices. Automatic AES67 startup remains planned.

See [test hardware and measurements](docs/overview.md) for validated configurations. The software limit is eight mono paths; eight-path audio and AES67 remain unvalidated.

After installation, run `defeedback-linux` to start audio and `defeedback-linux --help` for updates, licensing, AES67, and diagnostics.
