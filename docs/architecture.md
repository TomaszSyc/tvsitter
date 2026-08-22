# Architecture decisions

A record of what has been decided and why. New decisions are appended; existing ones are
not edited — if one stops applying it gets a note pointing at the decision that
superseded it.

## The hardware this is built on

- TV: Philips Google TV TA5 (TPV, `PH1M_WW_9972`), Android 14 (API 34).
- Home Assistant 2026.8.2 on HAOS, Mosquitto broker add-on, HACS.
- Notifications: `notify.mobile_app_pixel_9_pro` and `notify.mobile_app_pixel_watch_4`.

## D1 — Enforcement on the TV, not over ADB

The obvious approach is to drive the TV from Home Assistant through the `androidtv`
integration (ADB): `am force-stop`, `pm disable-user`, `input keyevent SLEEP`. Rejected,
because ADB is not stable enough on this hardware. The `media_player.philips_tb` entity
logged 577 `off`↔`idle` state changes in 48 hours, 10–60 seconds apart, while the
independent `philips_js` integration reported clean single transitions over the same
period. A lock that only fires most of the time is not much of a lock. Turning network
debugging off in Settings also takes a child about fifteen seconds.

ADB remains an installation tool only (see `setup.md`).

## D2 — AccessibilityService as the foundation

An accessibility service provides three things at once, without root:

1. the `TYPE_WINDOW_STATE_CHANGED` event carrying the foreground package name, which is
   the only root-free real-time source of "what is running right now",
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
  `event` entity for triggering automations, none of which Discovery alone gives,
- one source of entities is easier to reason about than two mechanisms competing for the
  same names.

Consequence: the app publishes plain state JSON, no discovery payloads. Anyone who would
rather not install the integration can hand-write MQTT entities from the same topics.

## D6 — One repository for both halves

HACS only requires `custom_components/<domain>/` and `hacs.json` in the repository root;
it does not forbid additional content, so the Gradle project can sit alongside.

In favour of the monorepo: the MQTT contract changes in a single commit across both sides,
there is one issue tracker (a user cannot tell which half is at fault anyway), and the two
halves cannot drift apart in version.

The accepted cost: HACS derives the integration version from the repository's latest
release, so a release that only touches the TV app also bumps the integration version, and
users see an update in which nothing changed for them. Adopted resolution: a single SemVer
version for the whole product, since the two halves have to match each other anyway. If
this becomes annoying, splitting the integration into its own repository while keeping
history is a `git subtree split`.

## D7 — Toolchain versions

- AGP 9.3.1 ships built-in Kotlin support and explicitly rejects the
  `org.jetbrains.kotlin.android` plugin, so `:app` does not apply it.
- compileSdk / targetSdk 37, forced by `androidx.core:core-ktx` 1.19.0, which refuses to be
  compiled against anything lower.
- minSdk 26 (Android 8), so that `java.time` works without desugaring. Older Android TV
  releases are not a realistic target.
- Gradle 9.7.1 (wrapper committed), JDK 21.

## D8 — The lock screen uses plain views, not Compose

An accessibility window has none of the lifecycle owners Compose expects. `LockOverlay` is
load-bearing for the entire app, and the fewer layers here, the fewer things can break.
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

- Getting ADB authorised needed Revoke debugging authorisations plus toggling network
  debugging on the TV. Until that was done the daemon answered on port 5555 and refused
  every key without ever showing the confirmation dialog. Home Assistant's own, previously
  working ADB connection went unavailable at the same time, which suggests a rejected key
  can wedge the daemon for everyone.
- A manifest-declared receiver has not received implicit broadcasts since Android 8, so the
  debug hook has to be addressed as `-n app.tvsitter.tv/.DebugCommandReceiver`. Without it
  `am broadcast` prints `Broadcast completed: result=0` and runs nothing, which looks like
  success.

## D10 — A full-screen overlay above playing video does work here (observed, 2026-08-21)

The reference app, TVCP, happens to be installed on the same TV. Inspecting the window
stack while Netflix was playing settled a question we were about to test the hard way:

```
Window #2 io.middlepoint.tvcp   ty=APPLICATION_OVERLAY fmt=TRANSLUCENT
                                Requested w=1920 h=1080  mBaseLayer=111000
                                mHasSurface=true isReadyForDisplay()=true
Window #5 com.netflix.ninja/MainActivity
```

So on this firmware a full-screen overlay can sit above a playing video app, permanently.
Two things follow.

Our window type layers higher. TVCP uses `TYPE_APPLICATION_OVERLAY` (2038, base layer
111000), which requires `SYSTEM_ALERT_WINDOW`, an app-op that on Google TV generally cannot
be granted from the UI to a sideloaded app. That is why `TYPE_ACCESSIBILITY_OVERLAY` (2032)
was chosen in D2. That type sits above 2038 in the window layer order, so nothing about
their approach can cover ours. Open question 1 below is now very likely a yes; it still
gets tested rather than assumed.

TVCP uses no accessibility service. With our service enabled, the enabled list contains
only ours. Its app-ops are `SYSTEM_ALERT_WINDOW` (allow, held for hours) and
`GET_USAGE_STATS` (allow). Its foreground detection is therefore `UsageStatsManager`, which
is polled, where ours is event-driven off `TYPE_WINDOW_STATE_CHANGED`. That is a real
difference in enforcement latency in our favour, and it explains how TVCP can promise setup
with "no developer tools or special settings".

Consequence for testing: two parental control apps enforcing on one TV will interfere. TVCP
keeps a full-screen translucent overlay present at all times, so it has to be stopped before
the overlay and key-interception tests, or the results mean nothing.

## D11 — The overlay covers video and swallows HOME, once two bugs are out of the way (spike, 2026-08-21)

Answers open questions 1 and 2, both yes, on the Philips TA5.

The overlay draws above full-screen video. Our window comes up as `ty=2032 fmt=TRANSLUCENT`,
full-screen 1920×1080, and `dumpsys window windows` puts it above `com.netflix.ninja` in the
z-order while Netflix is playing.

HOME is intercepted. `dumpsys accessibility` reports `capabilities=9`, which is
`RETRIEVE_WINDOW_CONTENT + FILTER_KEY_EVENTS`, so writing the service into
`enabled_accessibility_services` over ADB does grant key filtering; it is not withheld for
being enabled without the UI consent dialog. With the lock showing, HOME, BACK, ENTER and
all four D-pad directions reach `onKeyEvent`, and during a run of HOME presses the overlay
window kept the same id, meaning no window transition happened and the launcher never came
forward.

Methodology, and a trap: `adb shell input keyevent KEYCODE_HOME` does not reach the
accessibility key filter. Injected events bypass it, so an ADB-driven key test reports a
false negative. Key behaviour has to be tested with the physical remote.

Two bugs found by testing on hardware, both fixed:

- The overlay's root `FrameLayout` was focusable and won focus, then swallowed every D-pad
  and ENTER event rather than letting them through to the button. The lock rendered fine
  while its only control was dead, which would have taken the M3 "ask for more time" feature
  with it. The container is now non-focusable with `FOCUS_AFTER_DESCENDANTS`, and the button
  takes focus explicitly; the log line now carries `button focused=true`, and a press
  produces the click within ~220 ms.
- The backdrop was `0xF2` alpha, that is 95% opaque, which looked better and let a bright
  picture show through on a large panel. Now fully opaque.

What the overlay does not do is stop playback. With the screen entirely covered, the audio
carried on. Tracked as #16: covering pixels and ending a media session are separate jobs,
and only the first is done.

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
therefore covers it, confirmed by eye with the console on screen. The fallback of forcing a
source change or powering the set off through `philips_js` is not needed, and M4 keeps its
original shape.

`reassert()` was useful here: navigating the source switcher while locked produced three
`overlay reasserted above a new window` lines, and the lock stayed on top throughout.

Two caveats.

Detection is not instant. Foreground events for the input do arrive
(`org.droidtv.tvsystemui`, `org.droidtv.channels/.sources.SourcesActivity`,
`org.droidtv.playtv/.PlayTvActivity`), but they arrive on window transitions, so a rule keyed
on "which app" needs to treat `org.droidtv.playtv` as a distinct, blockable target rather
than expecting a per-input package.

Audio from an external source is expected to be out of reach of #16, and this has not been
measured. The audio-focus mechanism planned there acts on Android media sessions, and a
console's sound is not one, so on reasoning alone "stop playback" has to mean something else
for HDMI: changing source, muting, or powering the panel off. This was not confirmed on
hardware, since nothing was playing on the console at the time, so it stays a prediction to
test rather than a finding. If it holds, a child keeps playing by ear behind a covered
screen, which needs designing separately.

## D13 — The service is back before boot completes (spike, 2026-08-21)

Answers the last open question. After `adb reboot`:

```
BOOT_COMPLETED, service connected=true            (pid 3165)
/proc/uptime 176s  ·  pid 3165 ETIME 02:29 (149s) ·  dumpsys: capabilities=9
```

The service was already connected when `BOOT_COMPLETED` arrived, and uptime minus process
age puts its start about 27 seconds after the kernel came up. One reboot, one measurement,
so treat it as an order of magnitude rather than a constant. Either way it precedes
`BOOT_COMPLETED` and therefore precedes the point where anyone can reach the launcher.
Rebooting is not a way around the lock, and D2's premise — that an accessibility service is
the right home for the counter because the system revives it — holds.

(An earlier draft of this entry said eight seconds. That came from the `uptime` command,
which rounds to whole minutes; `/proc/uptime` is the one to read.)

Two notes for whoever runs this next.

`adb reboot` brings the panel back on, at the home screen, not into standby. A reboot is
therefore not usable as an enforcement action: it would turn the TV on rather than off.

The first version of `tools/device.sh reboot-test` hung forever waiting for the device,
because it matched on the output of `adb connect`, which answers `already connected` from a
stale entry even while the device is down. Device state has to come from `adb devices`. For
a related reason, `doctor` no longer decides whether the service is running by grepping the
log, since the buffer rotates during boot, and asks `dumpsys accessibility` instead.

## D14 — Pairing over zeroconf and a PIN, so nobody retypes broker credentials

MQTT stays the data plane (D4), but nothing about it should be typed twice.

Setup becomes: install the app on the TV, Home Assistant reports "TV Sitter discovered",
enter the PIN shown on the TV, done. The integration reads the broker address and
credentials from Home Assistant's own MQTT config entry, which it can do in-process, and
pushes them to the TV over a one-shot local endpoint that only answers when presented with
the PIN on screen. The app advertises itself over mDNS as `_tvsitter._tcp`.

Why a PIN at all: without it, anything on the local network could hand the TV a broker to
talk to, which is the same as handing it a new set of rules. The PIN is on the TV screen, so
possessing it means standing in the room, which is the same assumption the rest of the
product makes.

Credentials are shared by default and dedicated by choice. The config flow offers what Home
Assistant already has, so the common path involves no typing, and carries a section for
supplying a separate account instead. That keeps the recommendation in `SECURITY.md` — give
TV Sitter its own account with an ACL scoped to its topic prefix, because anyone able to
publish to `<prefix>/cmd` can unlock the TV — available to whoever wants it, without making
it the price of admission.

Rejected: having the integration create a Home Assistant user by itself. The API allows it.
An integration that mints accounts is a level of reach that would rightly alarm both
reviewers and users.

The manual route stays for development: `tools/device.sh configure` writes the same settings
over ADB, which is how this was brought up in the first place.

## D15 — An enabled accessibility service unmasks password fields (measured, 2026-08-21)

A cost of D2 that was not anticipated, found by a user noticing it rather than by testing.

With the service enabled, the Google account PIN entry on the TV stops masking what is
typed. Confirmed by elimination: it persists after dropping `canRetrieveWindowContent` and
after clearing the key-filter flag at runtime, leaving `capabilities=8`; and masking returns
the moment the service is disabled. So the trigger is that *an accessibility service is
enabled at all* — apps check `AccessibilityManager.isEnabled()` and unmask so that screen
readers work — not anything about how narrow our capabilities are.

This matters more here than it would elsewhere. A parent typing their account PIN in front
of the child whose screen time they are limiting is a bad failure for a product whose value
rests on being trustworthy.

TVCP does not have this problem, because per D10 it uses no accessibility service at all:
`SYSTEM_ALERT_WINDOW` plus `UsageStatsManager`. That is a genuine advantage of their
architecture over ours, and it belongs in the record.

### What was done anyway

Both changes stand on their own merits even though neither fixed the masking:

- `canRetrieveWindowContent` is now false. A grep across the app showed we only ever read
  `packageName` and `className` off an event and never touch window content, so claiming the
  right to read the screen, including what somebody types, was privilege we did not need.
  On-device capabilities went from 9 to 8.
- Key filtering is requested in the service config, so the user consents once and HOME stays
  interceptable, but the flag is cleared at runtime and set only while the lock is showing. A
  service receiving every keystroke is a keylogger by capability; it should be live for the
  seconds it is needed.

### The open question this raises

Whether to keep accessibility as the foundation at all. An untested alternative exists:
`SYSTEM_ALERT_WINDOW` for the overlay, granted over ADB, which setup already requires, plus
polled `UsageStatsManager` for foreground detection.

Against it: detection becomes polled rather than event-driven, and HOME can no longer be
swallowed, nor `GLOBAL_ACTION_HOME` used to leave an HDMI input, which was the plan for the
HDMI half of #16.

For it: no unmasked passwords, less privilege overall, and, from D10, a persistent
full-screen overlay that never has to re-assert itself, which is arguably sturdier than our
remove-and-re-add dance.

### Measured on hardware, same evening

The spike ran. `appops set SYSTEM_ALERT_WINDOW allow` does register once the permission is
declared in the manifest. An app-op for an unrequested permission has no effect, which is
why the first attempt looked like a refusal. With the accessibility service off (`Bound
services:{}`, `Enabled services:{}`) and YouTube in the foreground, a
`TYPE_APPLICATION_OVERLAY` window from our own app covered the screen: our window at `#3`,
YouTube at `#5`, confirmed by eye. And with no accessibility service enabled, the Google
account PIN entry masks again.

So option 2 works. What it costs, all measured rather than assumed:

| | Accessibility (today) | `SYSTEM_ALERT_WINDOW` |
|---|---|---|
| Covers full-screen video | yes | yes |
| System-wide password masking | broken | intact |
| HOME interceptable | yes | no |
| Window layer | `#1`, above the TV's system UI | `#3`, below the TV's system bars |
| Return after reboot | system revives it, ~27 s (D13) | must restart itself on `BOOT_COMPLETED` |
| Foreground detection | event-driven, immediate | polled, one to two seconds behind |
| Privilege asked for | read the screen *(since removed)* and every keystroke | draw on top |

That last row carries more weight than the masking. "Draw on top" is a much narrower ask
than "see everything on screen and every key pressed", and in an app whose value rests on a
parent trusting it, the difference is not a technical detail.

Two consequences to plan for rather than discover: without an accessibility service the
process needs a foreground service, which the system kills more readily than it kills an
accessibility service; and our window would sit below `org.droidtv.tvsystemui`, so the TV's
own volume and info bars would draw over the lock. Neither is an escape route, both are
real.

## D16 — SYSTEM_ALERT_WINDOW replaces the accessibility service. Supersedes D2

Decided after the measurements in D15. The lock is drawn with `TYPE_APPLICATION_OVERLAY`,
the foreground app comes from polled `UsageStatsManager`, and no accessibility service is
enabled at all.

Two reasons, in order of weight.

The privilege asked for shrinks from "read everything on screen and every keystroke" to
"draw on top". In an app whose value rests on a parent trusting it with the family
television, that difference decides whether the ask is a reasonable one.

And it fixes D15: with no accessibility service enabled, password fields mask again. A
parent typing their account PIN in front of the child whose screen time they are limiting
was never acceptable.

### What this supersedes or changes

- D2 is superseded. Its reasoning was sound on the evidence available; D15 was the evidence
  it lacked.
- D11's HOME interception no longer applies. `onKeyEvent` needs an accessibility service.
  This costs less than it sounds: a `SYSTEM_ALERT_WINDOW` at layer 111000 sits above every
  app window including the launcher, so pressing HOME changes what is *behind* the lock and
  nothing more. TVCP keeps a permanently present full-screen window for the same reason
  (D10), and it is sturdier than the remove-and-re-add `reassert()` it replaces.
- D13 must be re-measured. The system revived an accessibility service about 27 seconds
  after boot, for nothing. A foreground service has to restart itself from `BOOT_COMPLETED`,
  and the system kills those more readily. The gap after a reboot is an open question again.
- The HDMI half of #16 changes shape. `performGlobalAction(GLOBAL_ACTION_HOME)` is gone as
  the way to leave an input and end its audio. The replacement is to launch our own
  full-screen activity, which displaces the input rather than merely covering it, and
  displacing it is what stops the sound.

### What it costs, accepted knowingly

Detection becomes polled, so a newly opened app is visible for a second or two before the
lock appears. For counting screen time that is noise; for blocking it is a real if small
regression, and the reason TVCP's enforcement feels less immediate than ours did.

Our window sits below `org.droidtv.tvsystemui`, so the TV's own volume and info bars draw
over the lock. Not an escape route, but visible.

The process needs a foreground service, and therefore a notification. On a television that
is close to invisible, but it is one more thing that can be killed.

## D17 — The reboot gap grew from 27 to 67 seconds (measured, 2026-08-21)

Re-measures what D13 established, because D16 invalidated it. The number is the cost of no
longer having the system revive us for nothing.

```
BOOT_COMPLETED, starting the enforcer     22:26:55.565
onCreate()                                22:26:55.938   (+373 ms)
foreground=com.google.android.apps.tv.launcherx  22:26:56.358
mqtt: connected                           22:26:58.577
/proc/uptime 105.85s · process ETIME 39s  → started at uptime ~67s
```

Our own code is not the delay: enforcement resumes 373 milliseconds after the broadcast
arrives. The delay is that `BOOT_COMPLETED` is delivered about 67 seconds into boot, where
an accessibility service was revived at about 27 (D13) and, crucially, *before*
`BOOT_COMPLETED` rather than because of it.

The gap is large enough to matter. By the time we started, our own first reading said the
launcher had already been in the foreground, so the television was usable, and possibly
being used, while nothing counted and nothing could block. Roughly forty seconds of that per
reboot, and a child who works out that turning the TV off and on again buys a head start has
found a genuine hole.

Worth trying, not yet tried: `ACTION_LOCKED_BOOT_COMPLETED` with `directBootAware`, which
fires earlier than `BOOT_COMPLETED`. A television has no credential lock to wait on, so the
early start should be usable, with the caveat that credential-encrypted storage, and
therefore our settings, is not readable until the user is unlocked. Starting the overlay and
the counter early while deferring anything that needs settings is the shape of the fix.

## D18 — What Home Assistant knows about the broker is not what the TV needs (2026-08-22)

D14 says pairing should hand the TV the broker settings Home Assistant already has, so
nobody retypes them. Reading the MQTT config entry on a normal Home Assistant OS install
gives:

```
broker=core-mosquitto  port=1883  username_set=true  password_set=true
```

`core-mosquitto` is a container hostname on Supervisor's own network. It resolves inside
Home Assistant and nowhere else, so a TV told to connect there never will. The pairing
itself would succeed, since the TV accepts the settings and closes its endpoint, and the
failure would surface afterwards as a TV that is simply never online, with the one chance to
configure it already spent.

So credentials and port are taken from the MQTT entry as they are, and the address is not.
When the stored address only means something locally, the flow substitutes the local address
the routing table would use to reach the TV:

```python
sock = socket.socket(AF_INET, SOCK_DGRAM)
sock.connect((tv_host, port))  # sends nothing; asks which interface would be used
sock.getsockname()[0]
```

That is a better default than any configured URL, because it comes from the same network
path the TV was just discovered over. `internal_url` may be unset, may be a name only some
clients resolve, or may point through a proxy.

An address the user configured themselves is left alone: they may well have a broker
elsewhere on the network, and second-guessing it would do more harm than good. The test for
"local only" is loopback plus the Supervisor naming conventions (`core-`, `addon_`,
`hassio`).

Credentials are pre-filled but never rendered: the broker section starts with empty username
and password fields, and empty means "reuse the Home Assistant account". A typed username
takes the password typed beside it, because mixing a new username with a stored password
gives a TV that cannot authenticate.

Verified on the live instance by advertising a fake TV from a laptop with `dns-sd`, which
needs no hardware:

```
zeroconf.discovery  service_update: type=_tvsitter._tcp.local. state_change=Added
zeroconf.discovery  Discovered new device ... properties={'id': 'testdev01', 'paired': 'false'}
tvsitter.broker     Broker address core-mosquitto is local to Home Assistant; using <ha-ip>
```

## D19 — Everything about an MQTT connection has to be stated per connection (2026-08-22)

Found by switching the TV on after a night in standby. The process had been up for 12.6 hours,
held both app-ops, and had no socket to port 1883. Home Assistant had shown the retained Last
Will since the evening before. Four separate mistakes, all in the same few lines, and none of
them visible without a disconnect log.

`automaticReconnect()` does not reuse the CONNECT built by `connectWith()`. It builds a default
one, so every retry arrived with no username:

```
mqtt: disconnected by SERVER, attempt 1, reconnect=true
Mqtt5ConnAckException: CONNECT failed as CONNACK contained an Error Code: NOT_AUTHORIZED
```

```
Client tvsitter-tvsitter-salon disconnected: not authorised.
error: received null username or password for unpwd check
```

This is hivemq/hivemq-mqtt-client#574, open upstream. Moving the credentials to the client
builder is the workaround people suggest, and it is not enough: `cleanStart` and `keepAlive`
cannot be set there at all, so the keep-alive would revert to the default without a word. The
CONNECT is therefore built once as an `Mqtt5Connect` and handed both to the first attempt and to
`MqttClientReconnector.connect()` in the disconnected listener. Every attempt is identical by
construction.

Announcing availability and subscribing belong to a connection, not to a client. They were in
the connect callback, which fires once, so a reconnected TV was online but reported offline and
was subscribed to nothing. `addConnectedListener` runs on every connection, which is where they
belong. Publishing state belongs there too: `heartbeat()` delays before its first publish, so
without it Home Assistant showed the previous snapshot for a minute after every start.

If you subscribe from the connected listener, turn HiveMQ's own resubscribe off.
`resubscribeIfSessionExpired` defaults to true, so the filter was subscribed twice and every
command arrived twice. Harmless for `lock`; for `grant` it would have handed out double the
minutes.

Commands arrive on an RxJava thread owned by the client, and acting on one calls
`WindowManager.addView`, which throws off the main thread:

```
RuntimeException: Can't create handler inside thread Thread[RxComputationThreadPool-1,5,main]
  at WindowManagerImpl.addView -> LockOverlay.show -> EnforcerService.lock -> handleCommand
```

So locking the TV from Home Assistant had never worked. Every lock test until now went through
`tools/device.sh lock`, which arrives via `onStartCommand` on the main thread. The two paths read
the same in the code and are not the same. Commands now go through the service's
`Dispatchers.Main.immediate` scope before anything acts on them.

The general lesson, and the reason this is a decision rather than a bug report: a client object
is not a connection. Anything that is really a property of the connection — credentials, will,
keep-alive, subscriptions, the availability announcement — has to be re-established every time
one is made, and the only way to know it happened is to log the disconnects. There was no such
log, which is why twelve hours of silence left nothing to read.

## D20 — The screen saver does not count as screen time (2026-08-22)

A dream runs with the panel lit and the room empty, and Android does not send
`ACTION_SCREEN_OFF` for it. So `ScreenState` reports the screen as on,
`ForegroundAppMonitor` reports the dream as the foreground app, and the counter would spend a
child's evening while nobody is watching. Decided with the household: it does not count.

The evidence that this is not theoretical is the retained payload from the first night, which
carried `app_id: com.google.android.apps.tv.dreamx` — the Google TV screen saver — as the last
thing in the foreground.

Detected by asking the package manager which packages provide a `DreamService`, not by naming
that package. It is what this television happens to use; another set uses its own, and a
hard-coded name would be wrong there with nothing to say so. The resolved set is logged at
startup, because an empty set is silent and means every screen saver counts as viewing.

That query needs package visibility on Android 11 and later, declared as a `<queries>` intent
for `android.service.dreams.DreamService`. Deliberately not `QUERY_ALL_PACKAGES`: that is a
restricted permission Play reviews (see the Play notes in #14), and this needs one narrow answer
rather than the whole package list.

### What counts as an interval, rather than an instant

Worth recording because it is easy to get backwards. `ScreenState` and `ForegroundAppMonitor`
both announce a change *after* applying it, so at the moment a callback runs the new value is
already current. An interval is closed with what was true *during* it: an interval that ended
because the screen went off was watched, and one that ended because the app changed belongs to
the app that was showing. Reading "now" at sample time would charge every interval to the state
that replaced it — quietly moving time from Netflix to the launcher, and losing the last stretch
before every screen-off.

For the same reason the counter samples at every transition and not only on its timer: an
interval can only be attributed correctly if it is cut where the state changed.

## No open hardware questions from the M0 spike

Everything the spike set out to answer is answered, in D9 through D13. What it turned up
along the way is tracked as #16: the lock covers the screen but does not end the media
session, and for an external HDMI source it likely cannot.
