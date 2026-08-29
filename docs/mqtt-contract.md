# MQTT contract

The only interface between the app on the TV and Home Assistant. Both halves of the
project live in the same repository precisely because they have to agree on this file —
changing the contract is a single commit touching both sides.

The topic prefix is configurable and defaults to `tvsitter/livingroom`. Referred to as
`<p>` below.

How a TV learns the broker address, credentials and prefix is **not** part of this contract:
that is pairing, described in `architecture.md` as D14. Nothing here should ever be typed
twice.

| Topic | Direction | QoS | Retained | Payload |
|---|---|---|---|---|
| `<p>/availability` | app → HA | 1 | yes (LWT) | `online` / `offline` |
| `<p>/state` | app → HA | 0 | yes | state snapshot (JSON) |
| `<p>/request` | app → HA | 1 | **no** | request from the child (JSON) |
| `<p>/cmd` | HA → app | 1 | **no** | command (JSON) |

Three rules the correctness of the whole thing rests on:

1. `availability` is registered as the **Last Will and Testament** when connecting.
   Without it a crashed app looks alive to Home Assistant — which looks exactly like a
   child who has not been watching TV.
2. `cmd` is **never** retained. A retained `{"op":"lock"}` would mean the lock comes back
   on its own, for no reason, after every broker or TV restart. Locking a television that
   is switched off therefore cannot work by leaving a message on the broker: Home Assistant
   holds the intention instead and sends it when the TV reports in (D24).
3. `state` is retained, so Home Assistant knows the state immediately after a restart
   instead of waiting for the next tick.

## `<p>/state`

```json
{
  "schema": 1,
  "ts": 1787315400000,
  "fw": "0.1.0",
  "screen_on": true,
  "locked": false,
  "app_id": "com.google.android.youtube.tv",
  "app_name": "YouTube",
  "used_today_s": 4210,
  "limit_today_s": 5400,
  "remaining_today_s": 1190,
  "bonus_today_s": 900,
  "per_app": { "com.google.android.youtube.tv": 3600, "com.netflix.ninja": 610 },
  "per_app_names": { "com.google.android.youtube.tv": "YouTube", "com.netflix.ninja": "Netflix" },
  "active_window": "weekday_afternoon",
  "lock_reason": "daily_limit",
  "until_s": 1190,
  "rules_rev": 7,
  "pin_set": true,
  "pin_changed_at": 1787400000000,
  "pin_changed_by": "tv"
}
```

- `schema` — contract version. A receiver rejects a payload with an unknown, higher
  version instead of guessing what the fields mean.
- `ts` — send time in epoch milliseconds. Lets a consumer recognise a stale retained payload.
- `limit_today_s` — the limit the TV is enforcing right now, or `null` when it is enforcing
  none. Published rather than assumed: the TV keeps the rules and enforces them offline
  (D3), so it is the only thing that knows what is actually in force. Without it Home
  Assistant would have to remember what it last sent and hope, which is how a dashboard ends
  up disagreeing with the television.
- `remaining_today_s` — `null` means "no limit", not zero.
- `per_app_names` — friendly names for the packages in `per_app`, and only those. The labels
  exist on the television and nowhere else, so a consumer without them can only graph
  `com.google.android.youtube.tv`. Deliberately not a list of everything installed: that is a
  different thing and one Play reviews harder (#14).
- `active_window` — identifier of the rule window in force, so that "why did it block me
  right now" is answerable.
- `lock_reason` — why the screen is covered, or `null` when it is not. One of `daily_limit`,
  `app_limit`, `outside_window`, or `manual` for a lock a parent asked for. A parent's own lock
  outranks whatever the rules were saying at the time: they asked for it, and "the day's
  allowance is gone" would answer a question nobody put.
- `until_s` — how long viewing may still go on, counting whichever rule binds first, or `null`
  when nothing does. **Not** the same as `remaining_today_s`, which is the day's budget and
  nothing else: a window closing at half past seven ends the evening with an hour of budget
  left, and `until_s` is the number the television is counting down to. Keeping them apart is
  deliberate — redefining `remaining_today_s` to mean "whichever runs out first" without
  changing its name is the kind of change nobody finds afterwards.
- `pin_set` — whether a parent PIN exists on the TV. Not the PIN and not its hash: nothing
  that could be attacked offline leaves the television. What it answers is whether the lock
  can be lifted at the set itself, which is worth knowing before the evening Home Assistant
  is unreachable rather than during it.
- `pin_changed_at` — when the PIN last changed, epoch milliseconds, or `null` if it never
  has. `pin_changed_by` is `tv` or `ha`, and is what makes the timestamp actionable: a change
  made in Home Assistant was made by somebody holding the parent's phone, one made on the
  television by whoever was in the room. Because `state` is retained, a change made while
  Home Assistant was down arrives on the next connect.

## `<p>/request`

```json
{ "id": "8f14e45f", "kind": "more_time", "app_id": "com.netflix.ninja", "app_name": "Netflix", "asked_minutes": 15, "ts": 1787315400000 }
```

`app_name` is what the television calls the app, sent rather than left to be worked out
on the other side: Home Assistant could only pair `app_id` against whatever the last state
payload said, and a child changing app in the same breath as asking breaks that — leaving a
parent reading a package name off their phone at nine in the evening.

`id` must be stable for a single request. The app ignores `grant`/`deny` carrying an
unknown or already-settled `req_id` — otherwise a parent tapping the notification twice
grants the time twice.

The TV decides whether the child may ask at all, and does so on its own so that the feature
still works with no Home Assistant in reach:

- **three an hour.** A button a child can press forty times teaches a parent to swipe the
  notification away without reading it, and after that the feature is worse than not having it
- **fifteen minutes after a refusal.** No should mean no for a while, not until the next press
- **ten minutes to answer.** After that the child is told nobody answered rather than being
  left in front of a screen that claims to be waiting. A `grant` arriving later is still
  honoured: the duplicate protection exists so that two taps are not thirty minutes, not to
  enforce punctuality on the person being generous
- `asked_minutes` is always 15. The child asks; the parent decides the number

All of it survives a restart, because force-stopping the app is something a child can do from
Settings.

## `<p>/rules`

The rules in force, exactly as the television has them, retained.

```json
{ "daily_limit_s": 5400, "days": { "sat": 7200 }, "warn_before_s": [900, 300] }
```

Published when they change and again on every connect. The television keeps the rules and
enforces them offline (D3), so it is the only thing that knows what is actually in force —
without this, Home Assistant can show the daily limit, because `state` carries that one, and
nothing else. "Why did it lock at half past seven" is a question a schedule invites and a
dashboard could not otherwise answer.

Sent as stored rather than as understood, unknown keys and all: a newer Home Assistant writing a
rule this television ignores should see it come back rather than watch it disappear and conclude
the write failed. `rules_rev` in `state` says which revision this is.

Retained, unlike `cmd`, and at least once, unlike `state`: rules change rarely, so a lost publish
would leave a dashboard showing last week's schedule until somebody happened to edit something.

## `<p>/day`

The last closed budget day, retained, and nothing older.

```json
{
  "schema": 1, "day": "2026-08-28",
  "used_s": 8040, "limit_s": 9000, "bonus_s": 900, "granted_s": 900, "lock_count": 2,
  "per_app": { "com.netflix.ninja": 3600 },
  "per_app_names": { "com.netflix.ninja": "Netflix" },
  "requests": { "asked": 3, "granted": 1, "denied": 1, "expired": 1 },
  "ts": 1787490000000
}
```

Published when the day rolls over at 04:00 and again on connect. Without it a day that ends leaves
nothing behind: the counter wipes the per-app split, and Home Assistant only knows what it was
told while it was listening — one that was down at four in the morning would have no yesterday at
all.

- `day` is the budget day as the counter names it, so one in the morning on a Saturday is still
  Friday. That is why it is not simply a calendar date.
- `limit_s` is what was **being enforced**, null when nothing was. Not what the rules said: a
  limit set aside at nine is a day with no limit, and claiming one would make the used total read
  as an overrun nobody allowed.
- `granted_s` is what a parent actually handed over during the day, which is not the same as
  `bonus_s` — that one is what was still unspent when the day closed.
- `requests` and `lock_count` cannot be worked out from the counter afterwards: a refused request
  leaves nothing behind, and neither does a lock that went up and came down.

One day only. The archive belongs to whoever is listening — the recorder now, an add-on or a
server later (D25) — and a television that keeps a month of history is a television with a
database on it.

## `<p>/alert`

Something a parent should hear about. QoS 1, **not** retained.

```json
{ "schema": 1, "id": "a1b2c3d4", "kind": "pin_lockout", "ts": 1787490000000,
  "detail": { "failures": 5, "seconds": 300 } }
```

Retained `state` is the wrong shape for these: a counter in it rewrites the payload on every wrong
keypress, and a value cannot say *when*. A request is the right shape and the wrong subject. So
every tamper signal is a `kind` here, and `detail` is free per kind — "five wrong guesses, shut for
five minutes" and "the clock moved four hours" have nothing in common but their shape.

Never retained: an alarm replayed after every broker restart is one a parent learns to ignore.
`id` is stable for one occurrence, so a redelivered alert is not a second alarm.

Kinds are registered as they are built: `pin_lockout`, `clock_changed`, `overlay_lost`,
`usage_lost`, `unclean_restart`, `source_fight`. A receiver that meets one it does not know shows
it rather than refusing it — a newer television must be able to raise an alarm an older
integration can still pass on.

Never the PIN, never its hash, never what was typed. An alarm that leaked any of those would be a
worse hole than the one it reports.

## `<p>/cmd`

```json
{ "op": "lock",      "reason": "bedtime" }
{ "op": "lock",      "in_minutes": 30 }
{ "op": "unlock",    "minutes": 30 }
{ "op": "grant",     "req_id": "8f14e45f", "minutes": 15 }
{ "op": "deny",      "req_id": "8f14e45f" }
{ "op": "set_rules", "rev": 8, "rules": { } }
{ "op": "set_pin",   "hash": { "iterations": 120000, "salt": "0f1e…", "hash": "9734…" } }
{ "op": "set_pin",   "hash": null }
{ "op": "stop_app",  "pkg": "com.google.android.youtube.tv" }
{ "op": "ping" }
```

`lock` carrying `in_minutes` is a **sleep timer**: it arms a deadline rather than covering the
screen now, and zero cancels one already armed. The television keeps that deadline in
device-encrypted storage, so pulling the plug does not buy the evening back, and the engine turns
it into the same thing every rule becomes — how long until viewing has to stop — which is where
its warnings and countdown come from. It is a command rather than a rule because it is one
evening's decision: it is not stored with the rules and does not survive the night.

Lifting the lock clears it. A deadline already past keeps saying zero, so a lock lifted without
clearing would come straight back on the next sample — and whoever lifted it has answered the
bedtime too.

`unlock` without `minutes` lifts the lock. If the daily limit is what put the lock there,
the limit is set aside until the next reset — anything less would be undone by the next
sample, ten seconds later. If the lock was one a parent asked for, the limit stays in force:
taking down a bedtime lock is not a decision to hand over the rest of the day's budget. A
correct parent PIN at the television means exactly the same thing.

A `set_rules` whose `rev` is not higher than the current `rules_rev` is ignored, which
protects against a duplicated message rolling the rules back.

`set_rules` **merges** into the rules already in force, and a key carrying `null` removes
it. So `{"daily_limit_s": null}` lifts the daily limit and leaves everything else alone,
and `{}` changes nothing — which is worth stating because the obvious reading is the
opposite. The alternative, replacing the whole object, would force whoever is editing to
know every rule in force; since the TV keeps the rules (D3) that means publishing all of
them and hoping the two copies agree, and it lets two controls on a dashboard quietly
clobber each other.

The merge reaches **inside objects**, key by key, and a `null` removes at any depth. So
`{"app_limits_s": {"com.netflix.ninja": 1800}}` sets one app's budget and leaves the other
apps' budgets alone, and `{"app_limits_s": {"com.netflix.ninja": null}}` removes just that
one. A `null` on the container itself — `{"app_limits_s": null}` — clears all of them.
Removing the last entry inside an object leaves an empty object behind rather than removing
the container; nothing reads the two differently.

Arrays and scalars **replace whole**. A window in a list has no key identity to merge on,
so `windows` is always sent complete, and half a schedule would be worse than the one
already in force. The merge stops recursing after four levels and replaces instead, which
is slack rather than a limit: the rules are two levels deep, and the bound is there because
this walks a payload that arrived over the network.

### The rules object

```json
{
  "daily_limit_s": 3600,
  "days": { "sat": 7200, "sun": 7200 },
  "windows": [
    { "id": "school",  "from": "16:00", "to": "19:30", "days": ["mon", "tue", "wed", "thu", "fri"] },
    { "id": "weekend", "from": "09:00", "to": "21:00", "days": ["sat", "sun"] }
  ],
  "app_limits_s": { "com.netflix.ninja": 1800, "com.twitch.android.app": 0 },
  "warn_before_s": [900, 300],
  "block_settings": false
}
```

What an absent key, a `null`, a `0` and an empty list each mean, per rule — stated because this
is where a misreading turns into a television that enforces the opposite of what was intended:

| key | absent | `null` | `0` | `[]` |
|---|---|---|---|---|
| `daily_limit_s` | no limit | removes it | no viewing today | — |
| `days.<day>` | that day takes `daily_limit_s` | removes the override | no viewing that day | — |
| `windows` | hours not restricted | removes them | — | hours not restricted |
| `app_limits_s.<pkg>` | app has no budget of its own | removes its budget | **app is blocked** | — |
| `warn_before_s` | the default, five minutes | back to the default | no warning | no warning |
| `block_settings` | Settings reachable | reachable | — | — |

- `days` is keyed `mon` … `sun`, and a full name (`monday`) is accepted on the way in. The day is
  the **budget day**, so watching at 01:00 on a Saturday is still Friday's allowance and Friday's
  limit — the same boundary the counter already uses.
- `windows` carry `id`, `from`, `to` and optionally `days`; an absent `days` means every day. Times
  are `HH:MM` and nothing else — `16:00:30` is refused rather than rounded. A window whose `from`
  equals its `to` is refused too: read as all day it hands over the evening, read as no time it
  takes one away, and neither is a guess worth making. The `id` is what `active_window` publishes.
- `app_limits_s` is keyed by package and counts against the same screen time as the daily budget.
  A blocked app is one with a budget of zero; there is no separate block list, because zero
  already means "none of that" everywhere else here.
- `warn_before_s` is seconds before the end, and the TV uses them farthest first. A single number
  is accepted where a list belongs. Duplicates and zeros are dropped: zero is how "no warning" is
  spelled, and the same warning twice is one warning.

- `block_settings` is a switch rather than a budget: "twenty minutes of Settings a day" is not a
  thing anybody means. It applies whether or not the lock is up, which is the point — behind a
  lock Settings already lasts under a second, and with no lock up it lasts all day (D30). The
  packages that count are resolved from the `ACTION_SETTINGS` intent rather than named, so this
  is not a Philips-only rule. Anything unreadable there is a **no**: a rule nobody can parse must
  not lock a parent out of their own Settings.

A rule the TV cannot read is not enforced, and it says which one in its log rather than guessing.
That degrades towards **less** enforcement — a window that fails to parse widens the evening
rather than closing it — which is deliberate, and the reason nothing may be dropped silently.

`set_pin` carries a **hash**, never the PIN: Home Assistant derives it, so the PIN itself
never reaches the broker. PBKDF2-HMAC-SHA256 over exactly four digits, and the parameters
travel with the digest so that raising the iteration count later does not invalidate a PIN
already in use. A `null`
hash removes the PIN — the same convention as a null rule value — and the key has to be
present, so a truncated command cannot quietly strip the PIN off a television.

No current PIN is required for this, because reaching it means publishing to the broker the
TV is paired with. Changing the PIN *at the television* does require the current one, and
cannot create a first PIN at all; D23 explains why. `set_pin` must never be retained: a
retained one would be replayed after every broker restart and put the old PIN back over a
PIN changed at the set.

`stop_app` is **not implemented and cannot be**, as D21 records: an ordinary Android app
cannot stop another one. It stays here as a name because the operation is still the right
shape for the problem, and a Device Owner build could honour it; nothing should be written
against it in the meantime.

## Watching it live

```bash
mosquitto_sub -h <broker> -u <user> -P <password> -t 'tvsitter/#' -v
```

Or in Home Assistant: Developer tools → MQTT → listen to `tvsitter/#`.
