# Alpha Labs De-Feedback on Linux

Unofficial Linux integration for the Alpha Labs De-Feedback plugin. Not affiliated with or endorsed by Alpha Labs. REAPER and Alpha Labs De-Feedback are separately licensed products. This project includes neither license. Obtain and activate each product according to its vendor's terms.

Products and licensing: [REAPER](https://www.reaper.fm/purchase.php) · [Alpha Labs De-Feedback](https://www.alphalabsaudio.com/defeedback/).

Run the Windows De-Feedback VST3 on Ubuntu Studio with native Linux REAPER using yabridge and patched Wine. The hardware-aware launcher selects a supported USB device and opens its mono routing project. The goal is a headless appliance that loads the appropriate audio settings at boot for USB or AES67. USB selection is implemented. Boot without a monitor has been validated. Full automatic AES67 service startup is planned. See [startup selection](https://github.com/psmsmets/defeedback-linux/blob/main/docs/setup.md#startup-selection).

This project grew out of a personal preference for Linux and difficulty obtaining a Windows 11 IoT Enterprise LTSC license. I would rather put that budget toward a REAPER license and explore running De-Feedback on Linux. This is an independent compatibility experiment, with test results and remaining limitations documented here.

- [Documentation](docs/README.md)
- [Workstation command](docs/commands.md)
- [Setup and operation](docs/setup.md)
- [Code and installation bundle](defeedback-linux/)

See [test hardware and measurements](docs/overview.md) for validated configurations.

After installation, run `defeedback-linux` to start REAPER with the detected audio device. Use `defeedback-linux --help` for all available commands.

## Screenshots

REAPER after automatic appliance startup on the reference Beelink, with an Audient EVO8 detected over USB and four mono paths using the activated De-Feedback plugin. See [startup and routing](docs/setup.md#dedicated-workstation-startup).

![REAPER 7.86 with the Audient EVO8 and four mono De-Feedback instances after appliance autostart](docs/images/defeedback-reaper-evo8-4ch.png)

REAPER with an Allen & Heath CQ12T over USB and five mono De-Feedback paths, mapping inputs **6–10 → outputs 1–5**. See [CQ routing](docs/reaper-projects.md#cq-signal-flow-and-channel-mapping).

![REAPER 7.86 with the CQ12T and five mono De-Feedback instances, inputs 6–10 to outputs 1–5](docs/images/defeedback-reaper-cq12t-5ch.png)

Successful De-Feedback activation in VSTHost, with the installed REAPER and license-management desktop shortcuts visible. Run `defeedback-linux open-license-gui`, then follow the [activation steps](docs/setup.md#license-management-in-vsthost).

![De-Feedback license window showing Status: Activated in VSTHost, alongside the desktop shortcuts](docs/images/defeedback-license-vsthost.png)

These results were confirmed on 25 November 2026. See [validation status](docs/overview.md#validation-status) for the tested configurations and remaining work.
