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

## D21 — Audio focus stops playback; `stop_app` cannot be built (measured, 2026-08-22)

The lock covered the screen and the sound carried on (#16), which leaves anything audio-led
unrestricted. Taking `AUDIOFOCUS_GAIN` when the lock goes up fixes it, measured with YouTube
playing:

```
before   media_session  youtube.tv  state=PLAYING(3)
         audio          piid:559  state:started  usage=USAGE_MEDIA content=CONTENT_TYPE_MOVIE
locked   media_session  state=PAUSED(2)
         audio          piid:559  state:paused
```

Confirmed by ear as well as by dumpsys.

`AUDIOFOCUS_GAIN` rather than a transient form, on purpose. Transient focus asks other apps to
pause and resume afterwards; for a lock that is the wrong shape, because a film starting up on
its own the moment the lock lifts is not what anybody asked for. Measured: playback stayed
paused after unlocking. The request presents as `USAGE_MEDIA` / `CONTENT_TYPE_MOVIE`, which is
the focus other players yield to — a sonification usage makes them duck instead, and a film at
low volume behind a lock screen is still a film.

### The contract has an operation that cannot be implemented

`stop_app` is in `docs/mqtt-contract.md` and was the planned escalation for an app that ignores
focus loss. An ordinary Android application cannot stop another application.
`ActivityManager.killBackgroundProcesses` needs a permission and only touches background
processes, never the foreground one — which is exactly the case that matters. There is no
in-app equivalent of `am force-stop` without Device Owner.

So the operation stays in the contract as a name with nothing behind it for now. The escalation
that is actually available is displacing the player: launching a full-screen Activity of our own
moves the media app to the background, and Android pauses it as part of the lifecycle. That is
the same mechanism D16 identified for leaving an HDMI input, and it changes shape rather than
degree — an Activity takes over the task stack, where the overlay merely sits above it. Tracked
as #40.

### Still out of reach

An external HDMI source is not an Android media session (D12), so none of this touches it.
Muting, changing source, or powering the panel off through `philips_js` are the only levers, and
they belong to Home Assistant rather than to the app.

## D22 — The reboot gap is mostly not ours to close (measured, 2026-08-22)

D17 recorded a 67-second gap after a reboot and suggested `ACTION_LOCKED_BOOT_COMPLETED` as the
fix. Before building for it, the question was how far ahead of `BOOT_COMPLETED` it actually
lands on this hardware — a television has no credential lock to wait on, so the two could be
moments apart. Measured with a `directBootAware` receiver that only logs:

```
LOCKED_BOOT_COMPLETED  uptime 40s
BOOT_COMPLETED         uptime 55s      (+15s)
onCreate()             +4.7s after BOOT_COMPLETED
```

So about 15 seconds is recoverable out of roughly 60. The first 40 seconds are unreachable:
nothing of ours runs before the earliest broadcast the system will deliver to us.

Also worth correcting from D17: `onCreate()` arrived 4.7 seconds after the broadcast, not the
373 milliseconds measured then. The service does more now — a package-manager query for screen
savers, rules and counter reads from storage — and it starts under boot-time load. Our own code
is no longer a rounding error in this figure, though it is still the smaller part.

### What starting early would cost

Code running before the user is unlocked cannot read credential-encrypted storage, which is
where everything this app persists lives: broker settings, rules, the counter. So an early start
buys nothing unless something moves to device-encrypted storage.

The minimum that would help is one boolean: whether the lock was up when the TV went down. If
the budget was spent then the lock was up, so that flag covers the case that matters — a child
who reboots to get a head start. Everything else can wait for the unlock and reconcile.

That also means `EnforcerService` would have to become `directBootAware` and defer every
storage-dependent step until `ACTION_USER_UNLOCKED`, rather than doing it in `onCreate` as it
does now.

### Decision, and what it turned out to be

Built. Enforcement now resumes from `LOCKED_BOOT_COMPLETED` when there was a lock to put back,
measured on the following reboot:

```
service start   uptime ~36s   (device up 59s, process alive 23s)
BOOT_COMPLETED  uptime 51s
```

against a baseline where nothing ran until `BOOT_COMPLETED` plus a few seconds of service
startup — so roughly fifteen seconds earlier, on a gap of about sixty. A 25% improvement, not
the fix D17 implied, and recording that ratio matters as much as the change: the remaining forty
seconds are a property of the platform rather than a bug to be fixed.

The early start is conditional. On an ordinary boot there is nothing to put back, and the
counter and rules are not readable yet, so starting early would mean fifteen seconds of a
service that can enforce nothing. It starts early only when the device-encrypted memory says a
lock was up.

### What the measurement corrected about the plan

On this television `isUserUnlocked` is already true when `LOCKED_BOOT_COMPLETED` arrives, so
credential-encrypted storage is readable from the start and the deferral never triggers. The
evidence for that is the MQTT timing: the connection landed six seconds after `onCreate`, waiting
for Wi-Fi, not for an unlock. `UnlockGate` therefore earns its place for correctness on devices
that do have a credential lock, not for this one.

Which also narrows what the device-encrypted memory is really for. A budget lock can be worked
out again from the counter and the rules, so it survives a restart without help — that was
already observed when reinstalling put the lock straight back. A lock a parent put up is a
decision rather than a calculation, and had no record of itself at all: a reboot forgot it. That
is the case this closes, and it is why the memory stores the cause rather than a flag.

The first attempt got this wrong in a way worth writing down. The restore was gated behind
"storage is locked", which on this hardware is never true, so it never ran — and a reboot still
forgot the lock. Whether a lock should come back has nothing to do with whether storage is
readable: it was up when the process last died, so it goes back up. Verified afterwards with a
manual lock, a reboot, and `STATUS: locked=true`.

Incidentally caught by the same measurement: `tools/device.sh reboot-test` decided the enforcer
was running by grepping for the process. A `directBootAware` receiver starts the process without
starting the service, so the test reported success about fifteen seconds early. It now asks
`dumpsys activity services`.

## D23 — The television can change the PIN, but never create one (2026-08-22)

The PIN is what lifts a lock at the set itself, so it has to be changeable without Home
Assistant: a dead SD card should not mean that a PIN a child watched being typed stays in force
indefinitely. Changing it on the television requires the current PIN, and that requirement is
what keeps the change screen from being the way past the lock — without it, a child sets a PIN
of their own and unlocks with it.

There is deliberately no way to set a *first* PIN at the television. Nothing there tells a
parent apart from a child except knowing the PIN, so a screen that could create one would hand
the lock to whoever reached it first, and the parent would find out on the evening Home
Assistant was unreachable. The first PIN comes from Home Assistant; either side can change it
afterwards.

### Where the work happens

Home Assistant hashes the PIN and sends the digest, so the PIN itself never reaches the broker:
PBKDF2-HMAC-SHA256, 120 000 iterations, a 16-byte salt per PIN, parameters stored alongside the
digest so the count can be raised later without invalidating a PIN in use. Two languages derive
those bytes — `SecretKeyFactory` on the TV, `hashlib` in the integration — and nothing but a
pinned test vector on both sides checks that they agree. A drift there would look like a parent
typing the right PIN into a television that refuses it.

What hashing buys is narrow and worth stating plainly. It stops the PIN being read out of a file
by somebody poking around with ADB, and it means a stolen file does not hand over a PIN the
parent may have used elsewhere. It does not make a four-digit secret safe against an offline
attack. The control that actually protects the PIN is the lockout: five wrong guesses shut the
keypad for five minutes, which turns ten thousand candidates into nineteen years.

Both places a PIN can be typed — the lock screen and the change screen — spend the same five
attempts. Two counters would be two doors with one lock between them, and a child would use the
other one.

### Where it is stored

The hash and the counter live in device-encrypted storage, alongside the lock memory of D22 and
away from everything else. A lock can be back on screen before the user has unlocked the device,
and a keypad that could not read the hash then would have to tell a parent standing in front of
a locked television to unlock the television first. For a hash this costs nothing: neither
storage area is readable by another app, and both are readable with root.

Persisting the counter is not tidiness. Held in memory it resets when the process dies, and
force-stopping an app is something a child can do from Settings.

### What Home Assistant is told

`pin_set`, `pin_changed_at` and `pin_changed_by`, and not the hash. Publishing the hash would
put something worth attacking offline onto the broker and into the recorder, and nothing in Home
Assistant has any use for it. Because `state` is retained and republished on every connect, a
change made at the television while Home Assistant was down arrives as soon as the broker is
back: late rather than lost.

`pin_changed_by` is there so the timestamp is actionable. A change made in Home Assistant was
made by somebody holding the parent's phone; a change made on the television was made by
whoever was in the room. If it says the television and nobody in the house did it, that is the
only warning there will be.

### The two ways out

A forgotten PIN is answered from Home Assistant, which can set or remove it without knowing the
old one — reaching that command means publishing to the broker the television is paired with. A
household with no PIN and no Home Assistant has no way to lift a lock at all, and the honest
answer there is uninstalling the app with the remote. Which is also why `binary_sensor` reports
whether a PIN exists: "there isn't one" is a bad thing to discover at that point rather than
before it.

### What the television changed about all of this (measured, 2026-08-22)

Three things, and the first two were wrong in the design rather than in the code.

**The keypad leaked the PIN it was built to hide.** A grid of nine buttons masks the entry and
then broadcasts every digit through the focus highlight, which follows the remote across a
fifty-inch screen. Rebuilt in the shape the platform uses for its own PIN — up and down move
between rows of three, and left, centre and right take one of the three — because there the
screen shows which row is in play and never which of the three was taken. That leaves somebody
watching a four-digit entry with eighty-one candidates instead of the code.

**A PIN is now exactly four digits**, where it was four to eight. Entry can only submit itself
when the length is known, and on the screen that *sets* a PIN it never is — so a range means a
confirm button on every keypad for ever, and the platform's own screens have none. The cost is
real and was paid for rather than ignored: ten thousand candidates at five tries per five
minutes is about a week of solid guessing, so the lockout now grows — five minutes, then
fifteen, then thirty — which puts it past a month.

**The derivation is far too slow for the main thread.** Measured on this processor:

```
pin: wrong, 4 attempts left in 2159ms
pin: accepted in 2037ms
```

Two seconds a time, and a change is two derivations. That is not a pause, it is a lock screen
that looks broken, so it runs on a thread of its own with "Sprawdzam…" on screen while it does.
The number is still logged on every entry, which is how it was found.

Also learned, and filed rather than fixed: the television's own image-sticking protection draws
a drifting logo above our windows after a few minutes of a static screen (#50), which answers
D16's open question about whether our overlay outranks `tvsystemui` — it does not.

And that saver costs the child time. Measured from the recorder while it was demonstrably on
screen: seven minutes counted, the screen reporting on throughout, and the foreground app never
changing — so D20's exclusion cannot see it, because it works by recognising screen-saver
packages and this is a window rather than an activity. Worse, nothing else can see it either:
this television emits no `USER_INTERACTION` usage events, so "somebody is pressing buttons" is
not a question that can be asked here.

The one free signal is `AudioManager.isMusicActive()`, and the obvious objection to it turned
out not to apply here. Measured with a PS5 running on HDMI: the console's sound reaches Android
as a started player, `USAGE_MEDIA`, `CONTENT_TYPE_MOVIE`, 5.1 at 48 kHz, owned by
`com.mediatek.tis` — the TV firmware's own input service. So "nothing is playing" does not
quietly cover a console session, and HDMI time is counted correctly today
(`org.droidtv.playtv` shows up in the per-app breakdown). #51 has what a correct rule still
has to combine, including a grace period so that browsing menus keeps counting.

### D21 corrected: the HDMI source takes the focus back (measured, 2026-08-22)

D21 said an app that ignores focus loss keeps playing, and put HDMI out of reach. With a
console actually running, what happens is more specific than "ignores":

```
21:29:37.088  audio: focus held, playback should stop
21:29:37.169  overlay shown
21:29:37.174  audio: focus taken back (-1), something is playing
```

Eighty-six milliseconds. `com.mediatek.tis` runs as `system` and owns the input hardware, so it
does not merely decline to pause — it re-acquires focus. Confirmed from the room at the same
moment: the screen was covered and the sound carried on.

So there is no audio lever for an HDMI source. There is a picture lever, and it turns out to
carry the sound with it: bringing the launcher to the front leaves the room silent. Confirmed by
ear, and it is the app's own to pull — `Intent.CATEGORY_HOME`, exempt from the
background-activity-start restriction by the same app-op that lets us draw the lock.

Which corrects a claim made here an hour earlier: that stopping a console needs an input change
or a power cut from Home Assistant, and that a full-screen Activity would hide the picture
without touching the sound. Neither is true, and what misled me is worth keeping as a warning
about method: **`dumpsys audio` reports the input service's track as `state:started` whether or
not anything is audible.** It says `started` under the lock, when the sound carries on, and it
says `started` on the home screen, when the room is quiet. A started `AudioTrack` is not
evidence of sound on this hardware; the only reliable instrument was somebody in the room.

So the escalation is: take focus, and if that is not enough, send the television home.

### The source key cannot be blocked, only undone (measured, 2026-08-22)

The first question anybody asks is why the lock does not simply refuse the source key. Because
the key never reaches us. `KEYCODE_TV` switched the input back to the console while our lock
window held focus — the television's own system UI handles it, and an ordinary app is not in
that path. Intercepting it would need an accessibility service (refused in D15 and D16, because
merely enabling one unmasks password fields system-wide), lock task mode (Device Owner, which
needs a factory reset and is out of scope), or vendor privileges.

What is left is to make the switch worthless, which took three triggers rather than one, and
each of the first two was found by the next test failing:

- **audio focus taken back** — about 20 to 80 ms, and catches something that plays without
  coming to the front
- **an app arriving in front of the lock** — 35 ms once the 1.5-second poll notices it
- **a sweep every two seconds while the lock is up** — the one that matters most, because the
  other two are edges and an edge cannot see a state that was already wrong. With the console
  already in front and the focus already lost, pressing the source key changed nothing anything
  was watching, and the lock sat over a playing console indefinitely

Requests inside the cooldown are deferred to its end rather than dropped, which was also found
by testing: pressing the source key twice in quick succession beat the first version, because
the second request went in the bin and nothing else was ever going to arrive.

Measured against three presses in a row: the console holds the screen for under a second each
time, with the picture covered throughout. Sound is the only thing that gets through, and only
in those gaps.

## D24 — Availability is not permission (2026-08-22)

Every entity follows the TV's own availability topic, which is right: a value nobody can read
is not a value, and a crashed app must not look like a television with nothing to report. The
lock switch followed the same rule and that turned out to be wrong. A switched-off television
drops off the network — measured on the Philips, the screen reads `off` for about ninety
seconds and then the connection goes — so the switch greyed out exactly when a parent decided
the evening was over, and commands are never retained, so there was nowhere for the decision
to go.

Availability answers "do I know whether it is locked". It is the wrong answer to "may I ask
for it to be locked". So the lock switch alone stays operable while the TV is offline, holds
the intention, and sends it the moment the TV reports in.

Three things keep that from becoming the optimism this switch was deliberately built without:

The intention exists only until it can be sent, not until the TV confirms. Afterwards the
television's own reports are the truth again, which also means a command it declines — such as
unlocking while the budget is spent — cannot turn into one resent for ever.

An intention that matches what the TV last reported is not queued at all. A stale `unlock`
arriving at a set that woke up locked by its own budget would set the daily limit aside for
the rest of the day, from a switch nobody had touched since the night before.

It survives a Home Assistant restart, through `RestoreEntity`. An update at the wrong moment
should not quietly drop a decision about tonight.

What this does not fix is the gap after a cold start. The intention lands when the app reaches
the broker, and on a television that was fully off that is the reboot gap of D22 — most of
which is not ours to close.

### Measured, 2026-08-22

Armed while the set was off, then switched on. Standby rather than a cold boot — same process
id throughout, so nothing had to start:

```
20:42:22  screen off
20:44:43  availability goes offline        (2m21s of network after the screen went dark)
20:45     lock armed in Home Assistant     (pending: on, nothing published)
21:11:42.313  screen on
21:11:43.295  mqtt: connected
21:11:43.355  mqtt: subscribed
21:11:43.406  mqtt: command Lock            (51 ms after the subscription)
21:11:43.594  overlay shown
```

**1.28 seconds from the screen coming on to the lock being up**, and the reboot gap does not
apply because standby never killed the process. Also worth keeping: the network survives the
screen going off by well over a minute — 141 seconds here, about 90 earlier the same evening —
so a lock sent in that window arrives immediately and never becomes an intention at all.

That 51 ms is the margin the race in #57 was decided by. The app announced itself online
before subscribing to commands, so Home Assistant answered an announcement from a client that
was not yet listening; the subscription happened to land first. Fixed by swapping the order,
which is the correct one anyway: never advertise availability before you can act.

## D25 — A second mode, without Home Assistant (2026-08-22)

TVCP's shape is two apps and a cloud between them: one on the television, one on the parent's
phone, paired with a QR code. This project deliberately does not have that — Home Assistant is
the parent's side — but plenty of households do not run Home Assistant and never will. Not
being built now. This records what already keeps the door open and what would quietly shut it.

### What is already independent of Home Assistant

The enforcing half, all of it. D3 put the rules and the counter on the television and enforced
them offline so that a dead Home Assistant cannot unlock the set. The same choice means a
household with no Home Assistant at all already has a working enforcer, and a second mode needs
no second implementation of the part that matters. The parent PIN (D23) already locks and
unlocks at the set with nothing else running anywhere.

The boundary is thin and written down. `docs/mqtt-contract.md` is four topics of JSON with a
schema version, and nothing in it mentions Home Assistant: anything that speaks MQTT can be the
parent's side.

`:rules` is plain Kotlin with no Android and no MQTT in it, so a phone app could reuse the
budget arithmetic rather than reimplement it and disagree with the television.

Pairing (D14) is local — zeroconf, an HTTP endpoint on the television, a six-digit PIN. It was
built for Home Assistant and nothing about it is specific to Home Assistant. The television
already runs an HTTP server while pairing, which is the obvious seat for a parent interface on
the same network.

### The four shapes it could take

- **A page served by the television.** The server is already there; a parent on the same Wi-Fi
  opens it. No accounts, no cloud, no store listing, nothing extra to run. What it cannot do is
  reach a parent who is out — which is exactly where "the child is asking for more time" needs
  to arrive.
- **A broker without Home Assistant.** Mosquitto in a container, the contract unchanged, a
  phone app or web page as the client. The cheapest shape that keeps every feature, and it asks
  the household to run a broker, which is not much easier than running Home Assistant.
- **Notifications through something already solved.** ntfy or similar for the request push,
  with control staying local. Two moving parts instead of one, and answering from outside the
  house still needs a way in.
- **A hosted backend, as TVCP has.** The only shape that makes remote notifications reliable,
  and the only one with accounts, a privacy policy and a bill. Under AGPL the server source
  would be published too — which is this project's own choice to make, since the copyright is
  in one pair of hands.

### What would close the door

One invariant, and it is already the rule: **Home Assistant configures and displays, the
television decides.** Anything evaluated in Python rather than in `:rules` is a feature the
second mode would not have.

Three places where that will be tempting. M4's schedule has to be evaluated on the television
rather than turned into "lock now" commands from an automation. M3's request flow has to be
complete at the set on its own — the rate limit, the expiry, and telling the child that nobody
answered — with the notification being the part Home Assistant adds rather than the part that
makes it work. And M5's history lives only in the recorder, so a second mode either keeps a
rolling window on the device or has no statistics at all.

### Checked after M4 and M5 (2026-08-29)

The invariant is easy to state and easy to lose by accident, so it was audited once both
milestones were in rather than assumed:

- `:rules` has **zero** Android imports. The only matches for the word are the licence header and
  a comment explaining why the module exists. It compiles for the JVM and knows nothing about
  where it runs.
- M4's schedule, windows and per-app budgets are all decided by `RuleEngine`, in `:rules`. Home
  Assistant sends rules and reads answers; it computes none of them.
- M5's day summary is built on the television, from the state that is closing, and published. Home
  Assistant keeps the archive because it has a recorder — the set keeps exactly one closed day,
  which is the rolling window a second mode would need.
- The only `if` statements in the integration that mention limits are null checks for display.

One deliberate exception, and it is worth naming rather than hiding: the response to
`source_fight` lives in a blueprint (#59). That is not enforcement, it is escalation, and it
exists precisely because it needs authority the television does not have — switching its own
source or cutting its own power. A second mode would not have it, and would still work.

## D26 — The rules merge reaches inside objects (2026-08-23)

`set_rules` has merged rather than replaced since M2, so that a control which knows about the
daily limit cannot wipe a schedule it has never heard of. The merge was shallow, and that
guarantee held only while every rule's value was a number.

M4's first rule with an object for a value breaks it. A per-app budget names one package:
`{"app_limits_s": {"com.netflix.ninja": 1800}}` under a shallow merge replaces the whole map
and drops every other app's budget — silently, since nothing on either side compares the two.
Home Assistant cannot avoid it by reading the current map and sending it back complete, because
the television is the side that keeps the rules (D3) and does not publish them.

So objects merge key by key and a `null` removes at any depth. Arrays and scalars still replace
whole: a window in a list has no key identity to merge on, and half a schedule is worse than
the schedule that was already in force. `windows` is therefore always sent complete, which is
also how it is documented.

Two smaller decisions inside that, both because the alternative needs explaining rather than
because it is wrong. Emptying a nested object leaves the empty object behind — dropping the
container would mean that removing the last app's budget also removed the thing that holds
them, and clearing all of them at once is what a `null` on the container is for. And the
recursion stops after four levels and replaces instead: the rules are two levels deep, so this
is slack rather than a limit, but the merge walks a payload that arrived over the network and a
service whose job is to enforce a limit must not be killable by one.

## D27 — Every rule becomes a number of seconds, and the smallest one wins (2026-08-23)

M4 adds three ways for viewing to have to stop — the day's allowance, the hours it is allowed in,
and one app's own budget — on top of the daily limit that was already there. The obvious shape is
a check per rule, each with its own warning, its own countdown and its own way of covering the
screen. That is three times the surface for the two failures that matter most here, a television
locked when it should not be and unlocked when it should not be.

So every rule is reduced to the same thing: how many seconds until viewing has to stop. The
smallest of them is the one in force, the existing warning ladder and countdown work unchanged
whichever rule it is, and the verdict carries a reason saying which. `active_window` — declared in
the contract since M1 and never populated — is what the window half of that reason publishes.

Three decisions inside it, each of which could reasonably have gone the other way:

**A window list is a list of permissions.** Once any window exists, viewing outside the windows is
blocked on every day, including days no window mentions. The alternative — a day with no window of
its own is unrestricted — fails by silently not applying, and a parental control that quietly does
nothing is worse than one that is inconveniently strict. The cost is real: adding only a weekend
window closes Monday. So the lock says when viewing is allowed again, today at least, because
"blocked, and I cannot tell you why or for how long" is the state that gets a feature turned off.

**A spent app budget displaces the app; it does not cover the screen.** Netflix running out with
an hour of daily budget left is not the end of the evening, and covering everything would punish
the choice of app rather than the watching. It reuses the displacement built for #40. The reverse
also holds: behind a covered screen there is nothing to displace, and a spent day is the reason
worth explaining rather than whichever app happened to be in front.

**A limit set aside for tonight sets the hours aside with it, but not an app's own budget.** A
parent who lifts the lock at nine has answered the evening; re-covering the screen ten seconds
later because a window closed is exactly the "looks broken" failure the budget lock already
avoids. An app budget is a different rule, nobody lifted it, and displacement never puts a PIN
screen in front of anyone to lift it at — so it stands. Changing it means changing the rule, in
Home Assistant, which is where rules are edited.

One thing this does not do: work out that the next window is on Saturday. `opensAt` covers today
only. A lock screen has room for "allowed again at four" and not for a calendar.

## D28 — The lock's decisions move to `:rules` (2026-08-23)

Everything deciding whether the television was covered lived in `LockController` as two booleans
and a verdict, in `:app`, which has no test source set. Five bugs came out of it: only WITHIN
lifting a budget lock, `restoreFromMemory` gated behind locked storage, #42, #66, and the same
mistake as #66 one path along — a spent budget arriving during granted time wrote BUDGET over a
parent's decision, so a restart restored a lock that lifted by itself.

That is the worst place in the product to be checking by hand, one case at a time, on hardware.
The two failure modes it owns are a television locked when it should not be and unlocked when it
should not be.

So the state is a data class in `:rules` with pure transitions — verdict applied, manual lock,
manual unlock, unlock-until-reset, stand down for granted time, stand-down expiry, restore after a
reboot — each returning the new state and what should be different on screen. `LockController`
compares what was covered before against what should be covered now and touches the overlay, the
banner, audio focus and the two values in device-encrypted storage. It decides nothing.

Both values go to storage on every transition rather than at the places that used to write them,
which is what killed #66 and its sibling: there is now one place where the memory can disagree
with the state, and it is three lines long.

Twenty-three JVM tests cover the interleavings that used to need a television, including all five
bugs above. The controller lost two functions doing it, which matters more than it sounds: it and
`EnforcerService` both sit one function under the detekt threshold, with `maxIssues: 0` and no
baseline, so M4's wiring had to fit in the room the refactor made.

## D29 — Usage events say what moved, not what is there (measured, 2026-08-29)

The daily limit ran out while Netflix was playing. The lock covered the screen, the log said
playback should stop, and the sound carried on — reported by ear, which is the only instrument
that works here (D21). Asked what was in front, the service said `foreground=null`.

`UsageStatsManager.queryEvents` reports transitions. The monitor asked for the last sixty seconds,
so an app that came forward before the service started produced nothing to find — and by the time
a limit runs out, something has usually been playing for half an hour. The monitor then knew
nothing at all until somebody next changed app.

Two consequences, both silent. The lock had nothing to displace, so it covered a screen over a
programme that went on playing. And the counter had nothing to charge, so `per_app` was missing
whole programmes while the total stayed right.

Older than M4 and fatal to it: per-app budgets and app blocking are nothing but this value.

While nothing is known the question is asked a different way — the daily usage summary, most
recently used package first — and once an event has arrived that is never consulted again, because
events are the better answer. Measured after the fix: seeded as `com.netflix.ninja` at start-up,
and a lock raised over it displaced in 440 ms, with the sound stopping.

The general lesson is the one D21 already taught in a different costume: a value that is absent
looks exactly like a value that is correctly empty, and only the hardware can tell them apart.

## D30 — Settings cannot be kept out of reach by the app alone (measured, 2026-08-29)

Force stop, "draw on top" and the date all live behind the Settings app, so the whole product
rests on whether a child can get there. Three ways were on the table and none had numbers. Now
two of them do.

**What the lock already does, and when it does nothing.** Anything coming forward behind a lock
is sent home. Measured with Settings: it appeared 949 ms after being launched and was gone by
1705 ms — about three quarters of a second on screen. Force stop is a dozen D-pad presses away
from there, so behind a lock Settings is effectively unusable, and each attempt starts over.

The same measurement with no lock up: Settings stayed for the twelve seconds it was watched, and
would have stayed all day. That is the finding. The mechanism protects Settings exactly when a
child has no reason to go there, and does nothing on a weekday morning when the television is
unlocked and the app is one Force stop away from silence.

**`pm suspend` works, and an app cannot call it.** Suspending `com.android.tv.settings` replaces
it with the system's own "app is paused" screen — decisive, and reversible in one command.
But `setPackagesSuspended` needs Device Owner, Profile Owner, or a system permission, so nothing
this app can do at runtime reaches it. It is an ADB action a parent runs once at setup, and it
costs them Settings too: every picture setting, every network change, would need ADB to undo it
first. That is a real price, not a footnote, and it should be offered rather than recommended.

**Device Owner: still unmeasured, deliberately.** The set has no owner and D21's assumption that
provisioning needs a factory reset may well be wrong. It was not tested here because a device
owner is, on many devices, removable only by a factory reset — that is somebody's television, and
the decision is theirs to make knowingly rather than as a side effect of a spike.

**So the position for now.** Prevention is out of reach without a decision nobody has made yet.
Evidence is not: a force-stop, a revoked permission and a moved clock all raise alarms now, and
the force-stop alarm survives the restart that carries it. A child who disables the product no
longer does so quietly, and that is the whole of what this milestone can honestly claim.

## No open hardware questions from the M0 spike

Everything the spike set out to answer is answered, in D9 through D13. What it turned up
along the way is tracked as #16: the lock covers the screen but does not end the media
session, and for an external HDMI source it likely cannot.

### D31 — the television edits its own rules, by the same road Home Assistant uses

D25 said the enforcing half has to work with Home Assistant switched off, and it does. The
editing half did not: every rule could only be changed from the other side, so a house whose
Home Assistant was down could enforce a limit and never change one.

The settings screen now writes rules locally. It is not a second way of writing them — a local
edit is a `set_rules` that never went over the wire. It merges by the same rules, takes the next
revision, and is published, so Home Assistant learns what changed rather than being surprised by
it later. Two ways of writing the same thing is how they come to disagree.

The rules sit behind the parent PIN, the door pairing already sits behind (#98), and proving it
covers the visit rather than each press: three questions in a row with two seconds of hashing
between them is how a parent gives up halfway through.
