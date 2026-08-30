"""The parent's page: one document, sent once, and true by itself thereafter.

The panel serves this shell and nothing else. Every value on it arrives from
`GET /api/state` and every change leaves through `POST /api/do`, so the markup here is a
constant with nothing in it to escape — nothing from Home Assistant is ever written into
it. The script sets what it reads with `textContent` instead: a television and an app
are named by whoever installed them, and a name is not markup.

No framework and no CDN. An App is reached through an Ingress URL nobody can predict, so
every address here is relative to the page and not to the host; and it is opened from a
phone on a network that may have no way out, so every byte of it is in it.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

# The television's own palette, from TvStyle.kt, which is the original. It lives twice
# because two languages read it, and the two halves of the product have to look like one
# thing to the person who owns both of them.
_STYLE = """
:root {
  color-scheme: dark;
  --backdrop: #0B1017;
  --surface: #141F2B;
  --raised: #1C2733;
  --edge: #24313F;
  --accent: #5BE1BE;
  --text: #F2F6F9;
  --muted: #8FA3B3;
  --warn: #FFC46B;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0;
  padding: 1rem;
  background: var(--backdrop);
  color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 54rem; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 0.2rem; }
h2 { font-size: 1.1rem; margin: 0 0 1rem; }
h3 {
  color: var(--muted);
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 1.6rem 0 0.2rem;
  text-transform: uppercase;
}
p { margin: 0; }
.lead { color: var(--muted); margin-bottom: 1.4rem; }
.empty { color: var(--muted); }
.banner {
  background: var(--surface);
  border-left: 4px solid var(--warn);
  border-radius: 14px;
  color: var(--warn);
  margin-bottom: 0.8rem;
  padding: 0.85rem 1.1rem;
}
.tabs { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.2rem; }
.card {
  background: var(--surface);
  border-radius: 22px;
  margin-bottom: 1rem;
  padding: 1.2rem;
}
@media (min-width: 40rem) {
  body { padding: 2rem; }
  .card { padding: 1.7rem; }
  .figure { padding: 0.9rem 1rem; }
}
button {
  background: var(--raised);
  border: 0;
  border-radius: 999px;
  color: var(--text);
  cursor: pointer;
  font: inherit;
  padding: 0.55rem 1.1rem;
}
button:hover { background: var(--edge); }
button[aria-pressed="true"] { background: var(--accent); color: var(--backdrop); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
input {
  background: var(--backdrop);
  border: 1px solid var(--edge);
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  padding: 0.45rem 0.6rem;
  width: 5rem;
}
input[type="checkbox"] {
  accent-color: var(--accent);
  height: 1.35rem;
  padding: 0;
  width: 1.35rem;
}
.pills { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
.pill {
  background: var(--raised);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.85rem;
  padding: 0.2rem 0.8rem;
}
.pill.yes { color: var(--accent); }
.pill.bad { color: var(--warn); }
.figures {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.figures.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.figure {
  background: var(--backdrop);
  border-radius: 16px;
  padding: 0.75rem 0.7rem;
}
.figure b {
  display: block;
  font-size: clamp(1.05rem, 4.6vw, 1.5rem);
  font-weight: 600;
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.figure span { color: var(--muted); font-size: 0.8rem; }
.figure.spent b { color: var(--warn); }
.lock {
  border-radius: 18px;
  font-size: 1.05rem;
  font-weight: 600;
  margin-top: 1rem;
  padding: 1rem;
  width: 100%;
}
.lock.up { background: var(--accent); color: var(--backdrop); }
.row {
  align-items: center;
  border-top: 1px solid var(--raised);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem 0;
}
.row .name { flex: 1 1 8rem; min-width: 0; }
.row .name small {
  color: var(--muted);
  display: block;
  font-size: 0.75rem;
  overflow-wrap: anywhere;
}
.row b { font-variant-numeric: tabular-nums; }
.unit { color: var(--muted); }
.tick { align-items: center; display: flex; gap: 0.45rem; }
.hint, .note { flex-basis: 100%; font-size: 0.85rem; }
.hint { color: var(--muted); }
.note { color: var(--accent); }
.note:empty { display: none; }
.note.bad { color: var(--warn); }
.split { display: grid; gap: 0.9rem; margin-top: 1.3rem; }
.app { display: grid; gap: 0.35rem 0.8rem; grid-template-columns: 1fr auto; }
.app .who {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app .much em { color: var(--muted); font-style: normal; }
.track {
  background: var(--raised);
  border-radius: 999px;
  grid-column: 1 / -1;
  height: 10px;
  overflow: hidden;
}
.track span {
  background: var(--accent);
  border-radius: 999px;
  display: block;
  height: 100%;
}
.foot { color: var(--muted); font-size: 0.8rem; margin-top: 1.1rem; }
"""

_BODY = """
<main>
<h1>TV Sitter</h1>
<p class="lead">Everything here comes from Home Assistant, which is the only thing that
talks to the televisions.</p>
<p class="banner" id="banner" hidden></p>
<p class="empty" id="nothing" hidden></p>
<div class="tabs" id="tabs" hidden></div>
<div id="panels"></div>
</main>
"""

# Wrapped in a function of its own so it declares nothing at all on `window`. That is
# tidiness for most of these names and a real trap for one of them: a browser window
# already has a `length`, and the formatter here is called what the television calls it.
_SCRIPT = """
(() => {
  "use strict";

  const MINUTES_PER_HOUR = 60;
  const POLL_MS = 5000;
  const NOTE_MS = 3000;

  /** So the shortest thing watched is still a bar rather than nothing at all. */
  const SHORTEST_BAR = 3;

  // The week in the order a week is read, keyed the way the state keys it.
  const WEEK = [
    ["mon", "Monday", "Mon"],
    ["tue", "Tuesday", "Tue"],
    ["wed", "Wednesday", "Wed"],
    ["thu", "Thursday", "Thu"],
    ["fri", "Friday", "Fri"],
    ["sat", "Saturday", "Sat"],
    ["sun", "Sunday", "Sun"],
  ];

  const banner = document.getElementById("banner");
  const nothing = document.getElementById("nothing");
  const tabs = document.getElementById("tabs");
  const panels = document.getElementById("panels");

  let views = new Map();
  let chosen = null;
  // Never a key any list can produce, so the first paint always builds, even the
  // first paint of nothing at all.
  let known = null;
  let seq = 0;

  function el(tag, cls, words) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    // Always the text side of the DOM. A television called by whoever set it up is not
    // markup, however much it looks like some.
    if (words !== undefined && words !== null) node.textContent = words;
    return node;
  }

  /** Unset, which is never zero: zero is a real setting everywhere in this project. */
  function unset(value) {
    return value === null || value === undefined;
  }

  /**
   * A length somebody reads rather than parses.
   *
   * The sensors carry whatever precision the arithmetic had — 167.95 minutes — and a
   * page is not the arithmetic. The unit is always on it, the way it is on the
   * television: a number that does not say what it is is not a number.
   */
  function length(minutes) {
    if (unset(minutes)) return "\\u2014";
    const total = Math.round(minutes);
    // A hard space between a number and its unit: three figures share the width of a
    // phone, and "2 h 48" over "min" is a number that has lost its unit at the one
    // width where the page most needs to be read.
    if (total < MINUTES_PER_HOUR) return total + "\\u00a0min";
    const rest = total % MINUTES_PER_HOUR;
    const hours = (total - rest) / MINUTES_PER_HOUR;
    return rest
      ? hours + "\\u00a0h " + rest + "\\u00a0min"
      : hours + "\\u00a0h";
  }

  /** What a rule looks like in a box somebody types into. Empty means unset. */
  function shown(minutes) {
    return unset(minutes) ? "" : String(Math.round(minutes));
  }

  function hold(note, words) {
    clearTimeout(note.timer);
    note.textContent = words;
    note.classList.remove("bad");
  }

  function say(note, words, bad) {
    hold(note, words);
    note.classList.toggle("bad", Boolean(bad));
    note.timer = setTimeout(() => { note.textContent = ""; }, NOTE_MS);
  }

  /**
   * Ask for a change, then read the state back rather than assume it took.
   *
   * The rules sensor's revision is what the television says it is enforcing, so the
   * only honest confirmation is the next answer from the server, not this one.
   */
  async function act(body, note, done) {
    hold(note, "Saving\\u2026");
    let answer = null;
    try {
      const back = await fetch("api/do", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
      });
      answer = await back.json();
    } catch (failure) {
      answer = {ok: false, error: "The panel could not reach the add-on."};
    }
    if (answer && answer.ok) say(note, done || "Saved", false);
    else say(note, (answer && answer.error) || "Home Assistant refused it.", true);
    await poll();
  }

  function warn(words) {
    banner.textContent = words || "";
    banner.hidden = !words;
  }

  async function poll() {
    let state = null;
    try {
      const back = await fetch("api/state", {headers: {"Accept": "application/json"}});
      state = (await back.json()) || {};
    } catch (failure) {
      // Keep what is on the screen. A phone that has just woken is offline for a second
      // and blanking the page for it would be the panel's own fault.
      warn("Home Assistant did not answer. This is what was last read.");
      return;
    }
    warn(state.error);
    paint(state.televisions || [], state.error);
  }

  function paint(list, error) {
    nothing.hidden = list.length > 0 || Boolean(error);
    if (!list.length) {
      nothing.textContent = "No televisions yet. The panel reads them from the TV " +
        "Sitter integration, so add that first \\u2014 this page is a second way to " +
        "see what it already knows, not a way round it.";
    }
    shelve(list);
    if (chosen === null || !views.has(chosen)) {
      chosen = list.length ? list[0].id : null;
    }
    show();
    list.forEach((tv) => {
      const view = views.get(tv.id);
      view.tv = tv;
      view.tab.textContent = tv.name;
      view.updates.forEach((update) => update(tv));
    });
  }

  /**
   * Build a panel per television, and only when the set of them changes.
   *
   * Everything below rewrites itself in place on every poll. A panel rebuilt instead
   * would take the focus, the caret and half a typed number down with it.
   */
  function shelve(list) {
    const key = list.map((tv) => tv.id).join("|");
    if (key === known) return;
    known = key;
    const fresh = new Map();
    list.forEach((tv) => {
      fresh.set(tv.id, views.get(tv.id) || build(tv.id));
    });
    views = fresh;
    tabs.replaceChildren(...list.map((tv) => views.get(tv.id).tab));
    panels.replaceChildren(...list.map((tv) => views.get(tv.id).node));
    // One television needs no way to choose between televisions.
    tabs.hidden = list.length < 2;
  }

  function show() {
    views.forEach((view) => {
      view.node.hidden = view.id !== chosen;
      view.tab.setAttribute("aria-pressed", String(view.id === chosen));
    });
  }

  function build(id) {
    const view = {id: id, tv: null, node: el("div"), updates: [], apps: new Map()};
    view.tab = el("button");
    view.tab.type = "button";
    view.tab.addEventListener("click", () => {
      chosen = id;
      show();
    });
    nowCard(view);
    todayCard(view);
    rulesCard(view);
    appsCard(view);
    hoursCard(view);
    return view;
  }

  function card(view, title) {
    const box = el("section", "card");
    box.appendChild(el("h2", null, title));
    view.node.appendChild(box);
    return box;
  }

  function line(box) {
    const node = el("div", "row");
    box.appendChild(node);
    return node;
  }

  function pill(into) {
    const node = el("span", "pill");
    into.appendChild(node);
    return node;
  }

  function tell(node, words, kind) {
    node.textContent = words;
    node.className = "pill " + kind;
  }

  function figure(into, label) {
    const box = el("div", "figure");
    const value = el("b");
    box.append(value, el("span", null, label));
    into.appendChild(box);
    return {box: box, value: value};
  }

  function nowCard(view) {
    const box = card(view, "Now");
    const trouble = el("div");
    const pills = el("div", "pills");
    const screen = pill(pills);
    const reporting = pill(pills);
    const pin = pill(pills);
    const figures = el("div", "figures two");
    const playing = figure(figures, "Playing");
    const left = figure(figures, "Left today");
    const lock = el("button", "lock");
    lock.type = "button";
    const note = el("p", "note");
    const foot = el("p", "foot");
    box.append(trouble, pills, figures, lock, note, foot);

    lock.addEventListener("click", () => {
      act({id: view.id, action: "lock", on: !view.tv.locked}, note);
    });

    view.updates.push((tv) => {
      // A television with something wrong with it says so in a line of its own, above
      // everything else on the card, rather than leaving a parent to work it out from a
      // figure that is missing.
      const said = tv.trouble || [];
      trouble.replaceChildren(...said.map((one) => el("p", "banner", one)));
      tell(screen, tv.screen ? "Screen on" : "Screen off", tv.screen ? "yes" : "");
      tell(reporting, tv.reporting ? "Reporting" : "Not reporting",
        tv.reporting ? "yes" : "bad");
      tell(pin, tv.pin_set ? "PIN set" : "No PIN", tv.pin_set ? "yes" : "bad");
      playing.value.textContent = tv.playing || "Nothing";
      spend(left, tv.remaining_today);
      lock.textContent = tv.locked ? "Lift the lock" : "Lock the television";
      lock.classList.toggle("up", Boolean(tv.locked));
      foot.textContent =
        (heard(tv.last_reported) + revision(tv.rules_revision)).trim();
    });
  }

  /** What is left, which stops at nothing left rather than going negative. */
  function spend(cell, remaining) {
    const gone = !unset(remaining) && remaining <= 0;
    cell.value.textContent = unset(remaining)
      ? "\\u2014"
      : length(Math.max(0, remaining));
    cell.box.classList.toggle("spent", gone);
  }

  function heard(when) {
    if (!when) return "Never reported. ";
    const at = new Date(when);
    if (isNaN(at.getTime())) return "Last reported " + when + ". ";
    const clock = at.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    return "Last reported at " + clock + ". ";
  }

  /** The one number that answers "has my change actually arrived". */
  function revision(count) {
    return unset(count) ? "" : "Rules revision " + count + ".";
  }

  function todayCard(view) {
    const box = card(view, "Today");
    const figures = el("div", "figures");
    const used = figure(figures, "Watched");
    const limit = figure(figures, "Limit today");
    const left = figure(figures, "Left");
    const aside = el("p", "foot");
    const split = el("div", "split");
    box.append(figures, split, aside);

    view.updates.push((tv) => {
      used.value.textContent = length(tv.used_today);
      limit.value.textContent = length(tv.limit_today);
      spend(left, tv.remaining_today);
      aside.textContent = besides(tv);
      bars(split, tv);
    });
  }

  function besides(tv) {
    const said = [];
    // A bonus of nothing is the ordinary day, and saying so every day is noise.
    if (!unset(tv.bonus_today) && tv.bonus_today > 0) {
      said.push("Bonus today " + length(tv.bonus_today) + ".");
    }
    if (!unset(tv.used_yesterday)) {
      said.push("Yesterday " + length(tv.used_yesterday) + ".");
    }
    return said.join(" ");
  }

  /**
   * The day split by app, longest first, the way the television draws it.
   *
   * Redrawn whole on every poll because there is nothing here to type into. The bar is
   * proportional to the longest thing watched rather than to the limit: the question
   * this answers is what he is watching, and against a limit every interesting row is
   * short.
   */
  function bars(into, tv) {
    const watched = (tv.apps || [])
      .filter((app) => app.minutes > 0)
      .sort((one, other) => other.minutes - one.minutes);
    if (!watched.length) {
      into.replaceChildren(el("p", "empty", "Nothing watched yet today."));
      return;
    }
    const longest = watched[0].minutes;
    into.replaceChildren(...watched.map((app) => bar(app, longest)));
  }

  function bar(app, longest) {
    const node = el("div", "app");
    const much = el("p", "much", length(app.minutes));
    if (!unset(app.limit)) {
      much.appendChild(el("em", null, " of " + length(app.limit)));
    }
    const track = el("div", "track");
    const fill = el("span");
    fill.style.width =
      Math.max(SHORTEST_BAR, (100 * app.minutes) / longest) + "%";
    track.appendChild(fill);
    node.append(el("p", "who", app.name || app.package), much, track);
    return node;
  }

  function rulesCard(view) {
    const box = card(view, "Rules");
    const daily = number(view, box, "Daily limit", "daily_limit",
      (tv) => tv.daily_limit);
    wipe(view, daily);
    number(view, box, "Sleep timer", "sleep_timer", (tv) => tv.sleep_timer,
      "How long from now until the television puts itself to bed.");
    number(view, box, "Warn before the end", "warn_before", (tv) => tv.warn_before,
      "One warning, this long before the allowance runs out.");
    switched(view, box, "Block the Settings app", "block_settings",
      (tv) => tv.block_settings,
      "So the rules cannot be turned off from the television itself.");

    box.appendChild(el("h3", null, "The week"));
    box.appendChild(el("p", "hint",
      "A day with its own allowance overrides the daily limit on that day. Clear one " +
      "to hand the day back; set it to zero to mean no viewing at all."));
    WEEK.forEach((day) => weekLine(view, box, day[0], day[1]));
  }

  /**
   * A rule that is one number, set where it is read.
   *
   * Committed when the box is left rather than by a button of its own: a button per
   * field on a phone is a column of buttons, and leaving a field is what a parent does
   * next anyway.
   */
  function number(view, box, label, key, read, tip) {
    const row = line(box);
    seq += 1;
    const tag = el("label", "name", label);
    const input = el("input");
    input.id = "n" + seq;
    input.type = "number";
    input.min = "0";
    input.step = "1";
    input.inputMode = "numeric";
    tag.htmlFor = input.id;
    const note = el("p", "note");
    row.append(tag, input, el("span", "unit", "min"));
    if (tip) row.appendChild(el("p", "hint", tip));
    row.appendChild(note);

    input.addEventListener("change", () => {
      const raw = input.value.trim();
      const value = Number(raw);
      if (raw === "" || !isFinite(value) || value < 0) {
        // There is no way to say "unset" to a number entity — it always holds a
        // number — and the one rule that can be taken away has its own button.
        input.value = shown(read(view.tv));
        say(note, "That wants a number of minutes.", true);
        return;
      }
      act({id: view.id, action: "number", key: key, value: value}, note);
    });

    view.updates.push((tv) => {
      if (document.activeElement !== input) input.value = shown(read(tv));
    });
    return {row: row, note: note};
  }

  /** Removing the daily limit outright, which zero cannot stand in for. */
  function wipe(view, field) {
    const button = el("button", null, "Remove");
    button.type = "button";
    field.row.insertBefore(button, field.note);
    field.row.insertBefore(el("p", "hint",
      "Removing it leaves the day uncapped. Zero is not the same thing: zero minutes " +
      "means no viewing today, which is a real thing a parent may mean."), field.note);
    button.addEventListener("click", () => {
      act({id: view.id, action: "clear_limit"}, field.note, "Limit removed");
    });
  }

  function switched(view, box, label, action, read, tip) {
    const row = line(box);
    seq += 1;
    const input = el("input");
    input.type = "checkbox";
    input.id = "s" + seq;
    const tag = el("label", "tick");
    tag.htmlFor = input.id;
    tag.append(input, el("span", null, label));
    const note = el("p", "note");
    row.append(tag);
    if (tip) row.appendChild(el("p", "hint", tip));
    row.appendChild(note);

    input.addEventListener("change", () => {
      act({id: view.id, action: action, on: input.checked}, note);
    });
    // A tick is never half-typed, so it is written back even while it has the focus:
    // after a refusal the box has to stop claiming what did not happen.
    view.updates.push((tv) => { input.checked = Boolean(read(tv)); });
  }

  function weekLine(view, box, key, name) {
    const row = line(box);
    seq += 1;
    const tag = el("label", "name", name);
    const input = el("input");
    input.id = "w" + seq;
    input.type = "number";
    input.min = "0";
    input.step = "1";
    input.inputMode = "numeric";
    input.placeholder = "\\u2014";
    tag.htmlFor = input.id;
    const hint = el("p", "hint");
    const note = el("p", "note");
    row.append(tag, input, el("span", "unit", "min"), hint, note);

    input.addEventListener("change", () => {
      const raw = input.value.trim();
      const value = Number(raw);
      if (raw !== "" && (!isFinite(value) || value < 0)) {
        input.value = shown((view.tv.week || {})[key]);
        say(note, "That wants a number of minutes, or nothing.", true);
        return;
      }
      // Empty is not zero. Empty hands the day back to the daily limit; zero is a day
      // with no viewing on it.
      act({
        id: view.id,
        action: "schedule",
        day: key,
        minutes: raw === "" ? null : value,
      }, note);
    });

    view.updates.push((tv) => {
      const own = (tv.week || {})[key];
      if (document.activeElement !== input) input.value = shown(own);
      hint.textContent = falls(own, tv.daily_limit);
    });
  }

  /** What an empty day means, said out loud, because a blank box says nothing. */
  function falls(own, daily) {
    if (own === 0) return "No viewing on this day.";
    if (!unset(own)) return "";
    if (unset(daily)) return "Takes the daily limit, which is not set either.";
    return "Takes the daily limit, " + length(daily) + ".";
  }

  function appsCard(view) {
    const box = card(view, "Apps");
    const lead = el("p", "hint");
    const list = el("div");
    box.append(lead, list);
    view.updates.push((tv) => {
      lead.textContent = restriction(tv.allowed_apps || []);
      appLines(view, list, tv);
    });
  }

  function restriction(allowed) {
    if (allowed.length) {
      return "Only the ticked apps may be opened; every other one is refused. A " +
        "budget of zero blocks an app whether or not it is ticked.";
    }
    // The way it fails matters more than the way it reads. Nothing enforced is
    // something a parent can undo; a television nobody can open is one that has locked
    // them out of the thing they would fix it with.
    return "The allow-list is empty, so every app is allowed. Untick one to start a " +
      "list: everything left ticked stays allowed and the rest are refused. A budget " +
      "of zero blocks an app on its own.";
  }

  /**
   * One line per app the set has seen.
   *
   * Lines are added and removed, never moved, because a line holds a number somebody
   * may be halfway through typing and a moved node drops the focus. That is also why
   * they are in the name's order rather than the minutes': minutes shuffle all day.
   */
  function appLines(view, list, tv) {
    const apps = (tv.apps || []).slice().sort(byName);
    const wanted = new Set(apps.map((app) => app.package));
    view.apps.forEach((held, id) => {
      if (!wanted.has(id)) {
        held.node.remove();
        view.apps.delete(id);
      }
    });
    apps.forEach((app, index) => {
      let held = view.apps.get(app.package);
      if (!held) {
        held = appLine(view, app.package);
        view.apps.set(app.package, held);
        list.insertBefore(held.node, list.children[index] || null);
      }
      held.fill(app);
    });
  }

  function byName(one, other) {
    return (one.name || one.package).localeCompare(other.name || other.package);
  }

  function appLine(view, id) {
    const node = el("div", "row");
    seq += 1;
    const who = el("div", "name");
    const name = el("span");
    who.append(name, el("small", null, id));
    const budget = el("input");
    budget.type = "number";
    budget.min = "0";
    budget.step = "1";
    budget.inputMode = "numeric";
    budget.placeholder = "\\u2014";
    const box = el("input");
    box.type = "checkbox";
    box.id = "p" + seq;
    const tag = el("label", "tick");
    tag.htmlFor = box.id;
    tag.append(box, el("span", null, "Allowed"));
    const note = el("p", "note");
    node.append(who, budget, el("span", "unit", "min"), tag, note);

    budget.addEventListener("change", () => {
      const raw = budget.value.trim();
      const value = Number(raw);
      if (raw !== "" && (!isFinite(value) || value < 0)) {
        say(note, "That wants a number of minutes, or nothing.", true);
        return;
      }
      // Empty takes the budget away; zero is a block. They are not the same thing and
      // the service takes both.
      act({
        id: view.id,
        action: "app_limit",
        package: id,
        minutes: raw === "" ? null : value,
      }, note);
    });

    box.addEventListener("change", () => {
      const packages = rebuild(view);
      act({id: view.id, action: "allowed_apps", packages: packages}, note,
        packages.length
          ? "Saved"
          : "Saved. An empty list is no restriction: every app is allowed again.");
    });

    function fill(app) {
      const called = app.name || app.package;
      name.textContent = called;
      budget.setAttribute("aria-label", "Minutes a day for " + called);
      if (document.activeElement !== budget) budget.value = shown(app.limit);
      box.checked = Boolean(app.allowed);
    }

    return {node: node, box: box, fill: fill};
  }

  /** The allow-list as the ticks stand, sent whole because that is how it is set. */
  function rebuild(view) {
    const packages = [];
    view.apps.forEach((held, id) => {
      if (held.box.checked) packages.push(id);
    });
    // An app that is allowed but has never been opened has no line to tick, and
    // dropping it here would quietly block it.
    (view.tv.allowed_apps || []).forEach((id) => {
      if (!view.apps.has(id) && packages.indexOf(id) < 0) packages.push(id);
    });
    return packages;
  }

  function hoursCard(view) {
    const box = card(view, "Hours");
    const list = el("div");
    box.append(list, el("p", "foot",
      "Shown, not edited. These hours come from a Home Assistant Schedule helper, " +
      "which is a weekly grid with a proper editor already \\u2014 draw the week " +
      "there and the television follows."));
    view.updates.push((tv) => {
      const windows = tv.windows || [];
      list.replaceChildren(...(windows.length
        ? windows.map(slot)
        : [el("p", "empty", "No hours set, so no hour of the day is refused.")]));
    });
  }

  function slot(one) {
    const node = el("div", "row");
    node.append(el("b", null, (one.from || "?") + " \\u2013 " + (one.to || "?")),
      el("span", "unit", days(one.days)));
    return node;
  }

  function days(list) {
    if (!list || !list.length) return "Every day";
    const said = WEEK.filter((day) => list.indexOf(day[0]) >= 0)
      .map((day) => day[2]);
    return said.length ? said.join(", ") : list.join(", ");
  }

  function beat() {
    // A panel in a pocket is a panel nobody is reading, and a phone's battery is worth
    // more than a figure that is five seconds fresher than the moment it is looked at.
    if (!document.hidden) poll();
  }

  document.addEventListener("visibilitychange", beat);
  setInterval(beat, POLL_MS);
  poll();
})();
"""


def render_shell() -> str:
    """Return the whole document, which is the same every time.

    There is nothing to interpolate: the page is a shell and the state arrives from
    `api/state` after it has loaded. Both addresses are relative, because an Ingress App
    is served under a path the Supervisor invents per session and an absolute one would
    leave the App altogether.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>TV Sitter</title>\n"
        "<style>" + _STYLE + "</style>\n"
        "</head>\n"
        "<body>" + _BODY + "<script>" + _SCRIPT + "</script>\n"
        "</body>\n"
        "</html>\n"
    )
