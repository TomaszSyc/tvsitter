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

## Open questions — still to be settled on real hardware

1. Does `TYPE_ACCESSIBILITY_OVERLAY` draw on top of **full-screen** video? If not, the
   fallback is a full-screen `Activity` of our own plus `GLOBAL_ACTION_HOME`.
3. Does `onKeyEvent` receive `KEYCODE_HOME`, and can it swallow it? That is the one key an
   ordinary window cannot stop.
4. Does the service really come back after the TV reboots, and how quickly?
5. Are HDMI inputs (a game console) visible as a foreground app? If they are a TV input
   framework surface out of reach of accessibility, blocking HDMI will have to go through
   `philips_js` / `androidtv_remote` rather than through the overlay.

Findings land in this file as decisions D9 onwards.
