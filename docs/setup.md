# Installing on the TV

> **Verified end to end on a Philips Google TV TA5 (TPV, Android 14, API 34)** on
> 2026-08-21. What the run established, including the traps, is in `architecture.md` as
> decisions D9 through D13.
>
> `tools/device.sh` performs all of this and checks the result of each step. Prefer it to
> running the commands by hand — two of them are easy to get wrong, and two more look like
> success when they have done nothing.

## What you need

On your computer:

```bash
brew install --cask android-commandlinetools android-platform-tools
brew install gradle
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
sdkmanager --sdk_root="$ANDROID_HOME" --install "platforms;android-37.1" "build-tools;37.0.0"
```

On the TV: Settings → System → About → tap "Build" seven times, then
Settings → System → Developer options → **Network debugging**.

## 1. Connect and authorise

```bash
adb connect 192.168.1.25:5555
adb devices -l
```

The first connection from a new computer pops up an "Allow debugging?" dialog **on the
TV**. It has to be accepted with the remote, ticking "always allow from this computer".
Until you do, `adb devices` reports `unauthorized` and nothing else will work. Home
Assistant has its own ADB key — authorising Home Assistant does not authorise your
computer.

**If no dialog ever appears** — which is what happened here — the daemon has already
recorded a refusal for your key and will not ask again. It keeps answering on port 5555 and
refusing every key, so `adb connect` reports `failed to authenticate` with nothing on screen
to accept. The fix, from the home screen rather than from inside a full-screen app:
Developer options → **Revoke debugging authorisations**, then toggle network debugging off
and on. Worth knowing: while the daemon was in that state, Home Assistant's own
previously-working ADB connection also went unavailable, so a rejected key appears to wedge
it for every client.

## 2. Install

```bash
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## 3. Permissions you cannot grant from the remote

```bash
PKG=app.tvsitter.tv

# Android 13+ blocks accessibility services for sideloaded apps ("restricted setting").
# Google TV usually has no "Allow restricted settings" entry in its UI, so this has to be
# unblocked over ADB.
adb shell appops set "$PKG" ACCESS_RESTRICTED_SETTINGS allow

# Usage access — Android TV lacks the settings screen this is normally granted from.
adb shell appops set "$PKG" GET_USAGE_STATS allow
```

## 4. Enable the accessibility service

Safest with the remote: Settings → Accessibility → TV Sitter → on.

Doing it over ADB requires care not to wipe services that are already enabled — that
setting is a single colon-separated field:

```bash
PKG=app.tvsitter.tv
SVC="$PKG/$PKG.EnforcerService"
CURRENT=$(adb shell settings get secure enabled_accessibility_services | tr -d '\r')

case "$CURRENT" in
  *"$SVC"*)   echo "already on the list" ;;
  null|"")    adb shell settings put secure enabled_accessibility_services "$SVC" ;;
  *)          adb shell settings put secure enabled_accessibility_services "$CURRENT:$SVC" ;;
esac

adb shell settings put secure accessibility_enabled 1
```

## 5. Check that it works

```bash
tools/device.sh doctor
```

Reports the device, the install, both app-ops and whether the service is actually bound.
The bound state comes from `dumpsys accessibility` rather than the log, because the log
buffer rotates during boot and a log-based check reports a false negative exactly when you
most want the answer.

```bash
adb logcat -s TVSitter:*
```

Enabling the service must produce an `onServiceConnected()` line, followed by a
`foreground=<package>` line every time the app on the TV changes.

There is also a diagnostics screen on the TV itself — the **TV Sitter** tile in the
launcher shows permission state and the app currently detected.

In **debug** builds the lock can be driven from your computer, without the remote:

```bash
R=app.tvsitter.tv/.DebugCommandReceiver
adb shell am broadcast -n $R -a app.tvsitter.tv.LOCK --es reason "lock test"
adb shell am broadcast -n $R -a app.tvsitter.tv.STATUS
adb shell am broadcast -n $R -a app.tvsitter.tv.UNLOCK
```

The `-n` is not optional. Since Android 8 a receiver declared in a manifest does not
receive implicit broadcasts, so without it `am broadcast` reports `result=0` and runs
nothing at all — it looks like it worked.

Easier: `tools/device.sh lock`, `status`, `unlock`.

The receiver handling those commands exists in debug builds only; it is absent from the
release manifest.

## Undoing it

```bash
PKG=app.tvsitter.tv
adb shell settings put secure accessibility_enabled 0
adb uninstall "$PKG"
```

Uninstalling the app also drops its `appops` entries. Turning network debugging back off
on the TV once you are done testing is a good idea.

## The Home Assistant side

Once TV Sitter is reporting, **do not also run the ADB-based `androidtv` integration against
the same TV.** It becomes redundant — screen state and the active app now arrive over MQTT —
and on at least one device it is actively harmful: on the Philips TA5 it logged 577
`off`↔`idle` state changes in 48 hours, which is noise in the recorder database and useless
as a signal. That measurement is what decision D1 rests on.

Worth keeping, if your TV has an equivalent: a **second, independent** source of power state,
such as `philips_js` for Philips sets. Not for control — TV Sitter needs nothing from it — but
as a witness for the tamper alarm in M5. "TV Sitter has gone quiet while the TV is powered on"
is only a meaningful alert if something other than TV Sitter can say the TV is on.

## Inventory of the child's apps

Package names needed when writing rules:

```bash
adb shell pm list packages -3        # user-installed
adb shell pm list packages -s        # system, including "Watch TV" and HDMI inputs
```
