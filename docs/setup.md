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

## Changing the rules

Most rules are one number, and each of those is a control you move: `number.…_daily_limit`,
`number.…_warn_before`, `number.…_sleep_timer`, `switch.…_block_settings`, one per day of the
week, and one `number.…_limit` per app the TV has charged time to. Setting an app's limit to zero blocks it
outright — one mechanism rather than two, and the same convention as everywhere else here.
An app's limit appears once the TV has seen the app; twelve is the ceiling, for the same
reason the per-app sensors have one.

Two rules are not one number each, and those are actions aimed at `sensor.…_rules`:

| Action | What it changes |
|---|---|
| `tvsitter.set_schedule` | One day of the week's own allowance. Leave `minutes` out to remove the override and hand the day back to the daily limit; zero means no viewing that day. |
| `tvsitter.set_windows` | When viewing is allowed at all, as a raw list. For hours that no schedule can express; ordinarily use the schedule below. |
| `tvsitter.set_app_limit` | An app's own budget, by package id. For the two things the number cannot say: an app the television has never opened, and taking a budget away — zero there is a block, not an absence. |

`sensor.…_rules` shows what the TV says it is enforcing, as attributes, and its state is the
revision the two sides agree on. The revision is why every write goes through one place: the
TV ignores a `set_rules` whose revision is not higher than the one it holds, so two changes
in a row have to count up even before the TV has answered.

### The hours viewing is allowed

Home Assistant already has a weekly grid with a proper editor — the **Schedule** helper — and the
rules already carry windows with the days they apply on. They are the same picture, so TV Sitter
reads one and writes the other rather than shipping a second editor.

Make a schedule helper (Settings, then Devices & services, then Helpers), draw the week on it,
and run `tvsitter.use_schedule` once against this TV's rules sensor. The helper is remembered:
every later edit to the grid reaches the television by itself, and an edit made while the set is
asleep goes out when it wakes.

The grid itself lives one tap further in than it looks: tapping the schedule tile opens more-info,
which shows state and history, and the editor is behind the gear in that dialog.

Blocks that share their hours become one window rather than seven, a block drawn on every day
loses its `days` key altogether, and a block running to the end of the day closes at midnight —
so the rules stay something you can read when a lock surprises you.

Editing a whole week by hand is what the add-on is for (#60). These are enough to set one
without it.

## The dashboard

Entities are plumbing. The surface a parent opens is
[`dashboards/tvsitter.yaml`](../dashboards/tvsitter.yaml): what is on now and one tap to lock it,
today by app and the last week, the rules, and — last, because it is only interesting when
something is wrong — whether the television is still reporting.

Settings, then Dashboards, then add one, open its three-dot menu, choose "Raw configuration
editor" and paste the file in. Every entity in it starts with `tv_lounge`, the slug Home Assistant
made from the name you gave the television; search and replace that one word with yours and the
whole file works. The per-app rows are whatever this house's television has opened, so delete the
ones you do not have and add the ones you do.

No custom card is shipped with it. A Lovelace card is a separate HACS category from an
integration, which by D6 means either a second repository or serving frontend code from this one,
and the built-in cards answer every question on the list.

## The parent panel

Optional, and Home Assistant OS or Supervised only — Apps do not exist on Container or Core.
The panel is a second interface onto the integration, not a second way to reach the televisions:
it talks to Home Assistant and never to your broker, so the integration stays the only thing
publishing a rule change (D34).

Add this repository under **Settings > Apps > App store**, three-dot menu, **Repositories**:

```
https://github.com/TomaszSyc/tvsitter
```

Then install **TV Sitter parent panel**. It appears in the sidebar and has nothing to configure.

Today it is one page listing the televisions the integration can see. Everything the integration
already does — the entities, the actions, the dashboard above — works without it.

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

### If you wear a watch

Measured rather than assumed, because the documentation and the behaviour disagree.

Sending only to the phone put nothing at all on the watch. Android bridges phone notifications
to a watch by default, but an app that ships its own watch app opts out to avoid duplicates,
and the Home Assistant companion app does exactly that.

So the blueprint offers a second notify action. Sending to the watch as well makes it arrive —
and in testing the buttons were there, which the companion app's documented field list does not
promise: it names `channel`, `message`, `notification_icon`, `tag`, `title` and
`vibrationPattern`, and `actions` is not among them. Undocumented is not the same as unsupported,
and one measurement is not a guarantee, so treat the buttons on the watch as a bonus rather than
the plan.

If they are missing on yours, there are two honest options: answer on the phone and let the watch
be a heads-up, or take the companion app off the watch entirely, after which Wear OS relays the
phone's notification and renders its buttons itself.

The blueprint also clears the notification on both once the request is answered, so a stale tap
cannot grant time twice.

## Inventory of the child's apps

Package names needed when writing rules:

```bash
adb shell pm list packages -3        # user-installed
adb shell pm list packages -s        # system, including "Watch TV" and HDMI inputs
```
