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
    for op in SYSTEM_ALERT_WINDOW GET_USAGE_STATS; do
        local mode
        mode="$(adb_ shell appops get "$PKG" "$op" 2>/dev/null | tr -d '\r' || true)"
        if [[ "$mode" == *allow* ]]; then ok "$op: $mode"; else bad "$op: ${mode:-not set}"; fi
    done

    say "Enforcer"
    if adb_ shell dumpsys activity services "$PKG" 2>/dev/null | grep -q "EnforcerService"; then
        ok "service is running"
        adb_ shell dumpsys activity services "$PKG" 2>/dev/null |
            grep -oE "isForeground=[a-z]+" | head -1 | sed 's/^/    /'
    else
        bad "not running — run: tools/device.sh start"
    fi

    local uptime_s process_age
    uptime_s="$(adb_ shell cat /proc/uptime | cut -d. -f1 | tr -d '\r')"
    process_age="$(adb_ shell ps -A -o ETIME,NAME 2>/dev/null | awk '/app.tvsitter.tv/ {print $1; exit}' | tr -d '\r')"
    [[ -n "$process_age" ]] && info "device up ${uptime_s}s, our process alive ${process_age}"

    say "Accessibility"
    local enabled
    enabled="$(adb_ shell settings get secure enabled_accessibility_services | tr -d '\r')"
    if [[ "$enabled" == *"$PKG"* ]]; then
        bad "an old TV Sitter accessibility service is still enabled"
        info "Since D16 the app does not use one. Merely having an accessibility service"
        info "enabled unmasks password fields system-wide, so remove it:"
        info "  tools/device.sh disable-a11y"
    else
        ok "no accessibility service, as intended since D16"
    fi
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
    # Google TV has no UI to give a sideloaded app either of these. An app-op only takes
    # effect for a permission the app declares, which both of these are.
    adb_ shell appops set "$PKG" SYSTEM_ALERT_WINDOW allow
    adb_ shell appops set "$PKG" GET_USAGE_STATS allow
    for op in SYSTEM_ALERT_WINDOW GET_USAGE_STATS; do
        local mode
        mode="$(adb_ shell appops get "$PKG" "$op" | tr -d '\r')"
        if [[ "$mode" == *allow* ]]; then
            ok "$op: $mode"
        else
            bad "$op did not take: $mode"
        fi
    done

    cmd_start
}

cmd_start() {
    require_device
    say "Starting the enforcer"
    # Through the activity, not `am start-foreground-service`: the service is not exported,
    # so the shell cannot start it directly — and it should stay that way. Opening the app is
    # also exactly what a user does after installing it, since nothing else starts the
    # service until the next reboot.
    adb_ shell am start -n "$PKG/.SetupActivity" >/dev/null 2>&1
    sleep 3
    if adb_ shell dumpsys activity services "$PKG" 2>/dev/null | grep -q "EnforcerService"; then
        ok "running"
        adb_ logcat -d -s TVSitter:I | grep -E "onCreate|mqtt:" | tail -3 | sed 's/^/    /'
    else
        bad "did not start"
    fi
}

# Only for cleaning up after the pre-D16 builds.
cmd_disable_a11y() {
    require_device
    say "Removing the accessibility service"
    adb_ shell settings delete secure enabled_accessibility_services >/dev/null
    adb_ shell settings put secure accessibility_enabled 0
    ok "removed; password fields will mask again"
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

# Broker settings, so they need not be typed with a remote. The password reaches the device
# as a broadcast extra and therefore appears in the system log: fine for a debug build,
# which is the only kind that carries this receiver.
cmd_configure() {
    require_device
    local host="" port="" user="" pass="" prefix="" tls=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
        --host) host="$2"; shift 2 ;;
        --port) port="$2"; shift 2 ;;
        --user) user="$2"; shift 2 ;;
        --pass) pass="$2"; shift 2 ;;
        --prefix) prefix="$2"; shift 2 ;;
        --tls) tls="$2"; shift 2 ;;
        *) shift ;;
        esac
    done

    local args=()
    [[ -n "$host" ]] && args+=(--es host "$(shell_quote "$host")")
    [[ -n "$port" ]] && args+=(--es port "$port")
    [[ -n "$user" ]] && args+=(--es user "$(shell_quote "$user")")
    [[ -n "$pass" ]] && args+=(--es pass "$(shell_quote "$pass")")
    [[ -n "$prefix" ]] && args+=(--es prefix "$(shell_quote "$prefix")")
    [[ -n "$tls" ]] && args+=(--es tls "$tls")

    if [[ ${#args[@]} -eq 0 ]]; then
        bad "nothing to set; pass at least one of --host --port --user --pass --prefix --tls"
        return 1
    fi

    broadcast CONFIGURE "${args[@]}"
    sleep 2
    adb_ logcat -d -s TVSitter:I | grep -E "configured:|mqtt:" | tail -4 | sed 's/^/    /'
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
    info "Since D16 nothing revives the enforcer for free. The accessibility service it"
    info "replaced came back on its own about 27 seconds after boot (D13); a foreground"
    info "service has to restart itself from BOOT_COMPLETED, so this measures whether it"
    info "does and how long enforcement is absent."
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
    local reachable_at=$(($(date +%s) - start))
    ok "reachable after ${reachable_at}s"

    local waited=0
    until adb_ shell ps -A -o NAME 2>/dev/null | grep -q "app.tvsitter.tv"; do
        sleep 5
        waited=$((waited + 5))
        if [[ $waited -ge 180 ]]; then
            bad "the enforcer did not start within ${waited}s of the device answering"
            info "That is a finding, not a script failure — it is the gap D16 warned about."
            info "Log so far:"
            adb_ logcat -d -s TVSitter:V | tail -5 | sed 's/^/      /' || true
            return 1
        fi
    done
    ok "enforcer running ${waited}s after the device answered (~$((reachable_at + waited))s from reboot)"

    say "What the log says"
    # `|| true` because grep exits non-zero when nothing matches, and under `set -o pipefail`
    # that aborts the whole run — losing the measurement that had already succeeded.
    adb_ logcat -d -s TVSitter:V | grep -E "BOOT_COMPLETED|onCreate|mqtt:" | head -6 |
        sed 's/^/    /' || true

    say "Process age against uptime"
    local uptime_s process_age
    uptime_s="$(adb_ shell cat /proc/uptime | cut -d. -f1 | tr -d '\r')"
    process_age="$(adb_ shell ps -A -o ETIME,NAME 2>/dev/null | awk '/app.tvsitter.tv/ {print $1; exit}' | tr -d '\r')"
    info "device up ${uptime_s}s, our process alive ${process_age}"
}

usage() {
    cat <<EOF
tools/device.sh <command>          target: $DEVICE (override with TVSITTER_DEVICE)

  doctor        report device, install, permission and service state
  install       build the debug APK, install it, grant the ADB-only permissions
  start         start the enforcer foreground service
  disable-a11y  remove the accessibility service left by pre-D16 builds
  inventory     dump the installed package list to build/device-packages.txt
  watch         tail the TVSitter log
  lock [reason] show the lock screen (debug builds only)
  unlock        dismiss the lock screen
  status        ask the service for its current state
  configure     set broker settings: --host --port --user --pass --prefix --tls
  reboot-test   reboot the TV and measure whether the service comes back
EOF
}

case "${1:-}" in
doctor) cmd_doctor ;;
install) cmd_install ;;
start) cmd_start ;;
disable-a11y) cmd_disable_a11y ;;
inventory) cmd_inventory ;;
watch) cmd_watch ;;
lock) cmd_lock "$@" ;;
unlock) cmd_unlock ;;
status) cmd_status ;;
configure) shift; cmd_configure "$@" ;;
reboot-test) cmd_reboot_test ;;
*) usage ;;
esac
