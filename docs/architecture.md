# Architecture decisions

A record of what has been decided and why. New decisions are appended; existing ones are
not edited — if one stops applying it gets a note pointing at the decision that
superseded it.

## The hardware this is built on

- TV: **Philips Google TV TA5** (TPV, `PH1M_WW_9972`), **Android 14** (API 34).
- Home Assistant **2026.8.2** on HAOS, Mosquitto broker add-on, HACS.
- Notifications: `notify.mobile_app_pixel_9_pro` and `notify.mobile_app_pixel_watch_4`.

## D1 — Enforcement on the TV, not over ADB

The obvious approach is to drive the TV from Home Assistant through the `androidtv`
integration (ADB): `am force-stop`, `pm disable-user`, `input keyevent SLEEP`. Rejected,
because ADB is not stable enough on this hardware — the `media_player.philips_tb` entity
logged **577 `off`↔`idle` state changes in 48 hours**, 10–60 seconds apart, while the
independent `philips_js` integration reported clean, single transitions over the same
period. A lock that sometimes fails to fire is not a lock. On top of that, turning
network debugging off in Settings takes a child about fifteen seconds.

ADB remains an installation tool only (see `setup.md`).

## D2 — AccessibilityService as the foundation

An accessibility service provides three things at once, without root:

1. the `TYPE_WINDOW_STATE_CHANGED` event carrying the foreground package name — the only
   root-free, real-time source of "what is running right now",
2. the right to draw its own `TYPE_ACCESSIBILITY_OVERLAY` window without the
   `SYSTEM_ALERT_WINDOW` permission, which often cannot be granted from the UI on Google TV,
3. the system brings it back after a reboot and restarts it after the process is killed.

That is why the screen time counter lives in the accessibility service rather than in an
ordinary foreground service.

## D3 — Rules run locally on the TV; Home Assistant is configuration and UI

The blocking decision has to be made on the device. A Home Assistant outage, a dropped
Wi-Fi link or a broker restart must not unlock the TV. Home Assistant supplies the rules,
displays state, keeps the history and handles requests for extra time.

## D4 — MQTT as the transport

The broker is already running (Mosquitto add-on), it is local, it has LWT for detecting
that the app died, and it needs no cloud. Contract: `docs/mqtt-contract.md`.

## D5 — The Home Assistant side is a HACS integration, not MQTT Discovery

The app could publish MQTT Discovery payloads and create its own entities without a line
of Python. A custom integration in `custom_components/tvsitter/` was chosen instead,
because:

- HACS distributes integrations, and that is the intended distribution channel,
- it provides a config flow, translations, custom actions (`tvsitter.grant_time`) and an
  `event` entity for triggering automations — none of which Discovery alone gives,
- one source of entities beats two mechanisms competing for the same names.

Consequence: the app publishes **plain state JSON**, no discovery payloads. Anyone who
would rather not install the integration can hand-write MQTT entities from the same topics.

## D6 — One repository for both halves

HACS only requires `custom_components/<domain>/` and `hacs.json` in the repository root;
it does not forbid additional content, so the Gradle project can sit alongside.

In favour of the monorepo: the MQTT contract changes in a single commit across both sides,
there is one issue tracker (a user cannot tell which half is at fault anyway), and the two
halves cannot drift apart in version.

The accepted cost: HACS derives the integration version from the **repository's latest
release**, so a release that only touches the TV app also bumps the integration version,
and users see an update in which nothing changed for them. Adopted resolution: **a single
SemVer version for the whole product** — the two halves have to match each other anyway.
Should this become annoying, splitting the integration into its own repository while
keeping history is a `git subtree split`.

## D7 — Toolchain versions

- **AGP 9.3.1** ships built-in Kotlin support and explicitly rejects the
  `org.jetbrains.kotlin.android` plugin, so `:app` does not apply it.
- **compileSdk / targetSdk 37**, forced by `androidx.core:core-ktx` 1.19.0, which refuses
  to be compiled against anything lower.
- **minSdk 26** (Android 8), so that `java.time` works without desugaring; older Android
  TV releases are not a realistic target.
- Gradle 9.7.1 (wrapper committed), JDK 21.

## D8 — The lock screen uses plain views, not Compose

An accessibility window has none of the lifecycle owners Compose expects. `LockOverlay` is
load-bearing for the entire app — the fewer layers here, the fewer things can break.
Compose is reserved for configuration screens.

## D9 — Accessibility does work on this firmware (spike, 2026-08-21)

Answers open question 1. On the Philips Google TV TA5 (TPV, `PH1M_WW_9972`, Android 14,
API 34, build `UKN2.241117.001`), a sideloaded accessibility service can be enabled, and
does start:

```
onServiceConnected(): version=0.1.0-m0 api=34 model=Philips Google TV TA5 manufacturer=TPV
```

The route is ADB only — `appops set app.tvsitter.tv ACCESS_RESTRICTED_SETTINGS allow`,
then writing `enabled_accessibility_services` and `accessibility_enabled`. Both app-ops
grants took effect, and `settings get` confirmed the service list afterwards.

Foreground detection works against real apps, including the ones that matter:
`com.netflix.ninja` while playing, and `com.google.android.apps.tv.launcherx` after HOME.
Decision D2 therefore stands.

Real package names, from `tools/device.sh inventory` (261 packages on the device):
`com.netflix.ninja`, `com.google.android.youtube.tv`, `com.disney.disneyplus`,
`pl.tvn.player.tv`, and for the M5 anti-tamper work `com.android.tv.settings` and
`com.android.vending`.

Two traps found along the way, both now handled in `tools/device.sh`:

- Getting ADB authorised needed **Revoke debugging authorisations** plus toggling network
  debugging on the TV. Until that was done the daemon answered on port 5555 and refused
  every key without ever showing the confirmation dialog — and Home Assistant's own,
  previously working ADB connection went unavailable at the same time, which suggests a
  rejected key can wedge the daemon for everyone.
- A manifest-declared receiver has not received implicit broadcasts since Android 8, so
  the debug hook has to be addressed as `-n app.tvsitter.tv/.DebugCommandReceiver`.
  Without it `am broadcast` prints `Broadcast completed: result=0` and runs nothing, which
  reads exactly like success.

## D10 — A full-screen overlay above playing video does work here (observed, 2026-08-21)

The reference app, TVCP, happens to be installed on the same TV, and inspecting the window
stack while Netflix was playing settled a question we were about to test the hard way:

```
Window #2 io.middlepoint.tvcp   ty=APPLICATION_OVERLAY fmt=TRANSLUCENT
                                Requested w=1920 h=1080  mBaseLayer=111000
                                mHasSurface=true isReadyForDisplay()=true
Window #5 com.netflix.ninja/MainActivity
```

So on this firmware a full-screen overlay can sit above a playing video app, permanently.
Two things follow.

**Our window type layers higher, not lower.** TVCP uses `TYPE_APPLICATION_OVERLAY` (2038,
base layer 111000), which requires `SYSTEM_ALERT_WINDOW` — an app-op that on Google TV
generally cannot be granted from the UI to a sideloaded app, which is precisely why
`TYPE_ACCESSIBILITY_OVERLAY` (2032) was chosen in D2. That type sits above 2038 in the
window layer order, so nothing about their approach can cover ours. Open question 1 below
is now very likely a yes; it still gets tested rather than assumed.

**TVCP does not use an accessibility service at all.** With our service enabled, the
enabled list contains only ours. Its app-ops are `SYSTEM_ALERT_WINDOW` (allow, held for
hours) and `GET_USAGE_STATS` (allow). So its foreground detection is `UsageStatsManager`,
which is polled, where ours is event-driven off `TYPE_WINDOW_STATE_CHANGED`. That is a real
difference in enforcement latency, in our favour, and it also explains how TVCP can promise
setup with "no developer tools or special settings".

**Consequence for testing:** two parental control apps enforcing on one TV will interfere.
TVCP keeps a full-screen translucent overlay present at all times, so it must be stopped
before the overlay and key-interception tests, or the results mean nothing.

## D11 — The overlay covers video and swallows HOME, once two bugs are out of the way (spike, 2026-08-21)

Answers open questions 1 and 2, both yes, on the Philips TA5.

**The overlay draws above full-screen video.** Our window comes up as
`ty=2032 fmt=TRANSLUCENT`, full-screen 1920×1080, and `dumpsys window windows` puts it
above `com.netflix.ninja` in the z-order while Netflix is playing.

**HOME is intercepted.** `dumpsys accessibility` reports `capabilities=9`, which is
`RETRIEVE_WINDOW_CONTENT + FILTER_KEY_EVENTS`, so writing the service into
`enabled_accessibility_services` over ADB does grant key filtering — it is not withheld for
being enabled without the UI consent dialog. With the lock showing, HOME, BACK, ENTER and
all four D-pad directions reach `onKeyEvent`, and during a run of HOME presses the overlay
window kept the same id, meaning no window transition happened and the launcher never came
forward.

**Methodology, and a trap:** `adb shell input keyevent KEYCODE_HOME` does **not** reach the
accessibility key filter. Injected events bypass it, so an ADB-driven key test reports a
false negative. Key behaviour has to be tested with the physical remote.

Two bugs found by testing on hardware, both fixed:

- The overlay's root `FrameLayout` was focusable and won focus, then swallowed every D-pad
  and ENTER event rather than letting them through to the button. The lock rendered fine
  while its only control was dead — which would have taken the M3 "ask for more time"
  feature with it. The container is now non-focusable with
  `FOCUS_AFTER_DESCENDANTS`, and the button takes focus explicitly; the log line now
  carries `button focused=true`, and a press produces the click within ~220 ms.
- The backdrop was `0xF2` alpha, that is 95% opaque, which looked better and let a bright
  picture show through on a large panel. Now fully opaque.

**What the overlay does not do: stop playback.** With the screen entirely covered, the
audio carried on. Tracked as #16 — covering pixels and ending a media session are separate
jobs, and only the first is done.

Incidental evidence for open question 3: the accessibility service came back on its own
after each `adb install -r`, with no manual step. A reboot is still a different scenario and
gets its own test.

## D12 — HDMI inputs are ordinary activities, and the overlay covers them (spike, 2026-08-21)

Answers the HDMI question, and the answer is the favourable one. Switching to the PS5 input
with the remote produces:

```
topResumedActivity = org.droidtv.playtv/.PlayTvActivity
SurfaceView[org.droidtv.playtv/org.droidtv.playtv.PlayTvActivity](BLAST)#761
```

Philips presents an external input as a normal Android activity drawing the feed into a
`SurfaceView`, not as a separate hardware plane composited above the UI. Our overlay
therefore covers it — confirmed by eye with the console on screen. The fallback of forcing
a source change or powering the set off through `philips_js` is not needed, and M4 keeps its
original shape.

`reassert()` earned its place here: navigating the source switcher while locked produced
three `overlay reasserted above a new window` lines, and the lock stayed on top throughout.

Two caveats.

**Detection is not instant.** Foreground events for the input do arrive
(`org.droidtv.tvsystemui`, `org.droidtv.channels/.sources.SourcesActivity`,
`org.droidtv.playtv/.PlayTvActivity`), but they arrive on window transitions, so a rule
keyed on "which app" needs to treat `org.droidtv.playtv` as a distinct, blockable target
rather than expecting a per-input package.

**Audio from an external source is expected to be out of reach of #16 — not yet measured.**
The audio-focus mechanism planned there acts on Android media sessions, and a console's
sound is not one, so on reasoning alone "stop playback" has to mean something else for
HDMI: changing source, muting, or powering the panel off. This was **not** confirmed on
hardware — nothing was playing on the console at the time — so it stays a prediction to
test rather than a finding. If it holds, a child keeps playing by ear behind a covered
screen, which needs designing separately.

## D13 — The service is back before boot completes (spike, 2026-08-21)

Answers the last open question, and answers it well. After `adb reboot`:

```
BOOT_COMPLETED, service connected=true            (pid 3165)
/proc/uptime 176s  ·  pid 3165 ETIME 02:29 (149s) ·  dumpsys: capabilities=9
```

The service was already connected when `BOOT_COMPLETED` arrived, and uptime minus process age
puts its start about **27 seconds** after the kernel came up — one reboot, one measurement, so
treat it as an order of magnitude rather than a constant. Either way it precedes
`BOOT_COMPLETED` and therefore precedes the point where anyone can reach the launcher.
Rebooting is not a way around the lock, and D2's premise — that an accessibility service is
the right home for the counter because the system revives it — holds.

(An earlier draft of this entry said eight seconds. That came from the `uptime` command, which
rounds to whole minutes; `/proc/uptime` is the one to read.)

Two notes for whoever runs this next.

`adb reboot` brings the panel back **on**, at the home screen, not into standby. A reboot is
therefore not usable as an enforcement action: it would turn the TV on rather than off.

The first version of `tools/device.sh reboot-test` hung forever waiting for the device,
because it matched on the output of `adb connect`, which answers `already connected` from a
stale entry even while the device is down. Device state has to come from `adb devices`. For
the same family of reason, `doctor` no longer decides whether the service is running by
grepping the log — the buffer rotates during boot — and asks `dumpsys accessibility` instead.

## No open hardware questions from the M0 spike

Everything the spike set out to answer is answered, in D9 through D13. What it turned up
along the way is tracked as #16: the lock covers the screen but does not end the media
session, and for an external HDMI source it likely cannot.
