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
adb connect <tv-ip>:5555
adb devices -l
```

The address is under Settings → Network on the TV. `tools/device.sh` finds it from
`$TVSITTER_DEVICE`, or from `tools/device.local` (git-ignored, one line:
`TVSITTER_DEVICE=<tv-ip>:5555`), or from `adb devices` when exactly one device is
attached. No address is committed — every household has a different one.

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

# The lock is drawn as a TYPE_APPLICATION_OVERLAY window. Google TV has no UI to grant
# this to a sideloaded app. Note that an app-op only takes effect for a permission the
# app declares — granting one it does not ask for silently does nothing, which is a
# confusing hour to lose.
adb shell appops set "$PKG" SYSTEM_ALERT_WINDOW allow

# Foreground-app detection reads usage events. Android TV lacks the settings screen this
# is normally granted from.
adb shell appops set "$PKG" GET_USAGE_STATS allow
```

No accessibility service is involved. That is deliberate, and the reason is worth knowing:
merely having one enabled makes apps stop masking password fields, so a parent typing their
account PIN on the TV does it in front of an audience. See D15 and D16 in
`architecture.md`.

If you ran a build from before that change, remove the leftover service:

```bash
tools/device.sh disable-a11y
```

## 4. Start it once

```bash
tools/device.sh start
```

**This step is not optional and is easy to miss.** Installing an app does not start it, and
nothing else will until the next reboot — the accessibility service this replaced was started
by the system when it was enabled, and a foreground service is not. Opening TV Sitter from the
launcher does the same thing, which is what a user would do anyway.

After a reboot the enforcer restarts itself from `BOOT_COMPLETED`, which on the test device
arrives about 67 seconds into boot (D17). The television is usable before that, so there is a
real gap; #23 tracks closing it.

## 5. Check that it works

```bash
tools/device.sh doctor
```

Reports the device, the install, both app-ops and whether the enforcer is actually running —
plus a warning if a pre-D16 accessibility service is still enabled.

```bash
adb logcat -s TVSitter:*
```

Starting the service must produce `onCreate()`, and a `foreground=<package>` line within a
second or two of changing app on the TV. Detection is polled rather than pushed, so it lags
slightly by design.

There is also a diagnostics screen on the TV: the **TV Sitter** tile in the launcher shows
permission state and the app currently detected, and starting it also starts the enforcer.

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

## Setting the parent PIN

The PIN is what lifts a lock at the television itself, with the remote and nothing else. Set
the first one from Home Assistant: the `Parent PIN` text control on the TV's device page, four
digits. It is hashed in Home Assistant and only the hash is sent, so the PIN never
reaches the broker; the control itself holds nothing and stays `unknown` however many times it
is used.

Afterwards it can be changed at the television as well — open TV Sitter, choose **Change the
parent PIN**, and type the current one first. That path is there for the evening Home Assistant
is not reachable. A *first* PIN cannot be set at the television, because nothing there tells a
parent apart from a child except knowing the PIN (D23).

On the television the keypad is the shape the platform uses for its own PIN: up and down
move between rows of three digits, and left, centre and right take one of the three. The
fourth digit submits by itself and the back button deletes, so there is nothing to confirm
and nothing to reach for. Which is also why a PIN is four digits and not a range — see D23.

`binary_sensor.…_parent_pin_set` says whether there is one, and carries `changed_at` and
`changed_by` attributes, so a PIN changed at the set is visible here as soon as the broker is
reachable. A PIN forgotten entirely is answered by setting a new one from Home Assistant,
which does not need the old one. Five wrong guesses shut the keypad for five minutes, then
fifteen, then thirty — on the television and in the change screen alike, because both spend
the same attempts.

## Answering a request from your phone

When the child presses "ask a parent for more time", the TV publishes on `<prefix>/request`
and the integration fires `event.…_time_request`. The lock screen then says what happened —
asked, already asked, not yet, too many, granted, refused, or nobody answered — because a
button that swallows a press is a button pressed again. The limits behind those answers are in
`docs/mqtt-contract.md`; they live on the TV, so they hold with Home Assistant switched off. Answering it is one action:
`tvsitter.grant_time` with `minutes`, or `tvsitter.deny_time`. Both take an optional `req_id`
and answer the most recent request without one.

The notification with buttons is a blueprint, in
[`blueprints/automation/tvsitter/more_time_request.yaml`](../blueprints/automation/tvsitter/more_time_request.yaml).
Until this repository is public and the blueprint can be imported by URL, copy it into
`config/blueprints/automation/tvsitter/` and reload automations. It asks for two things: the
TV's time-request event, and the notify action for the parent's phone.

That action has to be the old-style `notify.mobile_app_…` service rather than a notify
entity. Only the old service carries `actions`, and those buttons are the whole point — a
watch mirrors them, so the answer is one tap without unlocking a phone.

The request id travels inside the button's action name, so a tap answers the request it was
asked about rather than whichever is newest, and answering an old notification still works.
The notification is tagged with the same id, so a second request replaces its own
notification instead of stacking up.

The wording in the blueprint is English, like the rest of the repository. It is the one piece
of text a parent reads every day, so it is worth editing to taste after importing.

## Inventory of the child's apps

Package names needed when writing rules:

```bash
adb shell pm list packages -3        # user-installed
adb shell pm list packages -s        # system, including "Watch TV" and HDMI inputs
```
