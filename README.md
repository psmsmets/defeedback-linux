# Alpha Labs De-Feedback on Linux

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. REAPER and Alpha Labs De-Feedback are separately licensed products. This project includes neither license. Obtain and activate each product according to its vendor's terms.

Products and licensing: [REAPER](https://www.reaper.fm/purchase.php) · [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

Run the Windows De-Feedback VST3 on Ubuntu Studio with native Linux REAPER using yabridge and patched Wine. The hardware-aware launcher selects a supported USB device and opens its mono routing project. The goal is a headless appliance that loads the appropriate audio settings at boot for USB or AES67 via the second network port. USB selection is implemented. Boot without a monitor has been validated on the reference Beelink. Full automatic AES67 service startup is planned: when no supported USB audio device is available, the launcher must use a ready AES67 connection on the second network port and start four mono paths initially, with eight as the upper limit. See [startup selection](docs/setup.md#startup-selection).

This project grew out of a personal preference for Linux and difficulty obtaining a Windows 11 IoT Enterprise LTSC license. I would rather put that budget toward a REAPER license and explore running De-Feedback on Linux. This is an independent compatibility experiment, with test results and remaining limitations documented here.

- [Documentation](docs/README.md)
- [Workstation command](docs/commands.md)
- [Setup and operation](docs/setup.md)
- [Code and installation bundle](defeedback-linux/)

Use Focusrite Scarlett over USB for setup and initial audio tests. SQ and CQ USB profiles and Avantis and dLive AES67 profiles are available as explicit choices.

See [test hardware and measurements](docs/overview.md) for validated configurations. The software limit is eight mono paths; eight-path audio and AES67 remain unvalidated.

After installation, run `defeedback-linux` to start audio and `defeedback-linux --help` for updates, licensing, AES67, and diagnostics.
