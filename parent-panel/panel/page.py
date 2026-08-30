"""The parent's page: one document, sent once, and true by itself thereafter.

The panel serves this shell and nothing else. Every value on it arrives from
`GET /api/state` and every change leaves through `POST /api/do`, so the markup here is a
constant with nothing in it to escape — nothing from Home Assistant is ever written into
it. The script sets what it reads with `textContent` instead: a television and an app
are named by whoever installed them, and a name is not markup.

Four destinations, one of them on the screen at a time, which is the shape the
television's own setup screen was given after somebody called the single scrolling
column chaos (#108, #109). The same complaint was true here and for the same reason:
five sections stacked down one page is not a panel, it is a document. The rail names the
destination, so a pane does not repeat the name back.

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
  /* One half hour of the weekly grid, the row it sits in, the column the day is
     named in, and the strip the hours are named across. */
  --cell: 14px;
  --tall: 26px;
  --label: 2.9rem;
  --head: 1.15rem;
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
/* Which television, which is not one of the destinations and never looks like one. */
.chooser {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 1.2rem;
}
.label {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.tabs { display: flex; flex-wrap: wrap; gap: 0.5rem; }
/*
 * The rail. Across the top on a phone, down the side from 720px, and the same four
 * destinations in the same order either way — the width changes where it is, never what
 * is in it.
 */
.rail { display: flex; gap: 0.4rem; margin-bottom: 1.1rem; }
.where {
  align-items: center;
  background: var(--surface);
  border-radius: 999px;
  color: var(--muted);
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  font-size: 0.8rem;
  font-weight: 600;
  gap: 0.15rem;
  justify-content: center;
  min-width: 0;
  padding: 0.5rem 0.3rem;
  text-decoration: none;
}
.where svg { fill: currentColor; flex: none; height: 1.3rem; width: 1.3rem; }
.where:hover { background: var(--edge); color: var(--text); }
/* Filled with the accent, the way the television marks the destination it is on. */
.where[aria-current="page"] { background: var(--accent); color: var(--backdrop); }
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
@media (min-width: 720px) {
  main { max-width: 66rem; }
  .shell {
    align-items: start;
    display: grid;
    gap: 1.6rem;
    grid-template-columns: 12rem minmax(0, 1fr);
  }
  .rail { flex-direction: column; margin: 0; position: sticky; top: 2rem; }
  .where {
    flex: 0 0 auto;
    flex-direction: row;
    font-size: 0.95rem;
    gap: 0.7rem;
    justify-content: flex-start;
    padding: 0.7rem 1.1rem;
  }
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
/* A card opening with a row opens with a rule across it, which reads as a mistake. */
.row:first-child { border-top: 0; }
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
/*
 * The week as a grid: seven rows of half hours, drawn on rather than listed.
 *
 * Three grids on rows and columns that line up, in two boxes. The days are named in a
 * column that does not scroll at all, because which day a row is, is the one thing that
 * has to stay on the screen while the week is dragged sideways under it. Sticky was
 * tried first and does not hold: a grid item is pinned inside its own grid area, so the
 * name slides off with the row it names.
 *
 * The hours and the week scroll together and are still two grids, because the week
 * takes `touch-action: none` — a finger drawn across it is drawing hours, not scrolling
 * — and a phone would otherwise have no way to reach the far end of the day. The strip
 * of hours above it keeps `pan-x` and drags the pair.
 *
 * The half hours are `1fr` with a floor under them: they share out a wide screen and
 * stop shrinking at a size a finger can still land on, which is where the card scrolls
 * instead. Forty-eight boxes squeezed onto a phone is forty-eight boxes nobody can tell
 * apart, which is the one thing this card exists to show.
 */
.hoursbox {
  background: var(--backdrop);
  border-radius: 16px;
  display: flex;
  margin: 0.6rem 0;
  padding: 0.5rem;
}
.names {
  display: grid;
  flex: none;
  gap: 1px;
  /* The empty first row is the strip of hours, so the days line up beside them. */
  grid-template-rows: var(--head) repeat(7, var(--tall));
  margin-right: 0.4rem;
  width: var(--label);
}
/* Without this the scroller takes the width of its widest row and nothing scrolls. */
.hours { flex: 1 1 auto; min-width: 0; overflow-x: auto; }
.ticks, .week {
  display: grid;
  gap: 1px;
  grid-template-columns: repeat(48, minmax(var(--cell), 1fr));
}
.ticks {
  grid-auto-rows: var(--head);
  /* The gap the days keep between the strip and Monday, kept here as well. */
  margin-bottom: 1px;
  touch-action: pan-x;
}
.tick {
  color: var(--muted);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
  grid-column: span 6;
  line-height: var(--head);
}
.week {
  grid-auto-rows: var(--tall);
  touch-action: none;
  user-select: none;
}
/* Nothing to draw while a schedule helper owns the hours, so the finger has it back. */
.week.off { touch-action: pan-x; }
.day {
  background: var(--raised);
  border-radius: 8px;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0 0.4rem;
  text-align: left;
}
/* Written twice over the shared button rule, which would put a hover colour on both. */
.cell, .cell:hover {
  background: var(--surface);
  border-radius: 3px;
  padding: 0;
}
.cell.on, .cell.on:hover { background: var(--accent); }
.cell:enabled:hover { box-shadow: inset 0 0 0 1px var(--muted); }
/* A ring three pixels off a fourteen-pixel box swallows its neighbours. */
.cell:focus-visible { outline-offset: 1px; }
.cell:disabled, .day:disabled { cursor: default; }
/* Read-only, so a day is a label rather than something that looks pressable. */
.day:disabled { background: none; }
"""

# The rail is markup rather than script because the destinations are the one thing on
# this page that does not come from Home Assistant: there are four of them, they are the
# same four every time, and written here they are links a browser can follow on its own.
#
# The icons are the television's own drawables, path for path, so the two halves of the
# product are still recognisably one thing: the dial from the app's mark, three bars,
# two sliders. Apps is the odd one out — the television has no such destination — so it
# gets the tile grid every launcher already uses for the same idea.
_BODY = """
<main>
<h1>TV Sitter</h1>
<p class="lead">Everything here comes from Home Assistant, which is the only thing that
talks to the televisions.</p>
<div class="chooser" id="chooser" hidden>
<p class="label" id="which">Television</p>
<div class="tabs" id="tabs" role="group" aria-labelledby="which"></div>
</div>
<p class="banner" id="banner" hidden></p>
<p class="empty" id="nothing" hidden></p>
<div class="shell">
<nav class="rail" id="rail" aria-label="Sections">
<a class="where" id="go-now" href="#now"><svg viewBox="0 0 24 24"
aria-hidden="true"><path d="M12,2A10,10 0 1,0 22,12A10,10 0 0,0 12,2ZM12,4A8,8
0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4Z"/><path
d="M12,12L12,6A6,6 0 1,1 6,12Z"/></svg><span>Now</span></a>
<a class="where" id="go-today" href="#today"><svg viewBox="0 0 24 24"
aria-hidden="true"><path d="M4,14h4v6h-4z"/><path d="M10,8h4v12h-4z"/><path
d="M16,11h4v9h-4z"/></svg><span>Today</span></a>
<a class="where" id="go-rules" href="#rules"><svg viewBox="0 0 24 24"
aria-hidden="true"><path d="M3,6h18v2h-18z"/><path d="M3,16h18v2h-18z"/><path
d="M8,7m-3,0a3,3 0 1,0 6,0a3,3 0 1,0 -6,0"/><path d="M16,17m-3,0a3,3 0 1,0
6,0a3,3 0 1,0 -6,0"/></svg><span>Rules</span></a>
<a class="where" id="go-apps" href="#apps"><svg viewBox="0 0 24 24"
aria-hidden="true"><path d="M4,4h7v7h-7z"/><path d="M13,4h7v7h-7z"/><path
d="M4,13h7v7h-7z"/><path d="M13,13h7v7h-7z"/></svg><span>Apps</span></a>
</nav>
<div id="panels"></div>
</div>
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

  // The grid is half-hourly, the same half hours the rules are written in. Finer would
  // be ninety-six boxes to hit on a phone; coarser could not say the half past four a
  // school day actually starts at.
  const SLOT_MINUTES = 30;
  const SLOTS = (24 * MINUTES_PER_HOUR) / SLOT_MINUTES;

  /** How often the hour is named above the grid. All forty-eight would be a smear. */
  const TICK = 6;

  /** How long a keyed change waits for the next, so a held key is still one write. */
  const KEYED_MS = 400;

  // The arrows, as a day and a half hour to move by. Clamped rather than wrapped: an
  // arrow that runs off Monday morning into Sunday night is a box nobody aimed at.
  const MOVES = {
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
  };

  // The destinations, in the rail's order, keyed the way the address bar spells them.
  // The first is the start destination and the answer to anything unrecognised.
  const WHERE = ["now", "today", "rules", "apps"];

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
  const chooser = document.getElementById("chooser");
  const tabs = document.getElementById("tabs");
  const rail = document.getElementById("rail");
  const panels = document.getElementById("panels");
  const links = new Map(
    WHERE.map((name) => [name, document.getElementById("go-" + name)]),
  );

  let views = new Map();
  let chosen = null;
  let where = WHERE[0];
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

  /**
   * The time one half hour of the grid starts, spelled the way the rules spell it.
   *
   * The box past the end of the day is midnight, so the last box of a day reads as
   * 23:30 to 00:00 rather than to a twenty-fifth hour.
   */
  function clock(slot) {
    const minutes = (slot % SLOTS) * SLOT_MINUTES;
    return two(Math.floor(minutes / MINUTES_PER_HOUR)) +
      ":" + two(minutes % MINUTES_PER_HOUR);
  }

  function two(count) {
    return String(count).padStart(2, "0");
  }

  /** Keep a move inside the week, or inside the day, whichever is being moved along. */
  function within(place, howMany) {
    return Math.max(0, Math.min(howMany - 1, place));
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
    // One television needs no way to choose between televisions. The chooser is its own
    // control rather than a fifth destination: which set is being looked at and which
    // part of it is being looked at are two questions, and answering them in one row of
    // buttons is how the page ended up unreadable in the first place.
    chooser.hidden = list.length < 2;
    // Nothing to look at is nothing to navigate.
    rail.hidden = list.length === 0;
  }

  /**
   * Which destination the address bar is asking for.
   *
   * An unknown name is the start destination rather than an error: the hash is typed by
   * hand, kept in bookmarks and carried between versions of this page, so it is a
   * request and not an instruction.
   */
  function asked() {
    const name = (window.location.hash || "").replace("#", "");
    return links.has(name) ? name : WHERE[0];
  }

  /**
   * The address bar is where the destination lives, and this is the only reader of it.
   *
   * Nothing here sets it: the rail is four ordinary links, so the browser writes the
   * hash, the back button rewrites it, and a reload hands it back. Keeping the choice
   * in a variable as well would give two answers to one question.
   */
  function route() {
    where = asked();
    show();
  }

  /** One television and one destination showing, wherever the two were last set. */
  function show() {
    links.forEach((link, name) => {
      link.setAttribute("aria-current", name === where ? "page" : "false");
    });
    views.forEach((view) => {
      view.node.hidden = view.id !== chosen;
      view.tab.setAttribute("aria-pressed", String(view.id === chosen));
      view.panes.forEach((pane, name) => { pane.hidden = name !== where; });
    });
  }

  function build(id) {
    const view = {
      id: id,
      tv: null,
      node: el("div"),
      updates: [],
      apps: new Map(),
      panes: new Map(),
    };
    view.tab = el("button");
    view.tab.type = "button";
    view.tab.addEventListener("click", () => {
      chosen = id;
      // Only the television changes. Somebody comparing two sets is on one destination
      // and wants the same one on the other set.
      show();
    });
    WHERE.forEach((name) => {
      const pane = el("div", "pane");
      view.panes.set(name, pane);
      view.node.appendChild(pane);
    });
    nowPane(view);
    todayPane(view);
    rulesPane(view);
    appsPane(view);
    return view;
  }

  /**
   * A card on one destination. The first card of each goes untitled: the rail already
   * says where this is, and a heading repeating it is a word that carries nothing.
   */
  function card(view, name, title) {
    const box = el("section", "card");
    if (title) box.appendChild(el("h2", null, title));
    view.panes.get(name).appendChild(box);
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

  /** The start destination: is it working, what is on, and is the lock up. */
  function nowPane(view) {
    const box = card(view, "now");
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

  /** The day as it stands: three figures, then where the time actually went. */
  function todayPane(view) {
    const box = card(view, "today");
    const figures = el("div", "figures");
    const used = figure(figures, "Watched");
    const limit = figure(figures, "Limit today");
    const left = figure(figures, "Left");
    const aside = el("p", "foot");
    const split = el("div", "split");
    box.append(figures, aside, el("h3", null, "By app"), split);

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

  /**
   * Everything that can be changed, in three cards: what holds every day, what a
   * particular day overrides it with, and — at the bottom, as the grid it is — the
   * hours of the week viewing is allowed in whatever the limits say.
   */
  function rulesPane(view) {
    const box = card(view, "rules");
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

    const week = card(view, "rules", "The week");
    week.appendChild(el("p", "hint",
      "A day with its own allowance overrides the daily limit on that day. Clear one " +
      "to hand the day back; set it to zero to mean no viewing at all."));
    WEEK.forEach((day) => weekLine(view, week, day[0], day[1]));

    hoursCard(view);
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

  function appsPane(view) {
    const box = card(view, "apps");
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

  /**
   * The hours, as the week they already are: seven rows of half hours to draw on.
   *
   * They were read-only here, on the reasoning that Home Assistant's Schedule helper is
   * a weekly editor already (D33). Sending a parent out of the panel to a helper dialog
   * is the same complaint that split this page into destinations in the first place, so
   * the grid is here too; the helper is still there for whoever prefers it.
   *
   * Nothing leaves while a finger is down. A drag over ninety boxes is one decision,
   * and ninety writes would be ninety revisions of the rules for the television to
   * fetch — with the last of them landing well after the finger had lifted.
   */
  function hoursCard(view) {
    const box = card(view, "rules", "The hours");
    const warning = el("p", "banner");
    const lead = el("p", "hint",
      "Drag across the boxes to allow viewing in them, and drag out of a marked box " +
      "to clear instead. A day name takes the whole day. From the keyboard: the " +
      "arrows move, space marks, and shift with an arrow paints.");
    const frame = el("div", "hoursbox");
    const names = el("div", "names");
    const scroller = el("div", "hours");
    const ticks = el("div", "ticks");
    const week = el("div", "week");
    const open = el("p", "empty",
      "No half hour is marked, so the hours are not restricted at all: the " +
      "television may be watched at any time of day, within whatever the limits " +
      "above allow.");
    const note = el("p", "note");
    week.setAttribute("role", "group");
    week.setAttribute("aria-label", "The half hours viewing is allowed in");
    // The empty box above Monday, which is the strip of hours the days line up with.
    names.appendChild(el("div", "corner"));
    for (let slot = 0; slot < SLOTS; slot += TICK) {
      ticks.appendChild(el("div", "tick", clock(slot)));
    }
    scroller.append(ticks, week);
    frame.append(names, scroller);
    box.append(warning, lead, frame, open, note);

    // What is drawn, kept beside the boxes rather than read back off them: a gesture
    // asks what the week looked like before it started, and a class name cannot say.
    const ticked = WEEK.map(() => new Array(SLOTS).fill(false));
    const labels = [];
    const cells = [];
    // The value the last change set, which is what shift with an arrow goes on
    // painting. Marking is the guess before anything has been changed: an empty grid
    // is the one somebody has come here to draw on.
    let lately = true;
    let painting = null;
    let pending = null;

    WEEK.forEach((day, row) => {
      const label = el("button", "day", day[2]);
      label.type = "button";
      label.setAttribute("aria-label", "Every half hour of " + day[1]);
      label.addEventListener("click", () => { whole(row); });
      labels.push(label);
      names.appendChild(label);
      const line = [];
      for (let slot = 0; slot < SLOTS; slot += 1) {
        const cell = el("button", "cell");
        cell.type = "button";
        cell.tabIndex = -1;
        // Where a box is, on the box, because a pointer arrives as a point on the
        // screen and has to be turned back into a day and a half hour.
        cell.atDay = row;
        cell.atSlot = slot;
        cell.setAttribute("aria-pressed", "false");
        cell.setAttribute("aria-label",
          day[1] + " " + clock(slot) + " to " + clock(slot + 1));
        line.push(cell);
        week.appendChild(cell);
      }
      cells.push(line);
    });
    let keyed = cells[0][0];
    keyed.tabIndex = 0;

    /** Whether the hours belong to a schedule helper, and so are not ours to write. */
    function sealed() {
      return Boolean(view.tv && view.tv.following_schedule);
    }

    /**
     * Whether somebody is in the middle of something a poll would take off them.
     *
     * The rule the typed numbers keep, in the terms a grid has: what Home Assistant
     * says is written back over the boxes unless a finger is on them, a keyed change
     * has not gone yet, or the focus is somewhere inside the week.
     */
    function busy() {
      return painting !== null || pending !== null ||
        week.contains(document.activeElement);
    }

    /** One box, touched only when it is actually changing. */
    function mark(row, slot, on) {
      if (ticked[row][slot] === on) return;
      ticked[row][slot] = on;
      cells[row][slot].classList.toggle("on", on);
      cells[row][slot].setAttribute("aria-pressed", String(on));
    }

    /**
     * Say what an empty grid means, because it looks like the opposite of what it is.
     *
     * No half hour marked is no restriction (D27), not a week with no viewing in it,
     * and a grid of empty boxes reads as the second one to anybody who has not been
     * told otherwise.
     */
    function tell() {
      open.hidden = !ticked.every((line) => line.every((on) => !on));
    }

    /** Put what the television is enforcing on the grid, box by box. */
    function draw(tv) {
      const given = (tv && tv.hours) || {};
      WEEK.forEach((day, row) => {
        const marked = new Set(given[day[0]] || []);
        for (let slot = 0; slot < SLOTS; slot += 1) {
          mark(row, slot, marked.has(clock(slot)));
        }
      });
      tell();
    }

    /** A whole day, set or cleared from its name, which is the row a parent means. */
    function whole(row) {
      if (sealed()) return;
      const full = ticked[row].every(Boolean);
      for (let slot = 0; slot < SLOTS; slot += 1) mark(row, slot, !full);
      lately = !full;
      tell();
      commit();
    }

    /**
     * Draw the run between where the gesture started and where it has got to.
     *
     * A rectangle rather than a trail of everything the pointer has touched, because a
     * finger overshoots and a trail cannot be taken back without lifting and starting
     * the whole run again. Everything outside it goes back to how the week stood when
     * the gesture began, so dragging back shrinks the run rather than adding to it —
     * and a drag down the days sets the same evening on all of them at once.
     */
    function stretch(row, slot) {
      const first = Math.min(painting.row, row);
      const last = Math.max(painting.row, row);
      const opens = Math.min(painting.slot, slot);
      const shuts = Math.max(painting.slot, slot);
      for (let one = 0; one < WEEK.length; one += 1) {
        for (let each = 0; each < SLOTS; each += 1) {
          const inside = one >= first && one <= last &&
            each >= opens && each <= shuts;
          mark(one, each, inside ? painting.on : painting.was[one][each]);
        }
      }
      tell();
    }

    /** The box under a point, or nothing where the pointer has left the week. */
    function under(node) {
      const cell = node && node.closest ? node.closest(".cell") : null;
      return cell && cell.atSlot !== undefined ? cell : null;
    }

    /**
     * Which box the keyboard reaches, and the only one it reaches by tabbing.
     *
     * Three hundred and thirty-six tab stops is not access to a grid, it is a
     * punishment for opening one: reaching Friday evening would be four hundred
     * presses. One way in, and the arrows from there.
     */
    function rove(cell) {
      keyed.tabIndex = -1;
      keyed = cell;
      cell.tabIndex = 0;
    }

    /** Move the keyboard onto one box, painting it on the way when shift is down. */
    function land(row, slot, paint) {
      if (paint && !sealed()) {
        mark(row, slot, lately);
        tell();
        soon();
      }
      rove(cells[row][slot]);
      cells[row][slot].focus();
    }

    /**
     * Gather keyed changes into one write.
     *
     * A held arrow with shift down is a run being drawn a box at a time, and it is the
     * same single decision a drag is. Waiting for the keys to stop is what stands in
     * for a finger being lifted.
     */
    function soon() {
      clearTimeout(pending);
      pending = setTimeout(() => {
        pending = null;
        commit();
      }, KEYED_MS);
    }

    /** Send the week, whole and once, and then show what came back for it. */
    async function commit() {
      if (pending !== null) {
        clearTimeout(pending);
        pending = null;
      }
      const days = {};
      let full = true;
      WEEK.forEach((day, row) => {
        const marked = [];
        for (let slot = 0; slot < SLOTS; slot += 1) {
          if (ticked[row][slot]) marked.push(clock(slot));
          else full = false;
        }
        days[day[0]] = marked;
      });
      // Every day every time, marked and unmarked alike: an unmarked half hour has no
      // other way of being said, so a day left out would be a day with no viewing.
      await act({id: view.id, action: "hours", days: days}, note, full
        ? "Saved. A week with nothing refused is no restriction, so it clears."
        : "Hours saved");
      // `act` has read the state back, so this is what the television has rather than
      // what was drawn at it. A refusal snaps the week back instead of leaving a grid
      // nobody is enforcing on the screen.
      if (!painting) draw(view.tv);
    }

    week.addEventListener("pointerdown", (event) => {
      const cell = under(event.target);
      if (sealed() || !cell) return;
      // The gesture takes the pointer with it: on a touchscreen every event after this
      // one is delivered here whatever the finger has moved over, which is why the box
      // under it is looked up by where it is rather than by what it hit.
      event.preventDefault();
      if (week.setPointerCapture) week.setPointerCapture(event.pointerId);
      painting = {
        row: cell.atDay,
        slot: cell.atSlot,
        // Starting on a marked box clears, the way a spreadsheet does it: the box
        // pressed says which of the two things the whole gesture is.
        on: !ticked[cell.atDay][cell.atSlot],
        was: ticked.map((line) => line.slice()),
      };
      lately = painting.on;
      // Where the keyboard picks up next, without taking the focus off whatever has
      // it: a press is a place to draw, not a request to be moved.
      rove(cell);
      stretch(cell.atDay, cell.atSlot);
    });

    week.addEventListener("pointermove", (event) => {
      if (!painting) return;
      const cell = under(document.elementFromPoint(event.clientX, event.clientY));
      if (cell) stretch(cell.atDay, cell.atSlot);
    });

    week.addEventListener("pointerup", () => {
      if (!painting) return;
      painting = null;
      commit();
    });

    week.addEventListener("pointercancel", () => {
      if (!painting) return;
      const was = painting.was;
      painting = null;
      // The browser took the gesture away rather than the parent finishing it, so
      // nothing was decided here and nothing is written.
      for (let row = 0; row < WEEK.length; row += 1) {
        for (let slot = 0; slot < SLOTS; slot += 1) mark(row, slot, was[row][slot]);
      }
      tell();
    });

    week.addEventListener("keydown", (event) => {
      const cell = under(event.target);
      if (!cell) return;
      const move = MOVES[event.key];
      if (move) {
        event.preventDefault();
        land(within(cell.atDay + move[0], WEEK.length),
          within(cell.atSlot + move[1], SLOTS), event.shiftKey);
      } else if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        land(cell.atDay, event.key === "Home" ? 0 : SLOTS - 1, event.shiftKey);
      } else if (event.key === " " || event.key === "Enter") {
        // Answered here rather than through the button's own click, so that one box
        // is never marked twice over by a press the pointer has already dealt with.
        event.preventDefault();
        if (sealed()) return;
        lately = !ticked[cell.atDay][cell.atSlot];
        mark(cell.atDay, cell.atSlot, lately);
        tell();
        soon();
      }
    });

    view.updates.push((tv) => {
      const followed = tv.following_schedule;
      const off = Boolean(followed);
      week.classList.toggle("off", off);
      labels.forEach((label) => { label.disabled = off; });
      cells.forEach((line) => line.forEach((cell) => { cell.disabled = off; }));
      lead.hidden = off;
      warning.hidden = !off;
      if (off) {
        warning.textContent = "These hours are taken from " + followed + ", which " +
          "the integration re-reads whenever it is edited, so they have to be " +
          "changed there. Anything drawn here would be undone by its next edit.";
      }
      if (!busy()) draw(tv);
    });
  }

  function beat() {
    // A panel in a pocket is a panel nobody is reading, and a phone's battery is worth
    // more than a figure that is five seconds fresher than the moment it is looked at.
    if (!document.hidden) poll();
  }

  window.addEventListener("hashchange", () => {
    route();
    // A destination is a fresh page to whoever asked for it, and being dropped halfway
    // down one is not that. Only on the way between two of them: on the first read the
    // browser is still restoring where the page was left, and this would undo it.
    if (window.scrollTo) window.scrollTo(0, 0);
  });
  document.addEventListener("visibilitychange", beat);
  setInterval(beat, POLL_MS);
  route();
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
