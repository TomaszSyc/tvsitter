# Parent panel, stage 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Home Assistant parent panel in the television's look, phone-first, with quick actions and answering time requests from the panel.

**Architecture:** The television reports a waiting request in its state; the integration exposes it and gains `tvsitter.add_time`; the panel's page leaves `page.py` for static files (classic scripts, no build step) served by the existing aiohttp server, one script per screen, sharing a small `TS` namespace.

**Tech Stack:** Kotlin (`:rules` JVM + Android `:app`), Python 3.14 (HA integration, aiohttp add-on), vanilla JS/CSS, Node page drivers run from pytest.

**Spec:** `docs/superpowers/specs/2026-10-11-parent-panel-stage1-design.md`

## Global Constraints

- Every commit bumps the patch version in `version.txt`, `custom_components/tvsitter/manifest.json` and `parent-panel/config.yaml` (quoted); `tests/test_version.py` checks all three. Commits happen only when the owner has authorised them for this run.
- Commit messages: one short line in the repo's style (`feat: …`, `fix: …`), no `Co-Authored-By`, no mention of AI tooling.
- No real household data anywhere (names, rooms, IPs, device names): fixtures use `TV Lounge`, `tv.example.*`, `notify.mobile_app_phone`.
- Palette, copied from `TvStyle.kt`: `INK #0B1117`, `DUSK #2E7184`, `SURFACE #141D26`, `RAISED #1C2732`, `LINE #2C3A47`, `EDGE #5A6B7A`, `TEXT #EEF3F6`, `SECONDARY #B4C1CC`, `TERTIARY #8798A7`, `ACCENT #5BE1BE`, `WARN #F6C467`, `ERROR #F4A9A3`. Always dark; no Home Assistant theme borrowing.
- No cards: content on the backdrop; the bottom sheet is the only raised surface. Touch targets ≥ 44 px. Text pairs ≥ WCAG AA. `prefers-reduced-motion` respected.
- Page text only through `textContent`; never `innerHTML`/`insertAdjacentHTML` with data. Every sentence through `phrase()` with a Polish entry in `parent-panel/panel/words.py`.
- No external fonts, CDNs or build step; Roboto with system fallback.
- Quick-action and answer amounts are fixed at 15 and 30 minutes.
- Kotlin: `./gradlew spotlessApply` then `spotlessCheck detekt :rules:test :app:lintDebug :app:assembleDebug` green (detekt limits: 15 functions per class, 80-line methods, 6 params per function/7 per constructor). Python: `pytest -q -p no:cacheprovider tests`, `ruff check .`, `ruff format --check .` green.
- AGPL header on every new source file; comments explain why, in English, in the surrounding style.

## Review Focus

1. A request answered from the phone notification while the panel is open — the amber panel must disappear on the next poll, not stay with live buttons (Task 6, test `request answered elsewhere drops the panel`).
2. Double-tapping +15 — must send one `add_time`, the button disabled until the answer (Task 6, test `a second tap while sending does nothing`).
3. Saving a block that touches or overlaps another on the same day — must merge into one, never send overlapping windows (Task 7, test `touching blocks become one`).
4. Reloading the panel while a change waits for a sleeping television — the day axis must show the waiting hours, not the old ones (Task 7, test `the axis draws the waiting hours`).
5. A 360 px wide phone with a long app name — no horizontal page scroll, the name truncates (Task 11, checked on the rendered 360 px preview).

---

### Task 1: Waiting request on the television (`:rules`)

**Files:**
- Modify: `rules/src/main/kotlin/app/tvsitter/rules/TimeRequests.kt`
- Test: `rules/src/test/kotlin/app/tvsitter/rules/RequestPolicyTest.kt`

**Interfaces:**
- Produces: `PendingRequest(id: String, askedMinutes: Int, askedAtMs: Long, appName: String? = null)` (new optional field, keeps `@Serializable` compatibility); `RequestPolicy.pendingAt(history: RequestHistory, nowMs: Long): PendingRequest?`.

- [ ] **Step 1: Write the failing tests** in `RequestPolicyTest.kt`:
  - `a waiting request is pending until it expires`: ask at `t`, `pendingAt(history, t + EXPIRY_MS - 1)` returns the request; `pendingAt(history, t + EXPIRY_MS)` returns `null`.
  - `an answered request is not pending`: after `grant(history, id, 15)`, `pendingAt(...)` is `null`; same after `refuse`.
  - `a stored request without an app name still reads`: `Json.decodeFromString<RequestHistory>` of a history JSON whose `pending` has no `appName` yields `appName == null`.
- [ ] **Step 2: Run** `./gradlew :rules:test --tests 'app.tvsitter.rules.RequestPolicyTest'` — expected FAIL (unresolved `pendingAt`).
- [ ] **Step 3: Implement** `pendingAt` (pending and `nowMs - askedAtMs < EXPIRY_MS`) and add `appName: String? = null` to `PendingRequest`; `RequestPolicy.ask` takes an extra `appName: String? = null` stored on the new pending request.
- [ ] **Step 4: Run** the same command — expected PASS; then `./gradlew :rules:test` all green.
- [ ] **Step 5: Commit** — `feat: the television knows which request is still waiting`.

### Task 2: `request_pending` in the state payload (contract + app)

**Files:**
- Modify: `rules/src/main/kotlin/app/tvsitter/rules/contract/StateSnapshot.kt`, `rules/src/test/kotlin/app/tvsitter/rules/contract/ContractCodecTest.kt`, `app/src/main/kotlin/app/tvsitter/tv/TimeRequester.kt`, `app/src/main/kotlin/app/tvsitter/tv/EnforcerService.kt`, `docs/mqtt-contract.md`

**Interfaces:**
- Consumes: Task 1 `RequestPolicy.pendingAt`, `PendingRequest`.
- Produces: `StateSnapshot.requestPending: PendingState? = null` serialised as `request_pending`, where `@Serializable data class PendingState(val id: String, @SerialName("asked_minutes") val askedMinutes: Int, @SerialName("asked_at") val askedAt: Long, @SerialName("app_name") val appName: String? = null)`; `TimeRequester.pending: PendingRequest?` (via `pendingAt(history, System.currentTimeMillis())`).

- [ ] **Step 1: Failing tests** in `ContractCodecTest.kt`: `a waiting request travels in the state` (encode a snapshot with `PendingState("ab12", 15, 1_791_700_000_000, "Netflix")`, the JSON has `request_pending.asked_minutes == 15`, decode round-trips); `no waiting request is no field` (encoded JSON has no `request_pending` key — `explicitNulls = false` is already the codec setting; assert it).
- [ ] **Step 2: Run** `./gradlew :rules:test --tests '*ContractCodecTest'` — FAIL.
- [ ] **Step 3: Implement** the field; in `EnforcerService.currentState()` set `requestPending = requests?.pending?.let { PendingState(it.id, it.askedMinutes, it.askedAtMs, it.appName) }`; `TimeRequester.ask()` passes `currentAppName()` into `RequestPolicy.ask`; `settle()` and expiry already change state — make sure both end with `telemetry?.publishSoon()` (through the existing `say`/callback path, or a new `onChanged: () -> Unit` set after construction, matching the class's "set after construction" pattern).
- [ ] **Step 4: Run** the Kotlin check set from Global Constraints — green. Document `request_pending` in `docs/mqtt-contract.md` beside the other state fields (optional, absent when nothing waits).
- [ ] **Step 5: Commit** — `feat: the state says when a request is waiting`.

### Task 3: Integration — pending request and `tvsitter.add_time`

**Files:**
- Modify: `custom_components/tvsitter/models.py`, `event.py`, `const.py`, `services.yaml`, `strings.json`, `translations/en.json`, `translations/pl.json`
- Test: `tests/test_event.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: Task 2 payload `request_pending`.
- Produces: `StateSnapshot.request_pending: PendingRequest | None` (`@dataclass(frozen=True, slots=True) class PendingRequest: id: str; asked_minutes: int; asked_at: int; app_name: str | None`); event entity `event.<tv>_time_request` attribute `pending` = `{"id", "asked_minutes", "asked_at", "app_name"}` or `None`; service `tvsitter.add_time` (target: the time-request event entity, field `minutes` int 1–240) sending `{"op": "unlock", "minutes": n}`; `SERVICE_ADD_TIME = "add_time"`; the active-app sensor's attributes gain `"fw": snapshot.firmware` beside the existing `lock_reason` and `until_s`.

- [ ] **Step 1: Failing tests:**
  - `test_models.py::test_a_waiting_request_is_read` — payload with `request_pending` → fields; `test_a_malformed_waiting_request_is_none` — `request_pending: "x"` → `None`, no exception.
  - `test_event.py::test_the_waiting_request_is_an_attribute` — snapshot with a pending request → entity `extra_state_attributes["pending"]["id"] == "ab12"`; with none → `None`.
  - `test_event.py::test_adding_time_unlocks_with_minutes` — `async_add_time(15)` publishes `{"op": "unlock", "minutes": 15}` on `<prefix>/cmd`, QoS 1, not retained.
  - `test_sensor.py::test_the_active_app_carries_the_version` — attribute `fw == "0.11.20"` for a snapshot with that firmware.
- [ ] **Step 2: Run** `pytest -q -p no:cacheprovider tests/test_event.py tests/test_models.py` — FAIL.
- [ ] **Step 3: Implement**; register `add_time` with `platform.async_register_entity_service` beside `grant_time`; strings in `services.yaml`/`strings.json`/both translations.
- [ ] **Step 4: Run** the full Python suite and ruff — green.
- [ ] **Step 5: Commit** — `feat: time can be added without being asked, and a waiting request is visible`.

### Task 4: Panel API — pending request, add time, answer

**Files:**
- Modify: `parent-panel/panel/api.py`
- Test: `tests/test_panel_api.py`

**Interfaces:**
- Consumes: Task 3 attribute `pending` on the entity with translation key `time_request`; services `tvsitter.add_time`, `tvsitter.grant_time`, `tvsitter.deny_time`.
- Produces: in `described()`: `"pending_request": {"id", "asked_minutes", "asked_at", "app_name"} | None`, `"lock_reason": str | None`, `"until_s": int | None` and `"version": str | None` (read from the active-app sensor's attributes); `apply()` actions `{"action": "add_time", "minutes": 15|30}`, `{"action": "grant", "req_id": str, "minutes": 15|30}`, `{"action": "deny", "req_id": str}`.

- [ ] **Step 1: Failing tests** (Recorder fake as in the file): `test_a_waiting_request_reaches_the_page`; `test_the_lock_reason_until_and_version_reach_the_page`; `test_adding_time_calls_add_time` (`("tvsitter", "add_time", {"entity_id": "x.time_request", "minutes": 15})`); `test_only_fifteen_or_thirty_minutes_can_be_added` (`minutes: 240` → `ValueError` whose text ends with "."); `test_granting_names_the_request`; `test_denying_names_the_request`; `test_answering_without_a_request_id_is_refused_in_words`.
- [ ] **Step 2: Run** `pytest -q -p no:cacheprovider tests/test_panel_api.py` — FAIL.
- [ ] **Step 3: Implement** the three `case` branches and the field; minutes validated against `{15, 30}`.
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: the panel can add time and answer a request`.

### Task 5: Static shell, tokens, router, polling

**Files:**
- Create: `parent-panel/panel/static/index.html`, `static/tokens.css`, `static/app.css`, `static/js/words.js`, `static/js/api.js`, `static/js/main.js`, `parent-panel/panel/shell.py`
- Modify: `parent-panel/panel/server.py`, `parent-panel/Dockerfile` (copy `static/`), `tests/test_panel_script.py`, `tests/test_panel_grid.py` (rename to `tests/test_panel_page.py`), `tests/page/dom.js`
- Test: `tests/test_panel_script.py`, `tests/test_panel.py`

**Interfaces:**
- Produces:
  - `shell.SCRIPTS: tuple[str, ...]` — load order `("words.js", "api.js", "sheet.js", "now.js", "rules.js", "apps.js", "history.js", "settings.js", "main.js")`; later tasks add their file to `static/js/` only (the tuple already names them; a missing file is a test failure from Task 5 on, so Tasks 6–10 each create theirs — Task 5 creates empty-namespace stubs `TS.screens.<name> = {render() {}}` for the five screens and `sheet.js`).
  - `shell.render_shell(said: dict[str, str] | None = None, language: str = "en") -> str` — same contract as today: `<html lang>`, `const SAID = …` with `</` escaped, then one `<script src="static/js/<f>">` per `SCRIPTS` entry (relative, for Ingress), `<link rel="stylesheet" href="static/tokens.css">` and `app.css`.
  - `shell.script() -> str` — the scripts concatenated in order, for Node drivers.
  - Browser namespace: `window.TS = {phrase(text, values?), api: {state(): Promise, act(body): Promise}, state: {televisions, current, error}, screens: {now, rules, apps, history, settings}, go(tab), sheet: {open(build), close()}}`; tabs `"now" | "rules" | "apps" | "history"`; settings opened by `TS.go("settings")`.
- [ ] **Step 1: Failing tests:** `test_panel_script.py::test_every_script_parses` (each file through `node --check`); `test_the_shell_names_every_script_once`; `test_no_script_closes_the_document` (`</script` absent from every file); `test_panel.py::test_static_files_are_served_without_cache` (aiohttp test client: `GET /static/js/main.js` → 200, `Cache-Control: no-store`, `GET /static/../server.py` → 404).
- [ ] **Step 2: Run** them — FAIL.
- [ ] **Step 3: Implement.** `tokens.css` holds the palette from Global Constraints as `--ink` … `--error`, a spacing scale (4/8/12/16/24/32 px), radius 12/20/22, type sizes 12/13/16/20/28/46 px. `app.css`: body `--ink` with the glow `radial-gradient(120% 55% at 50% -12%, var(--dusk) 0%, var(--ink) 70%)` fixed behind the page; header (dial, name, status, gear button with `aria-label`); bottom bar of four tabs, each a `<button>` with `aria-current="page"` when active, fixed with `env(safe-area-inset-bottom)` padding; `.pill`, `.pill--accent`, `.pill--outline`, `.pill--warn`, `:focus-visible` ring 2 px `--accent` with 2 px `--ink` gap. `api.js`: poll `api/state` every 5 s (existing behaviour: keep the last good state on error, set `TS.state.error`), `act()` POSTs to `api/action`. `main.js`: builds header and bottom bar, routes, re-renders the current screen on each poll without touching an element that has focus; with more than one television the name in the header is a `<select>` switching `TS.state.current`; when `TS.state.error` is set, a single "No connection to Home Assistant" line shows under the header and the screen keeps its last content.
- [ ] **Step 4: Run** the full suite — green (old page tests still import `page.py`; leave `page.py` until Task 11). Point `server.py`'s `index` at `shell.render_shell` and add the `/static` route (`app.router.add_static` refused: write a handler that resolves inside `static/` only and sets `no-store`).
- [ ] **Step 5: Commit** — `feat: the panel's page moves to static files in the television's colours`.

### Task 6: Now screen

**Files:**
- Create: `parent-panel/panel/static/js/now.js`, `tests/page/now.js`
- Modify: `parent-panel/panel/static/app.css`, `parent-panel/panel/words.py`

**Interfaces:**
- Consumes: `TS` from Task 5; television fields from `api.described()` (`reporting`, `locked`, `playing`, `remaining_today`, `limit_today`, `used_today`, `until_s`, `lock_reason`, `last_reported`, `apps`, `pending_request`); "allowed until" is now + `until_s` formatted HH:MM; actions from Task 4 plus existing `lock` and `clear_limit`.
- Produces: `TS.screens.now.render(root: Element, tv: object)`.

- [ ] **Step 1: Failing driver** `tests/page/now.js` (run by `test_panel_page.py` with `shell.script()`), checks named in its output:
  - `watching shows what is left and four actions` — remaining 45 → text `45 min`; buttons `+15 min`, `+30 min`, `Lock`, `No limit today`.
  - `a waiting request comes first` — `pending_request` set → amber panel is the first child of the screen, buttons `Give 15`, `Give 30`, `Not now`; tapping `Give 15` sends `{"action":"grant","req_id":"ab12","minutes":15}`.
  - `request answered elsewhere drops the panel` — next poll without `pending_request` → no amber panel.
  - `a second tap while sending does nothing` — two clicks on `+15 min` before the fetch resolves → one `add_time` sent; the button is `disabled` until it resolves.
  - `locked offers unlock first` — `locked: true` → first action `Unlock`, the reason and "allowed again at" line present.
  - `not reachable disables the immediate actions` — `reporting: false` → last-seen line, `+15 min` and `Lock` disabled with a reason line.
  - `a failed poll keeps the screen and says so` — the second `api/state` rejects → the Now content is unchanged and the "No connection to Home Assistant" line is present.
- [ ] **Step 2: Run** `pytest -q -p no:cacheprovider tests/test_panel_page.py -k now` — FAIL.
- [ ] **Step 3: Implement** the four states and today-by-app list; amounts fixed at 15/30; new phrases added to `words.py` (Polish).
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: the Now screen, with quick actions and a request to answer`.

### Task 7: Rules screen — how much and when, one day at a time

**Files:**
- Create: `parent-panel/panel/static/js/sheet.js` (replace stub), `parent-panel/panel/static/js/rules.js`, `tests/page/rules.js`
- Modify: `app.css`, `words.py`
- Delete: `tests/page/hours.js` (its scenarios move into `rules.js` as listed below)

**Interfaces:**
- Consumes: fields `hours` (`{mon: ["16:00", …]}`, half-hour slots, already overlaid with `pending_rules` by `api.py`), `week` (`{mon: minutes|null}`), `daily_limit`, `sleep_timer`, `pending_rules`, `following_schedule`; existing actions `hours` (whole week grid, unchanged payload), `number` (keys `daily_limit`, `limit_<day>`, `sleep_timer`), `forget_pending`.
- Produces: `TS.sheet.open(build: (root) => void)`, `TS.sheet.close()`; pure helpers on `TS.rules`: `blocks(slots: string[]): {from: string, to: string}[]` and `slots(blocks): string[]` (merge touching/overlapping, 30-minute steps, `"24:00"` allowed only as `to`).

- [ ] **Step 1: Failing driver** `tests/page/rules.js`:
  - `slots become blocks and back` — `["16:00","16:30","17:00"]` ↔ `[{from:"16:00",to:"17:30"}]`.
  - `touching blocks become one` — saving `16:00–17:00` next to `17:00–19:00` sends one window `16:00–19:00`.
  - `editing a block sends the whole week with only that day changed` — other days' slots byte-identical in the sent `hours`.
  - `the limit never moves the hours` — `−` on Saturday sends only `{"action":"number","key":"limit_sat",…}`.
  - `a limit over the window is said` — limit 240, window 210 min → amber note present.
  - `copy to weekdays` — sends Monday–Friday equal to the shown day, weekend untouched.
  - `the axis draws the waiting hours` — `pending_rules` with windows → axis shows those, amber bar with Undo sends `forget_pending`.
  - `hours from a schedule are read-only` — `following_schedule` set → no add/edit, note present.
  - Carried over from `hours.js`: a poll arriving while the sheet is open does not close it or change its values.
- [ ] **Step 2: Run** `pytest -q -p no:cacheprovider tests/test_panel_page.py -k rules` — FAIL.
- [ ] **Step 3: Implement** day chips (Mon–Sun, today selected on open), "How much" stepper (15-minute steps, "as daily" when `null`), the axis 06:00–24:00 with outlined blocks, the sheet with from/to selects in 30-minute steps (native `<select>` styled as wheels — accessible on Android), copy chips, the daily limit row (`number`, key `daily_limit`, the default for days without their own), sleep timer row, held bar.
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: the Rules screen edits one day on a time axis`.

### Task 8: Apps screen

**Files:**
- Create: `parent-panel/panel/static/js/apps.js`, `tests/page/apps.js`
- Modify: `app.css`, `words.py`

**Interfaces:**
- Consumes: `apps` (already without exempt packages), `allowed_apps`, `week_by_app`; existing actions `allowed_apps` (whole list), `app_limit` (`package`, `minutes|null`).
- Produces: `TS.screens.apps.render(root, tv)`.

- [ ] **Step 1: Failing driver** `tests/page/apps.js`: `the list is sorted by today's use`; `turning the allow-list on sends every listed app`; `blocking one app sends the list without it`; `the sheet sets and removes a daily limit` (`app_limit` with 60, then `null`); `a long name does not push the tag off the row` (name element has class `ellipsis`); `exempt packages never appear` (an `exempt_apps` entry absent).
- [ ] **Step 2: Run** `-k apps` — FAIL.
- [ ] **Step 3: Implement** letter tiles, tags (Allowed / Blocked / `N min a day`), the sheet with today and this week.
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: the Apps screen`.

### Task 9: Settings screen

**Files:**
- Create: `parent-panel/panel/static/js/settings.js`, `tests/page/settings.js`
- Modify: `app.css`, `words.py`
- Delete: `tests/page/asking.js` (its scenarios move here)

**Interfaces:**
- Consumes: `pin_set`, `warn_before`, `block_settings`, `following_schedule`, `version` and `last_reported` fields, the existing setup endpoint `api/setup` (phones) and actions `set_pin`, `clear_pin`, `number` (`warn_before`), `block_settings`, `schedule`, `stop_following`.
- Produces: `TS.screens.settings.render(root, tv)`; opened from the gear, back returns to the previous tab.

- [ ] **Step 1: Failing driver** `tests/page/settings.js`: every scenario of the old `asking.js` (phones offered, saving the first and second device, "Nobody" refused in words); `a PIN is four digits before it is sent` (`"12a4"` → message, nothing sent; `"1234"` → `set_pin`, field cleared); `back returns to the tab it came from`.
- [ ] **Step 2: Run** `-k settings` — FAIL.
- [ ] **Step 3: Implement** groups Parent / Television / Status.
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: settings behind the gear`.

### Task 10: History screen and the language

**Files:**
- Create: `parent-panel/panel/static/js/history.js`, `tests/page/history.js`
- Modify: `tests/page/language.js` (drive the new shell), `tests/test_panel_words.py` (scan `static/js/*.js` instead of `_SCRIPT`), `words.py`

**Interfaces:**
- Consumes: `apps` (today), `week_by_app`, `used_yesterday`.
- Produces: `TS.screens.history.render(root, tv)`.

- [ ] **Step 1: Failing tests:** driver `history.js` — `today and seven days are listed, longest first`; `nothing watched says so in a sentence`. `test_panel_words.py` — the existing four catalogue tests now read every `phrase(` in `static/js/*.js` (they fail until Tasks 6–10's phrases are in `words.py`).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**; complete the Polish catalogue; `language.js` checks the tab names and Now screen in Polish.
- [ ] **Step 4: Run** the full suite — green.
- [ ] **Step 5: Commit** — `feat: the History screen, and the panel in Polish`.

### Task 11: Retire `page.py`, document, preview

**Files:**
- Delete: `parent-panel/panel/page.py`
- Modify: any import of `panel.page` left in `server.py`/tests, `parent-panel/DOCS.md`, `docs/architecture.md` (append a decision record: the panel follows the television's look and is served as static files, with the reasons from the spec)
- Create (not committed): previews under `build/ui-preview/panel/` — phone 360×780 and 390×844, Now (all four states), Rules (with sheet open), Apps (with sheet open), Settings, History, rendered with headless Chrome from a local fixture server

- [ ] **Step 1:** `grep -rn "panel.page\|_SCRIPT" parent-panel tests` returns nothing after the change.
- [ ] **Step 2:** Full Python suite, ruff, and the Kotlin check set — green.
- [ ] **Step 3:** Render previews; check at 360 px: no horizontal scroll, long names truncate, bottom bar clear of content; fix CSS if not.
- [ ] **Step 4:** Scan the diff for household data: real names, rooms, device names, IPs and values taken from the live installation must not appear (fixtures use the names from Global Constraints).
- [ ] **Step 5: Commit** — `chore: the old page goes; the panel is documented`.
