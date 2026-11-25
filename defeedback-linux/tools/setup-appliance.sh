#!/usr/bin/env bash
# Configure Ubuntu Studio as a dedicated De-Feedback workstation.
set -euo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf '%s\n' 'Usage: defeedback-linux appliance setup' \
        'Enables desktop autologin, REAPER autostart, and appliance power settings.' \
        'Requires an installed workstation. First run bash setup-defeedback.sh from the Linux bundle.' \
        'To install and configure autostart together, run bash setup-defeedback.sh --appliance.' \
        'Interactive installation also offers this step, defaulting to no; --no-appliance skips the question.' \
        'USB settings load at launch. AES67 startup remains manual.' \
        'Run as the account that should log in automatically, from its Ubuntu Studio Plasma desktop.'
    exit 0
fi
[[ $# -eq 0 ]] || fail 'Usage: defeedback-linux appliance setup'
[[ $(uname -s) == Linux && $EUID -ne 0 ]] || fail 'Run as your desktop user on Ubuntu Studio.'
[[ ${XDG_CURRENT_DESKTOP:-} == *KDE* ]] || fail 'Run from the target user’s Plasma desktop session.'
[[ -x $HOME/.local/share/defeedback/bin/reaper ]] || fail 'First run bash setup-defeedback.sh from the Linux bundle, then run defeedback-linux appliance setup.'
for command in systemctl sudo kwriteconfig6; do
    command -v "$command" >/dev/null || fail "Missing command: $command"
done
systemctl is-active --quiet sddm.service || fail 'The appliance profile requires SDDM.'
systemctl --user is-active --quiet graphical-session.target ||
    fail 'The Plasma systemd user session is not active.'

# Keep the display protocol that is already working on this machine.
case ${XDG_SESSION_TYPE:-} in
    wayland) session_file=/usr/share/wayland-sessions/plasma.desktop ;;
    x11) session_file=/usr/share/xsessions/plasmax11.desktop ;;
    *) fail 'Could not detect a Plasma Wayland or X11 session.' ;;
esac
[[ -f $session_file ]] || fail "SDDM session file is missing: $session_file"

login_user=$(id -un)
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}"
unit_dir="$config_dir/systemd/user"
mkdir -p -- "$unit_dir"

cat > "$unit_dir/defeedback-reaper.service" <<'EOF'
[Unit]
Description=REAPER for De-Feedback
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=exec
ExecStartPre=/usr/bin/sleep 3
ExecStart="%h/.local/share/defeedback/bin/reaper"

[Install]
WantedBy=graphical-session.target
EOF

# Start a fresh Plasma session so it does not also restore an old REAPER window.
kwriteconfig6 --file ksmserverrc --group General --key loginMode emptySession
kwriteconfig6 --file kdeglobals --group Sounds --key Enable --type bool false
kwriteconfig6 --file baloofilerc --group 'Basic Settings' --key Indexing-Enabled --type bool false
kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock --type bool false

# PowerDevil handles the power button while Plasma owns the key.
# Its action IDs are NoAction=0 and Shutdown=8.
for profile in AC Battery LowBattery; do
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key AutoSuspendAction 0
    kwriteconfig6 --file powerdevilrc --group "$profile" --group SuspendAndShutdown --key PowerButtonAction 8
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key DimDisplayWhenIdle --type bool false
    kwriteconfig6 --file powerdevilrc --group "$profile" --group Display --key TurnOffDisplayWhenIdle --type bool false
done
if command -v powerprofilesctl >/dev/null && powerprofilesctl list | grep -qE '^[[:space:]*]*performance:'; then
    kwriteconfig6 --file powerdevilrc --group AC --group Performance --key PowerProfile performance
else
    printf '%s\n' 'The system does not advertise a performance power profile.'
fi

# Logind handles the power button when the desktop does not own the key.
sudo install -d -m 755 /etc/systemd/logind.conf.d /etc/systemd/sleep.conf.d
sudo tee /etc/systemd/logind.conf.d/90-defeedback-appliance.conf >/dev/null <<'EOF'
[Login]
IdleAction=ignore
HandlePowerKey=poweroff
EOF
sudo tee /etc/systemd/sleep.conf.d/90-defeedback-appliance.conf >/dev/null <<'EOF'
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
EOF

# The main SDDM file takes precedence over drop-ins, including existing login settings.
# Preserve the original main file on the first run if it exists.
sddm_config=/etc/sddm.conf
sddm_backup=/etc/sddm.conf.before-defeedback
if sudo test -f "$sddm_config" && ! sudo test -e "$sddm_backup"; then
    sudo cp -p -- "$sddm_config" "$sddm_backup"
fi
sudo kwriteconfig6 --file "$sddm_config" --group Autologin --key Session "${session_file##*/}"
sudo kwriteconfig6 --file "$sddm_config" --group Autologin --key Relogin --type bool false
sudo kwriteconfig6 --file "$sddm_config" --group Autologin --key User "$login_user"

# Prevent automatic activation through D-Bus, sockets, and path units.
installed_units=$(systemctl list-unit-files --no-legend --no-pager \
    ModemManager.service cups-browsed.service cups.path cups.socket cups.service)
unused_units=()
while read -r unit _; do
    [[ -n $unit ]] && unused_units+=("$unit")
done <<< "$installed_units"
if (( ${#unused_units[@]} > 0 )); then
    sudo systemctl mask --now "${unused_units[@]}"
fi

systemctl --user daemon-reload
systemctl --user enable defeedback-reaper.service
printf '\nAutomatic login is configured for %s (%s).\n' "$login_user" "${session_file##*/}"
printf '%s\n' 'Reboot when ready to apply the login and power settings and test REAPER autostart.'
