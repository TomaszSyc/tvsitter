# Installing on the TV

> **Status: not yet verified on hardware.** The steps below follow from the Android
> documentation, not from a successful run on the Philips TA5. The questions the first
> run is meant to answer are listed in `architecture.md`. This note disappears once they
> are answered.

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
adb logcat -s TVSitter:*
```

Enabling the service must produce an `onServiceConnected()` line, followed by a
`foreground=<package>` line every time the app on the TV changes.

There is also a diagnostics screen on the TV itself — the **TV Sitter** tile in the
launcher shows permission state and the app currently detected.

In **debug** builds the lock can be driven from your computer, without the remote:

```bash
adb shell am broadcast -a app.tvsitter.tv.LOCK --es reason "lock test"
adb shell am broadcast -a app.tvsitter.tv.STATUS
adb shell am broadcast -a app.tvsitter.tv.UNLOCK
```

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

## Inventory of the child's apps

Package names needed when writing rules:

```bash
adb shell pm list packages -3        # user-installed
adb shell pm list packages -s        # system, including "Watch TV" and HDMI inputs
```
