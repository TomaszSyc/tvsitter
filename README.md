<img src="brand/icon.png" width="96" align="right" alt="">

# TV Sitter

Parental control for **Android TV / Google TV**, driven from **Home Assistant**.
Screen time limits, a PIN-protected lock screen, and a "may I have more time?" request from
the remote that a parent answers with one tap on their phone.

Runs on your network. No cloud, no subscription.

> **Status: alpha, and in daily use on one television.** Everything below works on real
> hardware rather than in a test: the TV counts screen time against a day that starts at 04:00,
> enforces the rules behind a lock screen, and a child can ask for more time from the remote and
> have a parent answer it with one tap on a phone. A PIN lifts the lock at the set itself with no
> Home Assistant in reach.
>
> The rules are a daily limit, a different one per day of the week, the hours viewing is allowed
> in, a budget per app, an allow-list of the apps a child may open at all, and a sleep timer. All
> of them can be set from Home Assistant **or from the television**, behind the parent PIN. The
> television says why it locked, and Home Assistant graphs what was watched and keeps yesterday.
> It raises an alarm when somebody is at it: a keypad shut, a clock moved, a permission taken
> away, the app stopped.
>
> The screens are designed for a sofa now — a rail, three destinations, focus you can see across
> a room. The parent panel is a page that changes things now, not only a status board: one card
> per television with what is on, today's figures, the rules, the week, a budget per app and the
> allow-list. What is still thin: it is the youngest part of the project, and there are no
> screenshots in this README yet, which is the next thing worth fixing.
>
> **Tested on exactly one television** — a Philips Google TV TA5 on Android 14. If you try it
> on another, a [device report](../../issues/new?template=03-device-report.yml) is the most
> useful thing you could send.

## Why this exists

The starting point was [TVCP Guardian](https://play.google.com/store/apps/details?id=io.middlepoint.tvcp.guard),
which works well and covers most of what you would expect. Three things were missing,
and those are the reason for this project.

| | TVCP Guardian | TV Sitter |
|---|---|---|
| Price | 2.99 USD/month or 19.99 USD/year, 7-day trial | free, AGPL |
| Number of TVs | 1 per subscription | unlimited (topics carry a device id) |
| Time limit, PIN-protected lock | yes | **done** |
| App blocking, sleep timer | yes | **done** |
| Weekly schedules | announced | **done** — and allowed hours, and a budget per app |
| **"More time" request from the TV → actionable notification for the parent** | no | **done — the main reason this exists** |
| **Usage statistics and history** | no | **done** — per app, graphable, with yesterday kept |
| **At-a-glance "is the TV on, what is running"** | no | **done** |
| An allow-list — only these apps, rather than not that one | no | **done** |
| Rules changed at the television, with Home Assistant down | no | **done** |
| Where the data lives | vendor cloud | your MQTT broker and your Home Assistant |

## How it works

```
┌─ Android TV / Google TV ─────────────────────┐        ┌─ Home Assistant ─────────────┐
│ EnforcerService (foreground service)         │        │ custom_components/tvsitter   │
│  • detects the foreground app (usage events) │        │  • entities: screen, app,    │
│  • draws a lock screen over other apps       │  MQTT  │    time left, lock switch,   │
│  • counts screen time                        │◄──────►│    a number per rule         │
│  • rules edited at the set, behind the PIN   │        │  • time requests → push      │
│ RulesEngine (:rules, plain Kotlin)           │        │  • dashboard and statistics  │
└──────────────────────────────────────────────┘        └──────────────┬───────────────┘
                                                                       │ Home Assistant API
                                                        ┌──────────────┴───────────────┐
                                                        │ parent-panel (a HA App)      │
                                                        │  • its own pages via Ingress │
                                                        │  • optional, HA OS only      │
                                                        └──────────────────────────────┘
```

The panel never speaks MQTT. It asks Home Assistant, so the integration stays the only thing
that writes a rule — see D34.

**No accessibility service.** The permission asked for is "draw on top", not "read everything
on screen and every keystroke" — and merely having an accessibility service enabled stops
Android masking password fields, so a parent typing their account PIN on the TV would do it in
front of an audience. See D15 and D16 in [`docs/architecture.md`](docs/architecture.md).

The decision to block is made **on the TV**. A Home Assistant outage, a dropped Wi-Fi
link or a broker restart cannot unlock the TV. Home Assistant supplies the rules, shows
the state and handles requests for extra time.

Why not simply drive everything over ADB from Home Assistant, and every other decision
made so far: [`docs/architecture.md`](docs/architecture.md). The interface between the two
halves: [`docs/mqtt-contract.md`](docs/mqtt-contract.md).

## Requirements

- A TV or streaming device running Android TV / Google TV, **Android 8 or newer**.
- Home Assistant with an MQTT broker (the Mosquitto add-on is enough).
- ADB once, to grant the permissions Android TV will not let you grant from the remote —
  see [`docs/setup.md`](docs/setup.md).

Fire TV (Fire OS), Samsung (Tizen), LG (webOS) and Roku are not supported.

## Installation

**On the TV:** [`docs/setup.md`](docs/setup.md).

**In Home Assistant:** add this repository to HACS as a **custom repository** (category:
Integration), then install "TV Sitter" and restart. Or copy `custom_components/tvsitter/` into
your `config/custom_components/` by hand — either way, finish by adding "TV Sitter" from Devices
& Services.

It is not in the HACS default store and is not submitted to it. A custom repository needs one
paste of the URL and updates the same way afterwards.

**The parent panel** is optional and Home Assistant OS or Supervised only, because Apps do not
exist on Container or Core. It adds pages the integration cannot — see
[`parent-panel/`](parent-panel/). Everything that enforces a rule works without it; it talks to
Home Assistant rather than to your broker, so the integration stays the only thing that speaks
to a television.

## What it cannot do

Measured on the television it runs on, rather than guessed:

- **An external HDMI source cannot be stopped, only displaced.** The lock covers the screen and
  the TV is sent to its own home screen, which does silence a console — but pressing the source
  key brings it back, and the lock puts it away again a second or two later. Preventing the
  switch outright needs rights an ordinary app does not have.
- **The TV's own anti-burn-in screen saver can draw over the lock** on this Philips, because it
  belongs to the system UI ([#50](../../issues/50)).
- **Stopping another app is impossible**, so a blocked app is one the TV walks away from rather
  than one that gets killed. See D21 in [`docs/architecture.md`](docs/architecture.md).
- **Settings cannot be kept out of reach.** Behind a lock it lasts about three quarters of a
  second before the television is sent home, which is far too little to reach Force stop — but
  with no lock up it stays as long as anybody likes. What the app can do is notice: a force-stop,
  a revoked permission and a moved clock all raise alarms. See D30.
- Nothing here survives a factory reset, and it is not meant to. This is a house rule with
  teeth, not device management.

## Roadmap

| | Milestone | Contents | |
|---|---|---|---|
| M0 | foundation | repository, toolchain, app skeleton, on-device spike | done |
| M1 | telemetry | screen state and active app surfaced in Home Assistant | done |
| M2 | counter and lock | daily budget, day starting at 04:00, lock screen, PIN | done |
| M3 | time requests | button on the TV → actionable notification → granted time | done |
| M4 | rules | weekly schedule, allowed time windows, per-app budgets, app blocking, sleep timer | done |
| M5 | statistics and anti-tamper | per-app history, a closed day, alarms when somebody is at it | done |
| M6 | interface and graphics | screens designed for a ten-foot view, real artwork, the words a child reads | done |
| M7 | going public | this repository, opened | done |
| M8 | parent panel | pages of their own through Ingress, and the shapes Home Assistant configuration does not have | in progress |

## License

[AGPL-3.0-only](LICENSE). You may use, modify and redistribute it, provided you publish
the source of your changes under the same terms. Contribution rules and CLA:
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Disclaimer

An independent project, not affiliated with Google, Philips/TPV or MiddlePoint Solutions.
Android TV and Google TV are trademarks of Google LLC.
