#!/usr/bin/env bash
#
# Device bring-up and spike helpers for TV Sitter.
#
# The commands here are the executable version of docs/setup.md. They exist as a script
# rather than prose because two of the steps are easy to get wrong by hand: the
# accessibility service list is a single colon-separated setting that must be appended to
# rather than overwritten, and several checks silently look like success when they have in
# fact done nothing.
#
# Usage: tools/device.sh <command>
# Run without arguments for the list.
#
# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

DEVICE="${TVSITTER_DEVICE:-<tv-ip>:5555}"
PKG="app.tvsitter.tv"
SERVICE="$PKG/$PKG.EnforcerService"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="$REPO_ROOT/app/build/outputs/apk/debug/app-debug.apk"

say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; }
info() { printf '    %s\n' "$1"; }

adb_() { adb -s "$DEVICE" "$@"; }

require_device() {
    adb connect "$DEVICE" >/dev/null 2>&1 || true
    local state
    state="$(adb devices | awk -v d="$DEVICE" '$1 == d {print $2}')"
    case "$state" in
    device)
        return 0
        ;;
    unauthorized)
        bad "$DEVICE reports 'unauthorized'"
        info "Accept the 'Allow debugging?' dialog on the TV with the remote, ticking"
        info "'always allow from this computer'. Home Assistant's own ADB key does not"
        info "authorise this machine."
        exit 1
        ;;
    "")
        bad "$DEVICE is not responding"
        info "Check the TV is on, and that Developer options → Network debugging is enabled."
        exit 1
        ;;
    *)
        bad "$DEVICE is in state '$state'"
        exit 1
        ;;
    esac
}

cmd_doctor() {
    require_device
    say "Device"
    for prop in ro.product.manufacturer ro.product.model ro.build.version.release \
        ro.build.version.sdk ro.build.display.id; do
        info "$prop = $(adb_ shell getprop "$prop" | tr -d '\r')"
    done

    say "TV Sitter"
    if adb_ shell pm list packages | tr -d '\r' | grep -qx "package:$PKG"; then
        ok "installed, version $(adb_ shell dumpsys package "$PKG" |
            awk -F= '/versionName/ {print $2; exit}' | tr -d '\r')"
    else
        bad "not installed — run: tools/device.sh install"
    fi

    say "Permissions"
    for op in ACCESS_RESTRICTED_SETTINGS GET_USAGE_STATS; do
        local mode
        mode="$(adb_ shell appops get "$PKG" "$op" 2>/dev/null | tr -d '\r' || true)"
        if [[ "$mode" == *allow* ]]; then ok "$op: $mode"; else bad "$op: ${mode:-not set}"; fi
    done

    say "Accessibility service"
    local enabled
    enabled="$(adb_ shell settings get secure enabled_accessibility_services | tr -d '\r')"
    if [[ "$enabled" == *"$SERVICE"* ]]; then
        ok "listed as enabled"
    else
        bad "not in the list — run: tools/device.sh enable-a11y"
        info "current list: ${enabled}"
    fi
    local master
    master="$(adb_ shell settings get secure accessibility_enabled | tr -d '\r')"
    if [[ "$master" == "1" ]]; then
        ok "accessibility master switch on"
    else
        bad "master switch off ($master)"
    fi

    # The authority is the bound-services list, not the log. After a reboot the log buffer
    # rotates and a log-only check reports a false negative exactly when it matters most.
    if adb_ shell dumpsys accessibility 2>/dev/null | grep -q "Service\[label=TV Sitter"; then
        ok "bound and running (dumpsys accessibility)"
        adb_ shell dumpsys accessibility 2>/dev/null |
            grep -oE "label=TV Sitter.{0,60}capabilities=[0-9]+" | head -1 | sed 's/^/    /'
    else
        bad "not bound — the service is listed as enabled but is not running"
    fi

    if adb_ logcat -d -s TVSitter:I 2>/dev/null | grep -q onServiceConnected; then
        info "onServiceConnected() still in the log buffer"
    fi

    local uptime_s process_age
    uptime_s="$(adb_ shell cat /proc/uptime | cut -d. -f1 | tr -d '\r')"
    process_age="$(adb_ shell ps -A -o ETIME,NAME 2>/dev/null | awk '/app.tvsitter.tv/ {print $1; exit}' | tr -d '\r')"
    [[ -n "$process_age" ]] && info "device up ${uptime_s}s, our process alive ${process_age}"
}

cmd_install() {
    require_device
    say "Building"
    (cd "$REPO_ROOT" && ./gradlew --quiet :app:assembleDebug)
    [[ -f "$APK" ]] || {
        bad "APK not found at $APK"
        exit 1
    }
    ok "$(du -h "$APK" | cut -f1) at $APK"

    say "Installing"
    adb_ install -r "$APK"

    say "Granting permissions the remote cannot grant"
    # Android 13+ hides accessibility behind a "restricted setting" for sideloaded apps,
    # and Google TV usually has no UI entry to lift it.
    adb_ shell appops set "$PKG" ACCESS_RESTRICTED_SETTINGS allow
    adb_ shell appops set "$PKG" GET_USAGE_STATS allow
    for op in ACCESS_RESTRICTED_SETTINGS GET_USAGE_STATS; do
        local mode
        mode="$(adb_ shell appops get "$PKG" "$op" | tr -d '\r')"
        if [[ "$mode" == *allow* ]]; then
            ok "$op: $mode"
        else
            bad "$op did not take: $mode"
        fi
    done
}

cmd_enable_a11y() {
    require_device
    say "Enabling the accessibility service"
    local current
    current="$(adb_ shell settings get secure enabled_accessibility_services | tr -d '\r')"

    # This setting is one colon-separated field shared by every accessibility service on
    # the device. Overwriting it would silently disable whatever else the user relies on.
    case "$current" in
    *"$SERVICE"*)
        ok "already present"
        ;;
    null | "")
        adb_ shell settings put secure enabled_accessibility_services "$SERVICE"
        ok "list was empty, set to $SERVICE"
        ;;
    *)
        adb_ shell settings put secure enabled_accessibility_services "$current:$SERVICE"
        ok "appended to existing list ($current)"
        ;;
    esac
    adb_ shell settings put secure accessibility_enabled 1

    say "Verifying"
    sleep 2
    if adb_ logcat -d -s TVSitter:I | grep -q onServiceConnected; then
        ok "service connected"
        adb_ logcat -d -s TVSitter:I | grep onServiceConnected | tail -1 | sed 's/^/    /'
    else
        bad "no onServiceConnected() yet"
        info "On Android 13+ the setting can be written and still refused. Open"
        info "Settings → Accessibility → TV Sitter on the TV and check what it says."
    fi
}

cmd_inventory() {
    require_device
    local out="$REPO_ROOT/build/device-packages.txt"
    mkdir -p "$(dirname "$out")"
    say "Package inventory"
    {
        echo "# $(adb_ shell getprop ro.product.model | tr -d '\r'), API $(adb_ shell getprop ro.build.version.sdk | tr -d '\r')"
        echo "# user-installed"
        adb_ shell pm list packages -3 | tr -d '\r' | sed 's/^package://' | sort
        echo "# system"
        adb_ shell pm list packages -s | tr -d '\r' | sed 's/^package://' | sort
    } >"$out"
    ok "$(grep -cv '^#' "$out") packages written to $out"
}

cmd_watch() {
    require_device
    say "Watching TVSitter log — Ctrl-C to stop"
    adb_ logcat -c
    adb_ logcat -s TVSitter:V
}

# Since Android 8, receivers declared in a manifest do not receive implicit broadcasts,
# so the component has to be addressed explicitly. Without -n the broadcast is accepted,
# reports "result=0" and silently runs nothing.
RECEIVER="$PKG/.DebugCommandReceiver"

broadcast() {
    adb_ shell am broadcast -n "$RECEIVER" -a "$PKG.$1" "${@:2}" >/dev/null
}

# adb shell concatenates its arguments into one command line that the device shell splits
# again, so anything containing spaces has to survive a second round of quoting.
shell_quote() { printf "'%s'" "${1//\'/\'\\\'\'}"; }

cmd_lock() {
    require_device
    broadcast LOCK --es reason "$(shell_quote "${2:-spike lock test}")"
    ok "lock broadcast sent"
}

cmd_unlock() {
    require_device
    broadcast UNLOCK
    ok "unlock broadcast sent"
}

cmd_status() {
    require_device
    # The buffer is deliberately not cleared: the log is the only record of what the
    # service has seen, and clearing it destroyed that evidence once already. Taking the
    # last matching lines is enough, since new ones are appended.
    broadcast STATUS
    sleep 1
    adb_ logcat -d -s TVSitter:I | grep -E "STATUS|not connected" | tail -2 | sed 's/^/    /'
}

cmd_reboot_test() {
    require_device
    say "Reboot survival test"
    info "The counter lives in the accessibility service because the system is supposed to"
    info "restart it after a reboot. This measures whether that holds, and how long the gap is."
    adb_ reboot
    local start
    start="$(date +%s)"
    info "rebooting; waiting for the device to answer again"
    # The device state has to come from `adb devices`, not from the output of `adb connect`.
    # A stale entry makes connect answer "already connected" even while the device is down,
    # so matching on its output loops forever — which it did the first time this ran.
    local waited_boot=0
    until [[ "$(adb devices | awk -v d="$DEVICE" '$1 == d {print $2}')" == "device" ]]; do
        adb connect "$DEVICE" >/dev/null 2>&1 || true
        sleep 5
        waited_boot=$((waited_boot + 5))
        if [[ $waited_boot -ge 300 ]]; then
            bad "device did not come back within ${waited_boot}s"
            return 1
        fi
    done
    ok "reachable after $(($(date +%s) - start))s"

    local waited=0
    until adb_ logcat -d -s TVSitter:I 2>/dev/null | grep -q onServiceConnected; do
        sleep 5
        waited=$((waited + 5))
        if [[ $waited -ge 180 ]]; then
            bad "no onServiceConnected() within ${waited}s after reboot"
            info "That is a finding, not a script failure — record it on issue #5."
            return 1
        fi
    done
    ok "service back ${waited}s after the device answered"
    say "Ordering of events"
    adb_ logcat -d -s TVSitter:I | grep -E "onServiceConnected|BOOT_COMPLETED" | sed 's/^/    /'
}

usage() {
    cat <<EOF
tools/device.sh <command>          target: $DEVICE (override with TVSITTER_DEVICE)

  doctor        report device, install, permission and service state
  install       build the debug APK, install it, grant the ADB-only permissions
  enable-a11y   enable the accessibility service without clobbering other services
  inventory     dump the installed package list to build/device-packages.txt
  watch         tail the TVSitter log
  lock [reason] show the lock screen (debug builds only)
  unlock        dismiss the lock screen
  status        ask the service for its current state
  reboot-test   reboot the TV and measure whether the service comes back
EOF
}

case "${1:-}" in
doctor) cmd_doctor ;;
install) cmd_install ;;
enable-a11y) cmd_enable_a11y ;;
inventory) cmd_inventory ;;
watch) cmd_watch ;;
lock) cmd_lock "$@" ;;
unlock) cmd_unlock ;;
status) cmd_status ;;
reboot-test) cmd_reboot_test ;;
*) usage ;;
esac
