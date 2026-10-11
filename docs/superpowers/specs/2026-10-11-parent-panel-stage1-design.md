# Parent panel, stage 1: the television's look, phone-first navigation, quick actions

Status: approved in conversation on 2026-10-11, awaiting review of this document.

## Why

The parent panel works but reads as a settings form. It does not look like the product on the
television, it is laid out for a desktop, and the things a parent does most — give a few minutes,
lock now, answer a request — are either buried or only possible from a notification.

The panel is used for three things about equally: reacting in the moment, setting rules, and
looking back at what was watched. It is opened mostly on a phone, in the Home Assistant companion
app.

## Scope and staging

The redesign is delivered in three stages, each released on its own:

1. **This document.** The television's visual language, phone-first navigation, the four screens
   and settings rebuilt, and quick actions including answering a time request from the panel.
2. History and trends (day-by-day charts over weeks, weekday against weekend) and an event log
   (requests and answers, locks, tamper alarms). Panel only; the data is already in Home
   Assistant's recorder.
3. Exceptions and modes (one-off days, holiday mode, a reward for tomorrow). Needs date-based rules
   on the television, a contract change and integration work.

Out of scope here: anything in stages 2 and 3, multiple children per television, and a lock at a
chosen time of day (the existing sleep timer stays in Rules).

## Visual language

- Always dark, regardless of the Home Assistant theme: the television's navy backdrop `#0B1117`
  with the mint glow from above, the same tokens as `TvStyle` (surfaces, lines, text levels).
- One accent, mint `#5BE1BE`, for what is active and for the number that matters. Amber `#F6C467`
  only for "needs attention" (a waiting request, an alarm, a held change). Rose for errors.
- Content stands on the backdrop as on the television's lock screen: no cards. Sections are
  separated by small uppercase headings, spacing and hairlines. A bottom sheet is the one raised
  surface, used for editing.
- The television's dial mark and Roboto. Touch targets at least 44 px; visible focus; reduced
  motion respected; WCAG AA contrast for every text pair.

## Navigation

- A header with the dial, the television's name, a one-line status and a gear icon.
- A bottom bar with four tabs: **Now**, **Rules**, **Apps**, **History**.
- Settings open from the gear as a screen of their own, with a back control.
- With more than one television, the header's name switches between them.

## Screens

### Now

One screen whose top changes with the television's state:

1. **Watching.** Status line: the app and for how long. A large "left today" figure, a progress
   bar against the limit, and the time viewing is allowed until. Quick actions: **+15 min**,
   **+30 min**, **Lock**, **No limit today**. Below, today's time by app.
2. **Request waiting.** An amber panel at the top: the request, how long ago, and **Give 15**,
   **Give 30**, **Not now**. It disappears when the request is answered from anywhere or expires.
3. **Locked.** A lock badge, the reason, and when viewing is allowed again. Primary action
   **Unlock**; also **+15 min** and **No limit today**.
4. **Not reachable.** When the television was last seen, and that its rules keep working and
   changes will wait for it. Immediate actions are disabled with a reason.

The amounts on the quick actions and on the request answers are fixed at 15 and 30 minutes; the
minutes the child asked for are shown in the request panel but do not change the buttons.

### Rules

- A row of weekday chips at the top; one day is edited at a time.
- **How much** on that day: the day's limit with − and +, and one sentence saying it is spent within
  the marked hours, with the length of the window. When the limit exceeds the window, an amber note
  says no more than the window can be watched. Changing the limit never changes the hours.
- **When** on that day: a vertical time axis with outlined blocks of allowed hours. Tapping empty
  space adds a block; tapping a block opens a bottom sheet with "from" and "to" wheels in 30-minute
  steps, and Delete, Cancel, Save.
- Copy the day to the weekend, to weekdays, or to the whole week.
- Below: the daily limit (the default for days without their own) and today's sleep timer.
- An amber bar, only while a change is held for a sleeping television, with Undo.
- Hours that come from a Home Assistant schedule helper are shown read-only with a note, as today.

### Apps

- A switch at the top: **Only chosen apps** (the allow-list), with one sentence on what it means.
- A list sorted by today's use: letter tile, name, today's time, and a state tag — Allowed, Blocked
  or the daily limit. Exempt packages (launcher, this app, the system, screen savers) are not listed.
- Tapping an app opens a bottom sheet: today and this week, Allowed/Blocked, and the daily limit
  with − and +, plus Remove limit.

### History (stage 1)

The current content in the new look: today by app and the last seven days by app. Stage 2 adds to
this tab.

### Settings

- **Parent:** the PIN (set, change, remove) and where time requests are sent (phone, second device).
- **Television:** warning before the end, block Settings on the television, take hours from a Home
  Assistant schedule.
- **Status:** the version on the television and when it last reported.

## Architecture

The page leaves `page.py` and becomes static files in the add-on, with no build step:

- `panel/static/index.html` — the shell: header, screen area, bottom bar.
- `panel/static/tokens.css` — palette, type and spacing, taken one-to-one from `TvStyle`.
- `panel/static/app.css` — layout and components: pills, bottom sheet, time axis.
- `panel/static/js/` — one module per job: `api.js` (poll every 5 s, send actions), `now.js`,
  `rules.js`, `apps.js`, `history.js`, `settings.js`, `sheet.js`, `words.js` (translations from
  `words.py`).

The aiohttp server serves `/static/*` with `no-store`, behind Ingress only, as today. All text is
set with `textContent`; no `innerHTML` with data.

## Changes outside the panel

1. **Television and contract:** an optional state field `request_pending` (id, asked minutes, when,
   app), set by `TimeRequester` while a request waits and cleared by an answer from any source or by
   expiry. Optional, so the schema version does not change.
2. **Integration:** a new action `tvsitter.add_time(minutes)` that sends the existing `unlock`
   command with minutes, and the pending request exposed as an attribute.
3. **Panel API:** new actions `add_time`, `grant`, `deny` (through `grant_time` and `deny_time`),
   and saving one day's hours, built on the existing whole-week save.

## Errors and edge cases

- Television asleep: rule changes are held as today; immediate actions are disabled with a reason.
- Home Assistant unreachable: the screen stays and a "no connection" line appears; nothing is wiped.
- A request answered from the phone, or expired: the panel drops it on the next poll.
- A limit larger than the day's window: allowed, with the amber note.

## Testing

- The existing Node page tests move to loading the modules from files; their scenarios stay
  (painting hours, held changes, requests).
- New page tests: the four Now states, editing a block on the day axis, copying days, the
  limit-over-window note, exempt packages hidden.
- Television: a JVM test for `request_pending` being set, cleared by an answer, and cleared on
  expiry.
- Integration: tests for `add_time` and for the pending-request attribute.
- Previews rendered in a headless browser at phone width for review before release.
