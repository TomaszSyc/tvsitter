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
  "active_window": "weekday_afternoon",
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
- `active_window` — identifier of the rule window in force, so that "why did it block me
  right now" is answerable.
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
{ "id": "8f14e45f", "kind": "more_time", "app_id": "com.netflix.ninja", "asked_minutes": 15, "ts": 1787315400000 }
```

`id` must be stable for a single request. The app ignores `grant`/`deny` carrying an
unknown or already-settled `req_id` — otherwise a parent tapping the notification twice
grants the time twice.

## `<p>/cmd`

```json
{ "op": "lock",      "reason": "bedtime" }
{ "op": "unlock",    "minutes": 30 }
{ "op": "grant",     "req_id": "8f14e45f", "minutes": 15 }
{ "op": "deny",      "req_id": "8f14e45f" }
{ "op": "set_rules", "rev": 8, "rules": { } }
{ "op": "set_pin",   "hash": { "iterations": 120000, "salt": "0f1e…", "hash": "9734…" } }
{ "op": "set_pin",   "hash": null }
{ "op": "stop_app",  "pkg": "com.google.android.youtube.tv" }
{ "op": "ping" }
```

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

`set_pin` carries a **hash**, never the PIN: Home Assistant derives it, so the PIN itself
never reaches the broker. PBKDF2-HMAC-SHA256, and the parameters travel with the digest so
that raising the iteration count later does not invalidate a PIN already in use. A `null`
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
