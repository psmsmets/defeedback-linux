#!/usr/bin/env bash
# Show post-install guidance and offer headless startup only in an interactive terminal.

show_setup_next_steps() {
    local mode=$1 appliance_tool=$2 answer=
    local unit="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/defeedback-reaper.service"
    printf '\nNext steps\n'
    printf '%s\n' \
        '  1. Run defeedback-linux and verify the Focusrite Scarlett audio path.' \
        '  2. In De-Feedback FX, click UI, then Options > License Management to activate.' \
        '  3. For headless USB startup, run defeedback-linux appliance setup.' \
        '     This enables automatic Plasma login, REAPER autostart, and workstation power/desktop settings.' \
        '     REAPER still uses a graphical session. AES67 service startup remains manual.' \
        '  Help: defeedback-linux --help or defeedback-linux appliance --help.'
    if [[ $mode == ask && -f $unit ]]; then
        printf 'An existing REAPER autostart service was found; its settings are kept.\n'
    elif [[ $mode == ask && -t 0 ]]; then
        printf '\nEnable headless startup for future logins now? [y/N] '
        IFS= read -r answer || answer=
        case $answer in
            y|Y|yes|YES|Yes) mode=true ;;
        esac
    fi
    if [[ $mode == true ]]; then
        bash "$appliance_tool"
    else
        printf 'To enable or reapply headless startup later: defeedback-linux appliance setup\n'
    fi
}
