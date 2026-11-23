# Repository instructions

Write all repository content in English, including documentation, code comments, CLI help, and user-facing script messages.

This is an unofficial Linux integration for Alpha Labs De-Feedback, not the plugin itself. Use `defeedback-linux` as the public command. Keep the unofficial status, separate REAPER and De-Feedback licensing, and vendor links clear in the README and CLI help.

Target Ubuntu Studio with Plasma. The goal is unattended live operation with settings and routing selected at startup for a connected USB device or AES67. Clearly distinguish implemented functionality, hardware-validated results, and planned work. Do not describe AES67 autostart or automatic recovery as working without supporting implementation and tests. Keep monitor-free boot validation consistent with the documented hardware results. The required startup policy is USB first, then AES67 on the second NIC if no supported USB device is available; ready AES67 defaults to four mono paths for initial testing, with a maximum of eight. An opt-in early AES67 fallback is implemented for testing: launch REAPER before readiness checks, then log link/PTP/endpoint state alongside it. Keep it disabled by default. Automatic PTP/audio service startup and routing remain planned.

Use Focusrite Scarlett over USB as the default profile for setup and initial audio tests. Keep Audient EVO8, Behringer UMC202HD, SQ and CQ USB support, and Avantis and dLive AES67 profiles available. Enforce a maximum of eight mono processing paths. Common USB settings are 48000 Hz, 24-bit, 64 samples, and three periods. Keep PipeWire/JACK as the current AES67 backend. Start AES67 plugin testing with four mono instances, retain eight transport channels and an eight-instance upper limit, and prioritize a working loop, round-trip measurement, then optimization. AES67 defaults to 48000 Hz and quantum 48, with the supported quantum choices retained; network buffering is separate from graph block duration and total insert latency.

Reserve the second wired interface for AES67 and keep control/Internet separate. The reference Beelink uses enp2s0 for AES67 and enp1s0 for control/Internet; confirm actual interface names. Default AES67 networking to automatic link-local without DHCP, gateway, or DNS. Keep DHCP and existing network configuration as explicit alternatives. Do not change the control interface as a side effect of audio setup.

Keep routine logging lightweight, bounded, and accessible through `defeedback-linux logs`. Use `--debug` for additional text diagnostics; logging and debug mode must never record audio. Do not add automatic device switching, restarts, or bypass behavior without an explicit design and validation for live use.

Keep documentation compact and generic. Preserve relevant test hardware and measurement details, with test results maintained in docs rather than duplicated here. Remove personal paths, unrelated devices, obsolete workflows, and development history. Use the public wrapper in user-facing examples where supported.

Keep internal components in defeedback-linux/lib/, REAPER template resources in defeedback-linux/reaper/, and operator tools in defeedback-linux/tools/. Update the installer, updater resource list, CLI help, documentation, and relevant tests together when commands or paths change. Preserve clean stdout for INI generation.
