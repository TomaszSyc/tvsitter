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
   on its own, for no reason, after every broker or TV restart.
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
  "rules_rev": 7
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
{ "op": "stop_app",  "pkg": "com.google.android.youtube.tv" }
{ "op": "ping" }
```

`unlock` without `minutes` unlocks until the end of the budget day. A `set_rules` whose
`rev` is not higher than the current `rules_rev` is ignored, which protects against a
duplicated message rolling the rules back.

`stop_app` is **not implemented and cannot be**, as D21 records: an ordinary Android app
cannot stop another one. It stays here as a name because the operation is still the right
shape for the problem, and a Device Owner build could honour it; nothing should be written
against it in the meantime.

## Watching it live

```bash
mosquitto_sub -h <broker> -u <user> -P <password> -t 'tvsitter/#' -v
```

Or in Home Assistant: Developer tools → MQTT → listen to `tvsitter/#`.
