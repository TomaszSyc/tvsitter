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

import html
import json

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
  --cell: 15px;
  --tall: 30px;
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
/* Two banners that hand a decision back rather than only reporting one: the
   sentence, the button, and underneath both the promise of what pressing it does not
   do. One offers the hours back off a helper; the other throws away a change the
   television never woke up to take. */
.banner.offer,
.banner.waiting {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem 1rem;
}
.banner.offer .said, .banner.waiting .said { flex: 1 1 15rem; }
.banner.waiting button { flex: none; }
.banner.offer button, .banner.offer button:hover {
  background: var(--accent);
  color: var(--backdrop);
  flex: none;
}
/* In the page's own quiet voice rather than the warning's. The reassurance is the half
   a parent has to believe, and one in the colour of an alarm is not believed. */
.banner .aside {
  color: var(--muted);
  flex-basis: 100%;
  font-size: 0.85rem;
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
/* The colour the page warns in, on the one button that takes something away. */
.danger, .danger:hover { background: var(--warn); color: var(--backdrop); }
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
/* Written with the boxes rather than left to the platform: a select in its default
   dress is a light grey control on a dark page, and the one place a parent picks
   something from a list should not look as though it came from somewhere else. */
select {
  background: var(--backdrop);
  border: 1px solid var(--edge);
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  max-width: 100%;
  padding: 0.45rem 0.6rem;
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
/* A card opening with a row opens with a rule across it, which reads as a mistake —
   and one directly under a heading reads as the heading being underlined. */
.row:first-child, .card h2 + .row { border-top: 0; }
.row .name { flex: 1 1 8rem; min-width: 0; }
/* A label that gives the rest of the row its width back, where what follows it is a
   short box and a button rather than a number and a unit. */
.row .name.short { flex: 0 1 auto; }
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
/*
 * What one control has to say for itself, drawn under that control.
 *
 * A row rather than a line, because a refusal stays until somebody dismisses it and
 * the button that does that belongs beside the words rather than under them. Long
 * words break: Home Assistant's own refusals quote entity ids, and one of those is
 * wider than a phone.
 */
.note {
  align-items: flex-start;
  color: var(--accent);
  display: flex;
  gap: 0.5rem;
  margin-top: 0.3rem;
}
.note .words { min-width: 0; overflow-wrap: anywhere; }
.note button { flex: none; font-size: 0.8rem; padding: 0.2rem 0.7rem; }
/* A refusal is the one message nobody catches, so it is the one that stays — and one
   that stays is drawn as something still on the page rather than as a line of text
   that happens not to have gone. */
.note.bad {
  background: var(--backdrop);
  border-left: 3px solid var(--warn);
  border-radius: 10px;
  color: var(--warn);
  padding: 0.5rem 0.7rem;
}
/*
 * The week as one strip, not as seven forms.
 *
 * Seven rounded blocks, each holding a small box and the word "min", was mostly empty
 * space: the card said its unit seven times and its answer once, and the one day
 * anybody had actually set looked exactly like the six they had not. It is one rule
 * shown seven times, so it is drawn the way the hours below it are — a single inset
 * panel, one column per day, the day named in the same muted three letters. The unit
 * is said once above the seven of them, and what a day is worth is the colour of its
 * number: its own allowance, or nought, or nothing.
 */
.allowances {
  background: var(--backdrop);
  border-radius: 16px;
  display: grid;
  gap: 1px;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  margin-top: 0.7rem;
  padding: 0.5rem;
}
.allowance { min-width: 0; text-align: center; }
.allowance label {
  color: var(--muted);
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}
/* The box takes its column's width and gives up the spinner for it: three digits and
   a pair of arrows do not both fit in a seventh of a phone, and the arrows are the
   half nobody came here to press. Lighter than the strip it sits in, the way a half
   hour of the grid is lighter than the grid. */
.allowance input {
  appearance: textfield;
  background: var(--surface);
  border: 0;
  border-radius: 10px;
  display: block;
  font-variant-numeric: tabular-nums;
  margin: 0 auto;
  /* Three digits wide and no wider. A box that took a seventh of a desktop would put
     one number in the middle of a slab, which is the emptiness this card had. */
  max-width: 4.2rem;
  min-width: 0;
  padding: 0.35rem 0.15rem;
  text-align: center;
  width: 100%;
}
.allowance input::-webkit-inner-spin-button { appearance: none; margin: 0; }
.allowance input::placeholder { color: var(--muted); opacity: 1; }
/* A day somebody set is the thing on this card worth seeing, so it is the only thing
   on it with a colour. Nought takes viewing away, and this page takes things away in
   the warning colour. */
.allowance input.set { color: var(--accent); font-weight: 600; }
.allowance input.none { color: var(--warn); font-weight: 600; }
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
  grid-column: span 4;
  line-height: var(--head);
}
.week {
  grid-auto-rows: var(--tall);
  touch-action: none;
  user-select: none;
}
/* Nothing to draw while a schedule helper owns the hours, so the finger has it back —
   and the week reads as a picture of the hours rather than as boxes that ignored it. */
.week.off { opacity: 0.75; touch-action: pan-x; }
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
/* A run of marked half hours has to read as one span of time rather than as a row of
   dots. The gap between boxes stays, because a finger drawing across them needs to see
   where one ends; a marked box paints over the gap to its right instead, so neighbours
   join into a bar and a single half hour is still a box. */
.cell.on, .cell.on:hover { box-shadow: 1px 0 0 0 var(--accent); }
/* Where the hour named above the grid falls, carried down through the week. Without it
   forty-eight identical boxes are a smear nobody can find half past six in — which is
   the whole complaint against a grid that shows exactly the right thing. */
.cell.mark { border-left: 1px solid rgba(143, 163, 179, 0.45); }
.cell.on.mark { border-left-color: rgba(11, 16, 23, 0.35); }
.tick { border-left: 1px solid rgba(143, 163, 179, 0.25); padding-left: 0.25rem; }
/* Midnight and noon, which are the two the eye actually navigates by. */
.cell.noon { border-left-color: rgba(143, 163, 179, 0.85); }
.cell.on.noon { border-left-color: rgba(11, 16, 23, 0.6); }
/* What is being drawn, said over the grid while it is drawn. A rectangle of boxes is
   something to count; the hours it means are the decision. Fixed to the window so it
   can sit above a finger anywhere on the week, and never under the pointer itself. */
.range {
  background: var(--raised);
  border: 1px solid var(--edge);
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
  color: var(--muted);
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
  padding: 0.3rem 0.6rem;
  pointer-events: none;
  position: fixed;
  transform: translate(-50%, -150%);
  white-space: nowrap;
  z-index: 20;
}
.range b { color: var(--accent); font-weight: 600; }
.range.clearing b { color: var(--warn); }
/* Under the pointer instead of over it, for a gesture near the top of the window,
   where above it would be off the screen altogether. */
.range.below { transform: translate(-50%, 60%); }
/* Drawn here, not yet on the television. Warning-coloured because the grid is saying
   something other than what the set is enforcing, which is the one state this card was
   built to never show silently. */
.held {
  color: var(--warn);
  font-size: 0.85rem;
  margin: 0.35rem 0 0;
}
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
<p class="lead" id="lead">Everything here comes from Home Assistant, which is the
only thing that talks to the televisions.</p>
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

  /**
   * What to say, in whatever language Home Assistant is set to.
   *
   * The English is the key as well as the fallback, so the page below still reads as
   * the sentences it puts on the screen, and a language that has no word for one of
   * them says it in English rather than saying nothing at all.
   *
   * Values go in afterwards, never by adding strings end to end: the order the pieces
   * of a sentence go in is not the same in every language, and "Read from " + name is
   * two fragments that can only be put back together in English.
   */
  function phrase(words, values) {
    let said = (typeof SAID === "object" && SAID && SAID[words]) || words;
    if (values) {
      Object.keys(values).forEach((name) => {
        said = said.split("{" + name + "}").join(String(values[name]));
      });
    }
    return said;
  }

  const MINUTES_PER_HOUR = 60;
  const POLL_MS = 5000;

  /*
   * How long a confirmation stands: the time it takes to notice one and read it.
   *
   * Not a round number, because nothing about reading a sentence is round. The fixed
   * part is finding a line that has just appeared and being sure of it once it has
   * been read; the rest is the sentence itself at two hundred words a minute, which
   * is unhurried silent reading — what somebody standing in a doorway holding a
   * phone actually does. So "Saved" is gone in one and seven tenths of a second, the
   * longest of the written confirmations runs to fourteen words and stands for five
   * and six tenths, and one that has to add that the set is asleep stands longer
   * again, because it is longer to read.
   *
   * Three seconds flat for every one of them was the fault: "Saved. An empty list is
   * no restriction: every app is allowed again." cannot be read in three seconds by
   * somebody who was looking at the television when it appeared.
   */
  const NOTICE_MS = 1400;
  const PER_WORD_MS = 300;

  /** How long a change the integration answers for itself is given to land. */
  const SETTLE_MS = 700;

  /** So the shortest thing watched is still a bar rather than nothing at all. */
  const SHORTEST_BAR = 3;

  // The grid is half-hourly, the same half hours the rules are written in. Finer would
  // be ninety-six boxes to hit on a phone; coarser could not say the half past four a
  // school day actually starts at.
  const SLOT_MINUTES = 30;
  const SLOTS = (24 * MINUTES_PER_HOUR) / SLOT_MINUTES;

  // How often the hour is named above the grid, and how often the line under that
  // name is carried down through the week. All forty-eight names would be a smear;
  // every third hour left the two a parent actually looks for — noon and six — with no
  // name of their own, so it is every second one.
  const TICK = 4;

  /** How long a keyed change waits for the next, so a held key is still one write. */
  const KEYED_MS = 400;

  // Room kept between the readout of what is being drawn and the edge of the window,
  // and how near the top of it the readout goes under the pointer rather than over.
  const PADDING = 8;
  const LOW = 64;

  // How long the week a parent drew stays on the grid while the television has yet to
  // report it back. Long enough to cover the write, the broker and a set that is
  // thinking about it; short enough that a television which read the rule differently
  // from this panel does not leave a picture of hours nobody is enforcing on the
  // screen. A set that is asleep is not on this clock at all — it is waited for.
  const AGREE_MS = 12000;

  // How long a parent PIN is, which is `ParentPin.LENGTH` on the television and
  // `parent_pin.LENGTH` in the integration. Checked here as well so that four digits
  // are asked for before anything is sent, rather than after Home Assistant has
  // refused them — its refusal quotes what it refused, and that is a PIN in a log.
  const PIN_LENGTH = 4;

  // The arrows, as a day and a half hour to move by. Clamped rather than wrapped: an
  // arrow that runs off Monday morning into Sunday night is a box nobody aimed at.
  const MOVES = {
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
  };

  // The two actions that send the television nothing at all: they change what Home
  // Assistant does about a set, not what the set is enforcing. Neither of them can be
  // waiting for a television to wake up, however much else is.
  const UNSENT = ["stop_following", "forget_pending"];

  // The destinations, in the rail's order, keyed the way the address bar spells them.
  // The first is the start destination and the answer to anything unrecognised.
  const WHERE = ["now", "today", "rules", "apps"];

  // The rules a television carries, in the words this page calls them by. A key it
  // has never heard of is said exactly as it arrived: an ugly name for a change that
  // is waiting beats a wrong one, and only the set knows what it sends.
  const RULES = {
    daily_limit_s: phrase("the daily limit"),
    warn_before_s: phrase("the warning before the end"),
    block_settings: phrase("the Settings block"),
    app_limits_s: phrase("the app budgets"),
    days: phrase("the week's allowances"),
    windows: phrase("the hours"),
    apps_allowed: phrase("the allowed apps"),
  };

  // The week in the order a week is read, keyed the way the state keys it.
  const WEEK = [
    ["mon", phrase("Monday"), phrase("Mon")],
    ["tue", phrase("Tuesday"), phrase("Tue")],
    ["wed", phrase("Wednesday"), phrase("Wed")],
    ["thu", phrase("Thursday"), phrase("Thu")],
    ["fri", phrase("Friday"), phrase("Fri")],
    ["sat", phrase("Saturday"), phrase("Sat")],
    ["sun", phrase("Sunday"), phrase("Sun")],
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

  // What to tell when the notification setup has been read. One list rather than one
  // per television: the answer covers every set at once and is asked for once.
  const wanting = [];
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

  /**
   * Where one control says what came of it, built to sit under that control.
   *
   * One of these per thing that can be changed rather than one for the page: a
   * confirmation in a corner is a confirmation about nothing in particular, and a
   * refusal in one is a refusal the next success anywhere else wipes out before
   * anybody has read it.
   */
  function notice() {
    const node = el("div", "note");
    // Announced rather than only shown. "Saving\u2026" puts the region on the page
    // before the answer replaces it, which is what makes the answer carry: a live
    // region that appears and speaks in the same breath is one nothing reads out.
    node.setAttribute("role", "status");
    node.words = el("p", "words");
    node.drop = el("button", null, phrase("Dismiss"));
    node.drop.type = "button";
    node.drop.addEventListener("click", () => { clear(node); });
    node.appendChild(node.words);
    clear(node);
    return node;
  }

  /** Nothing to say, and no room held open while there is nothing. */
  function clear(note) {
    hold(note, "");
    note.hidden = true;
  }

  function hold(note, words) {
    clearTimeout(note.timer);
    note.timer = null;
    note.words.textContent = words;
    note.hidden = false;
    // Taken out rather than hidden. A note with nothing to dismiss should have no
    // button in it at all: what the note says is then all the note contains.
    note.drop.remove();
    note.classList.remove("bad");
  }

  /**
   * Say what came of it, and decide there and then whether it goes on its own.
   *
   * A confirmation goes: it is read at a glance and after that it is in the way. A
   * refusal never does. It is the one message that matters, it is the one a parent
   * watching the television rather than the phone misses, and there is no way to ask
   * for it a second time \u2014 so it stands until the next change on this control
   * goes through, or until it is dismissed by hand.
   */
  function say(note, words, bad) {
    hold(note, words);
    if (bad) {
      note.classList.add("bad");
      note.appendChild(note.drop);
      return;
    }
    note.timer = setTimeout(() => { clear(note); }, dwell(words));
  }

  /** How long that particular sentence takes to notice and to read. */
  function dwell(words) {
    const many = String(words).split(/\\s+/).filter(Boolean).length;
    return NOTICE_MS + PER_WORD_MS * many;
  }

  /**
   * Ask for a change, then read the state back rather than assume it took.
   *
   * The rules sensor's revision is what the television says it is enforcing, so the
   * only honest confirmation is the next answer from the server, not this one.
   */
  async function act(body, note, done) {
    hold(note, phrase("Saving\\u2026"));
    let answer = null;
    try {
      const back = await fetch("api/do", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
      });
      answer = await back.json();
    } catch (failure) {
      answer = {ok: false, error: phrase("The panel could not reach the add-on.")};
    }
    // Read the state back before saying anything about it. Whether a change is in
    // force or waiting for a sleeping television is the state's answer and not this
    // one's, and a confirmation written before the read would be a guess.
    await poll();
    if (answer && answer.ok) say(note, landed(body, done), false);
    else say(note, (answer && answer.error) ||
      phrase("Home Assistant refused it."), true);
    // Handed back as well as said, because one caller has to tell the two apart: a
    // week drawn on the grid stays there when it was taken and snaps back when it was
    // not, and "was it taken" is not a question a sentence can be asked.
    return answer;
  }

  /**
   * What a change that was taken actually amounts to, now the state has been read.
   *
   * A rule changed while the set is asleep is accepted and held rather than refused,
   * and "Saved" on its own would leave a parent believing a rule is running that is
   * not \u2014 which is worse than the refusal this replaced, because a refusal at
   * least leaves them knowing where they stand.
   */
  function landed(body, done) {
    const view = views.get(body.id);
    const took = done || phrase("Saved");
    if (UNSENT.indexOf(body.action) >= 0) return took;
    if (!view || !view.tv || !view.tv.pending_rules) return took;
    return phrase("{took} The television is asleep, so it is waiting rather than " +
      "in force, and goes the moment the set is back.", {took: ended(took)});
  }

  /** End a sentence that may have ended already, so two can be joined. */
  function ended(words) {
    return /[.!?]$/.test(words) ? words : words + ".";
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
      warn(phrase("Home Assistant did not answer. This is what was last read."));
      return;
    }
    warn(state.error);
    paint(state.televisions || [], state.error);
  }

  function paint(list, error) {
    nothing.hidden = list.length > 0 || Boolean(error);
    if (!list.length) {
      nothing.textContent = phrase("No televisions yet. The panel reads them from " +
        "the TV Sitter integration, so add that first \\u2014 this page is a " +
        "second way to see what it already knows, not a way round it.");
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
   * A card on one destination.
   *
   * A heading that only says the rail's word back is left off, because it carries
   * nothing. A heading that names which of a destination's parts this one is stays:
   * where a destination is made of several, naming all of them is what makes them read
   * as parts rather than as things that happen to be stacked.
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
    const playing = figure(figures, phrase("Playing"));
    const left = figure(figures, phrase("Left today"));
    const lock = el("button", "lock");
    lock.type = "button";
    const note = notice();
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
      tell(screen, phrase(tv.screen ? "Screen on" : "Screen off"),
        tv.screen ? "yes" : "");
      tell(reporting, phrase(tv.reporting ? "Reporting" : "Not reporting"),
        tv.reporting ? "yes" : "bad");
      tell(pin, phrase(tv.pin_set ? "PIN set" : "No PIN"),
        tv.pin_set ? "yes" : "bad");
      playing.value.textContent = tv.playing || phrase("Nothing");
      spend(left, tv.remaining_today);
      lock.textContent = phrase(tv.locked ? "Lift the lock" : "Lock the television");
      lock.classList.toggle("up", Boolean(tv.locked));
      foot.textContent =
        (heard(tv.last_reported) + revision(tv.rules_revision)).trim();
    });

    pinCard(view);
    askingCard(view);
  }

  /**
   * The parent PIN, set and taken away under the pill that reports it (#133).
   *
   * Nothing is ever read back into the box. The entity holds no PIN to read — a hash
   * is what is kept — so a box arriving with something in it would be this page
   * inventing one. What was typed leaves the box the moment it is sent, and it is in
   * no message, no refusal and nothing this page hands to anybody else: what Home
   * Assistant says about a PIN it would not take is a sentence quoting the PIN, which
   * is why the four digits are asked for here before anything goes.
   */
  /**
   * Which phone is asked when the child asks, which was YAML until now.
   *
   * The automation behind this is the one thing left in the product that a parent had
   * to set up by hand: copy a blueprint into the configuration directory, reload,
   * create an automation from it, choose the targets. The add-on has been able to do
   * all of it since it could write blueprints — from everywhere except a page (#104).
   *
   * Two phones rather than one because a request nobody answers is a child sitting in
   * front of a locked television, and one parent is out more often than both are.
   */
  function askingCard(view) {
    const box = card(view, "now", phrase("Asking for more time"));
    const lead = el("p", "hint",
      phrase("When the child asks for more time, Home Assistant sends the question " +
        "to a phone with buttons to answer it."));
    const nothing = el("p", "empty");
    const row = el("div", "row");
    const first = picker(row, phrase("Ask"));
    const second = picker(row, phrase("And also"));
    const save = el("button", null, phrase("Save"));
    save.type = "button";
    const note = notice();
    row.appendChild(save);
    box.append(lead, nothing, row, note);

    /** Fill one picker with the phones, leaving whatever is chosen chosen. */
    function offer(into, phones, chosen, none) {
      into.textContent = "";
      const blank = el("option", null, none);
      blank.value = "";
      into.appendChild(blank);
      phones.forEach((phone) => {
        const one = el("option", null, called(phone));
        one.value = phone;
        into.appendChild(one);
      });
      into.value = chosen && phones.indexOf(chosen) >= 0 ? chosen : "";
    }

    /** A notify service, as the phone somebody would call it. */
    function called(service) {
      const bare = service.replace("notify.mobile_app_", "").split("_").join(" ");
      return bare ? bare[0].toUpperCase() + bare.slice(1) : service;
    }

    save.addEventListener("click", async () => {
      hold(note, phrase("Saving\u2026"));
      let answer = null;
      try {
        const back = await fetch("api/setup", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            id: view.id,
            notify: first.value,
            also_notify: second.value,
          }),
        });
        answer = await back.json();
      } catch (failure) {
        answer = {ok: false, error: phrase("The panel could not reach the add-on.")};
      }
      // Read back before saying anything, the way every other change here does: what
      // was made is Home Assistant's answer rather than this one's guess.
      await askSetup();
      if (answer && answer.ok) say(note, phrase("Saved"), false);
      else {
        say(note, (answer && answer.error) ||
          phrase("Home Assistant refused it."), true);
      }
    });

    wanting.push((said) => {
      const mine = ((said && said.televisions) || [])
        .filter((one) => one.id === view.id)[0];
      const phones = (said && said.notify) || [];
      const usable = Boolean(mine && mine.ready) && phones.length > 0;
      row.hidden = !usable;
      lead.hidden = !usable;
      nothing.hidden = usable;
      if (!usable) {
        nothing.textContent = (said && said.error) || phrase(mine && !mine.ready
          ? "This television has no time request to answer. It was set up by an " +
            "older version of the integration, which had none."
          : "No phone with the Home Assistant app on it was found, and only a phone " +
            "can carry buttons to answer with.");
        return;
      }
      offer(first, phones, mine.notify, phrase("Nobody"));
      offer(second, phones, mine.also_notify, phrase("Nobody else"));
    });
  }

  /** One labelled picker in a row, built the way the numbered boxes beside it are. */
  function picker(row, label) {
    const wrap = el("label", "name short");
    const chosen = el("select");
    wrap.append(el("span", null, label), chosen);
    row.appendChild(wrap);
    return chosen;
  }

  function pinCard(view) {
    const box = card(view, "now", phrase("The parent PIN"));
    box.appendChild(el("p", "hint",
      phrase("Home Assistant hashes it and sends the hash, so the television is " +
        "never told the digits typed here.")));
    const note = notice();
    const row = line(box);
    seq += 1;
    const input = el("input");
    input.id = "k" + seq;
    input.type = "password";
    input.inputMode = "numeric";
    // Off rather than `new-password`, which is an invitation to a password manager to
    // keep it. The card promises the digits are not written down; offering them to
    // whatever is listening for a new password would be the page breaking that itself.
    input.autocomplete = "off";
    input.maxLength = PIN_LENGTH;
    input.placeholder = "\\u2022\\u2022\\u2022\\u2022";
    const tag = el("label", "name short", phrase("New PIN"));
    tag.htmlFor = input.id;
    const set = el("button", null, phrase("Set the PIN"));
    set.type = "button";
    row.append(tag, input, set);

    // Removing one is two taps rather than one, because it is the tap that cannot be
    // undone: the PIN itself is not kept anywhere, so a stray one is not a setting to
    // put back but a PIN to think of again and type into every television.
    const drop = line(box);
    const ask = el("button", null, phrase("Remove the PIN"));
    const yes = el("button", "danger", phrase("Yes, remove it"));
    const no = el("button", null, phrase("Keep it"));
    const why = el("p", "hint",
      phrase("Without a PIN a lock cannot be lifted at the television at all, only " +
        "from Home Assistant."));
    [ask, yes, no].forEach((one) => { one.type = "button"; });
    // No label on this row: the buttons say what they do, and a word in front of them
    // would only repeat the heading of the card they are in.
    drop.append(ask, yes, no, why);
    box.appendChild(note);

    /** Whether the second tap is the one being waited for. */
    function arm(on) {
      ask.hidden = on;
      yes.hidden = !on;
      no.hidden = !on;
      why.hidden = !on;
    }
    arm(false);

    set.addEventListener("click", () => {
      const typed = input.value.trim();
      // Out of the box before anything is sent with it. A PIN left sitting in a field
      // is a PIN whoever picks the phone up next can read out of it, and a refusal
      // below is a refusal the parent reads rather than one that hands it back.
      input.value = "";
      if (typed.length !== PIN_LENGTH || !digits(typed)) {
        say(note, phrase("A PIN is four digits."), true);
        return;
      }
      act({id: view.id, action: "set_pin", pin: typed}, note, phrase("PIN set"));
    });

    ask.addEventListener("click", () => { arm(true); });
    no.addEventListener("click", () => { arm(false); });
    yes.addEventListener("click", () => {
      arm(false);
      act({id: view.id, action: "clear_pin"}, note, phrase("PIN removed"));
    });

    view.updates.push((tv) => {
      // Nothing to take away while there is none: the pill above has already said so,
      // and a button that removes nothing is a button that answers nothing.
      drop.hidden = !tv.pin_set;
      if (!tv.pin_set) arm(false);
    });
  }

  /** ASCII digits and nothing else, which is what a television remote can enter. */
  function digits(said) {
    return /^[0-9]+$/.test(said);
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
    if (!when) return phrase("Never reported.") + " ";
    const at = new Date(when);
    if (isNaN(at.getTime())) return phrase("Last reported {when}.", {when: when}) + " ";
    const clock = at.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    return phrase("Last reported at {clock}.", {clock: clock}) + " ";
  }

  /** The one number that answers "has my change actually arrived". */
  function revision(count) {
    return unset(count) ? "" : phrase("Rules revision {count}.", {count: count});
  }

  /** The day as it stands: three figures, then where the time actually went. */
  function todayPane(view) {
    const box = card(view, "today");
    const figures = el("div", "figures");
    const used = figure(figures, phrase("Watched"));
    const limit = figure(figures, phrase("Limit today"));
    const left = figure(figures, phrase("Left"));
    const aside = el("p", "foot");
    const split = el("div", "split");
    // Two lists of the same shape, so each says which stretch of time it is: "By app"
    // over one of them and nothing over the other is a week a parent reads as a day.
    const seven = el("div", "split");
    const naming = el("p", "hint");
    box.append(figures, aside, el("h3", null, phrase("Today, by app")), split,
      el("h3", null, phrase("The last seven days, by app")), naming, seven);

    view.updates.push((tv) => {
      used.value.textContent = length(tv.used_today);
      limit.value.textContent = length(tv.limit_today);
      spend(left, tv.remaining_today);
      aside.textContent = besides(tv);
      bars(split, tv.apps, phrase("Nothing watched yet today."));
      bars(seven, tv.week_by_app, phrase("Nothing recorded yet. These seven days " +
        "come from Home Assistant's own history rather than from the television, and " +
        "it has nothing for this set so far \\u2014 which is not the same as a week " +
        "with nothing watched in it."));
      naming.hidden = !unnamed(tv.week_by_app);
      naming.textContent = phrase("Where Home Assistant has no name for an app any " +
        "more, its package id stands in.");
    });
  }

  /**
   * Whether any of the seven days is named by its package id rather than by a name.
   *
   * The recorder keeps a figure per app for longer than the television keeps the app,
   * so a week can carry a row the daily list has no label for. It is said once, above
   * the list, rather than guessed at per row — and never made up, because a package
   * id is what the set actually called it.
   */
  function unnamed(listed) {
    return (listed || []).some((app) => !app.name || app.name === app.package);
  }

  function besides(tv) {
    const said = [];
    // A bonus of nothing is the ordinary day, and saying so every day is noise.
    if (!unset(tv.bonus_today) && tv.bonus_today > 0) {
      said.push(phrase("Bonus today {much}.", {much: length(tv.bonus_today)}));
    }
    if (!unset(tv.used_yesterday)) {
      said.push(phrase("Yesterday {much}.", {much: length(tv.used_yesterday)}));
    }
    return said.join(" ");
  }

  /**
   * A stretch of time split by app, longest first, the way the television draws it.
   *
   * Redrawn whole on every poll because there is nothing here to type into. The bar is
   * proportional to the longest thing watched rather than to the limit: the question
   * this answers is what he is watching, and against a limit every interesting row is
   * short.
   *
   * What an empty list means is handed in, because it is not the same thing on the two
   * lists drawn this way: a day with nothing on it is a day nobody watched, and seven
   * days with nothing on them is a recorder that has not been running that long.
   */
  function bars(into, listed, empty) {
    const watched = (listed || [])
      .filter((app) => app.minutes > 0)
      .sort((one, other) => other.minutes - one.minutes);
    if (!watched.length) {
      into.replaceChildren(el("p", "empty", empty));
      return;
    }
    const longest = watched[0].minutes;
    into.replaceChildren(...watched.map((app) => bar(app, longest)));
  }

  function bar(app, longest) {
    const node = el("div", "app");
    const much = el("p", "much", length(app.minutes));
    if (!unset(app.limit)) {
      much.appendChild(el("em", null,
        " " + phrase("of {much}", {much: length(app.limit)})));
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
   * Everything that can be changed, in three cards that read in an order: what holds
   * every day, what a particular day overrides it with, and — as the grid it is — the
   * hours of the week viewing is allowed in whatever the limits say.
   *
   * All three are named, this one included. Two named cards under a third with no name
   * are not three parts of one screen, they are a screen and two things stacked under
   * it; and "Every day" is not the rail's word repeated back but the answer to which of
   * the three a rule belongs in.
   */
  function rulesPane(view) {
    heldBack(view);
    const box = card(view, "rules", phrase("Every day"));
    const daily = number(view, box, phrase("Daily limit"), "daily_limit",
      (tv) => tv.daily_limit);
    wipe(view, daily);
    number(view, box, phrase("Sleep timer"), "sleep_timer", (tv) => tv.sleep_timer,
      phrase("How long from now until the television puts itself to bed."));
    number(view, box, phrase("Warn before the end"), "warn_before",
      (tv) => tv.warn_before,
      phrase("One warning, this long before the allowance runs out."));
    switched(view, box, phrase("Block the Settings app"), "block_settings",
      (tv) => tv.block_settings,
      phrase("So the rules cannot be turned off from the television itself."));

    const week = card(view, "rules", phrase("The week"));
    const lead = el("p", "hint");
    const days = el("div", "allowances");
    // One note for the card. Seven of them were seven places a refusal could turn up
    // and seven blank lines holding the room open for it while none had.
    const note = notice();
    week.append(lead, days, note);
    WEEK.forEach((day) => weekLine(view, days, day[0], day[1], day[2], note));
    view.updates.push((tv) => { lead.textContent = shared(tv.daily_limit); });

    hoursCard(view);
  }

  /**
   * The change that has been taken but has not reached the television.
   *
   * A rule changed while the set is asleep is accepted and held rather than refused,
   * and a page that drew it as done would be worse than one that refused it: a
   * refusal leaves a parent knowing the rule is not running, and a silent hold leaves
   * them certain it is.
   *
   * Above the three cards rather than beside one control, because what is waiting may
   * be several rules at once and because it changes how everything below is read \u2014
   * the numbers and the grid are what the television is still enforcing, not what is
   * coming. Whoever is looking at the rules is looking at this first.
   *
   * The note is outside the banner and stays behind it: throwing a change away is the
   * one press here that makes the banner vanish, and a confirmation inside something
   * that disappears is a confirmation nobody reads.
   */
  function heldBack(view) {
    const holder = el("div");
    const box = el("div", "banner waiting");
    const said = el("p", "said");
    const forget = el("button", "danger", phrase("Throw the change away"));
    forget.type = "button";
    const aside = el("p", "aside",
      phrase("For a television that is not coming back. What goes is only what has " +
        "not reached it: the set keeps enforcing exactly what it is enforcing now."));
    const note = notice();
    box.append(said, forget, aside);
    holder.append(box, note);
    view.panes.get("rules").appendChild(holder);

    forget.addEventListener("click", () => {
      act({id: view.id, action: "forget_pending"}, note,
        phrase("Thrown away. The television keeps the rules it already had."));
    });

    view.updates.push((tv) => {
      const held = tv.pending_rules;
      box.hidden = !held;
      if (!held) return;
      said.textContent = phrase("Waiting for {name} rather than in force: {what}. " +
        "The set was asleep when it was changed, so everything below is what it is " +
        "still enforcing until it is back.", {name: tv.name, what: listed(held)});
    });
  }

  /** Which rules are waiting, listed the way somebody would say them aloud. */
  function listed(held) {
    const said = Object.keys(held || {}).map((key) => RULES[key] || key);
    if (said.length < 2) return said[0] || phrase("a change");
    return phrase("{most} and {last}",
      {most: said.slice(0, -1).join(", "), last: said[said.length - 1]});
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
    const note = notice();
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
        say(note, phrase("That wants a number of minutes."), true);
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
    const button = el("button", null, phrase("Remove"));
    button.type = "button";
    field.row.insertBefore(button, field.note);
    field.row.insertBefore(el("p", "hint",
      phrase("Removing it leaves the day uncapped. Zero is not the same thing: zero " +
        "minutes means no viewing today, which is a real thing a parent may mean.")),
        field.note);
    button.addEventListener("click", () => {
      act({id: view.id, action: "clear_limit"}, field.note, phrase("Limit removed"));
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
    const note = notice();
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

  /**
   * One day of the week, as one column of the strip the seven of them make.
   *
   * A column rather than a block of its own. Seven of these are a week; seven blocks
   * were seven forms, six of them empty, and the unit repeated over every one of them
   * was the loudest thing on a card whose answer is which day differs.
   */
  function weekLine(view, into, key, name, short, note) {
    const cell = el("div", "allowance");
    seq += 1;
    const input = el("input");
    input.id = "w" + seq;
    input.type = "number";
    input.min = "0";
    input.step = "1";
    input.inputMode = "numeric";
    input.placeholder = "\\u2014";
    // Three letters over the column, because seven Wednesdays do not fit across a
    // phone. Anything reading it out gets the whole day and the unit the seven boxes
    // no longer repeat, because "Wed" is not a day and a number is not minutes.
    input.setAttribute("aria-label",
      phrase("Minutes a day for {day}", {day: name}));
    const tag = el("label", null, short);
    tag.htmlFor = input.id;
    cell.append(tag, input);
    into.appendChild(cell);

    input.addEventListener("change", () => {
      const raw = input.value.trim();
      const value = Number(raw);
      if (raw !== "" && (!isFinite(value) || value < 0)) {
        input.value = shown((view.tv.week || {})[key]);
        say(note, phrase("{day} wants a number of minutes, or nothing.",
          {day: name}), true);
        return;
      }
      // Empty is not zero. Empty hands the day back to the daily limit; zero is a day
      // with no viewing on it.
      act({
        id: view.id,
        action: "schedule",
        day: key,
        minutes: raw === "" ? null : value,
      }, note, phrase("{day} saved", {day: name}));
    });

    view.updates.push((tv) => {
      const own = (tv.week || {})[key];
      if (document.activeElement !== input) input.value = shown(own);
      // Colour rather than a sentence apiece. Seven lines saying which day overrode
      // what were most of the card's height, six of them held the room open while
      // saying nothing, and none of them was as quick to read as one coloured number.
      input.classList.toggle("set", !unset(own) && own > 0);
      input.classList.toggle("none", own === 0);
    });
  }

  /**
   * What the seven boxes are, said once above them rather than seven times inside.
   *
   * The unit opens it, because that is the word the boxes no longer each carry. The
   * daily limit is named because a day left empty is a day that takes it, and nought
   * is spelled out because a nought in a box is the one number on this card that does
   * not read as what it means.
   */
  function shared(daily) {
    const takes = unset(daily)
      ? phrase("which is not set either")
      : length(daily);
    return phrase("Minutes a day. A day left empty takes the daily limit, {takes}; " +
      "a day set to zero is no viewing at all.", {takes: takes});
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
      return phrase("Only the ticked apps may be opened; every other one is refused. " +
        "A budget of zero blocks an app whether or not it is ticked.");
    }
    // The way it fails matters more than the way it reads. Nothing enforced is
    // something a parent can undo; a television nobody can open is one that has locked
    // them out of the thing they would fix it with.
    return phrase("The allow-list is empty, so every app is allowed. Untick one to " +
      "start a list: everything left ticked stays allowed and the rest are refused. " +
      "A budget of zero blocks an app on its own.");
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
    tag.append(box, el("span", null, phrase("Allowed")));
    const note = notice();
    node.append(who, budget, el("span", "unit", "min"), tag, note);

    budget.addEventListener("change", () => {
      const raw = budget.value.trim();
      const value = Number(raw);
      if (raw !== "" && (!isFinite(value) || value < 0)) {
        say(note, phrase("That wants a number of minutes, or nothing."), true);
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
          ? phrase("Saved")
          : phrase("Saved. An empty list is no restriction: every app is allowed " +
            "again."));
    });

    function fill(app) {
      const called = app.name || app.package;
      name.textContent = called;
      budget.setAttribute("aria-label",
        phrase("Minutes a day for {app}", {app: called}));
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
   * A house that started following one months ago got the dialog anyway: a grid it
   * could not touch under a warning naming somewhere else, which is worse than no grid
   * at all. So the warning carries the way out with it, and pressing it changes no
   * hour of the week — only where they are read from.
   *
   * Nothing leaves while a finger is down. A drag over ninety boxes is one decision,
   * and ninety writes would be ninety revisions of the rules for the television to
   * fetch — with the last of them landing well after the finger had lifted.
   */
  function hoursCard(view) {
    const box = card(view, "rules", phrase("The hours"));
    // Three things and no more: which helper has them, what that means, and the way
    // out. It used to be the first two in three lines of warning colour above a grid
    // nobody could touch, which is the complaint the grid was built to answer.
    const warning = el("div", "banner offer");
    const sealedBy = el("p", "said");
    const take = el("button", null, phrase("Keep these hours and edit here"));
    take.type = "button";
    const kept = el("p", "aside",
      phrase("The hours stay exactly as they are; only the following stops, and the " +
        "helper is left alone."));
    warning.append(sealedBy, take, kept);
    const lead = el("p", "hint",
      phrase("A green box is half an hour the television may be watched in. Drag " +
        "across the boxes to allow viewing in them, or out of a marked box to clear; " +
        "the hours you are drawing are named above the pointer as you go. A day name " +
        "takes the whole day. From the keyboard: arrows move, space marks, shift and " +
        "an arrow paints."));
    const frame = el("div", "hoursbox");
    const names = el("div", "names");
    const scroller = el("div", "hours");
    const ticks = el("div", "ticks");
    const week = el("div", "week");
    const open = el("p", "empty",
      phrase("No half hour is marked, so the hours are not restricted at all: the " +
        "television may be watched at any time of day, within whatever the limits " +
        "above allow."));
    // What the gesture means, over the boxes it means it on. Out of the reading order:
    // every box already says its own day and half hour, and a screen reader following
    // a drag across ninety of them does not need a ninety-first voice.
    const range = el("div", "range");
    range.setAttribute("aria-hidden", "true");
    range.hidden = true;
    // The week as it stands here while the television has yet to hold it. Said in the
    // card rather than in the message under it, because a message goes away and this
    // does not: it is a state the grid is in, not something that just happened.
    const held = el("p", "held");
    held.hidden = true;
    // Two of them, because two different things are pressed here. What the take-over
    // has to say belongs where the banner carrying that button was; what the grid has
    // to say belongs under the grid, beside the boxes a finger has just been on. One
    // note for both would put half its messages at the wrong end of a tall card.
    const took = notice();
    const note = notice();
    week.setAttribute("role", "group");
    week.setAttribute("aria-label", phrase("The half hours viewing is allowed in"));
    // The empty box above Monday, which is the strip of hours the days line up with.
    names.appendChild(el("div", "corner"));
    for (let slot = 0; slot < SLOTS; slot += TICK) {
      ticks.appendChild(el("div", "tick", clock(slot)));
    }
    /** Whether the line under a named hour is carried down through this box. */
    function ruled(slot) {
      if (slot === 0 || slot === SLOTS / 2) return "cell mark noon";
      return slot % TICK === 0 ? "cell mark" : "cell";
    }
    scroller.append(ticks, week);
    frame.append(names, scroller, range);
    box.append(warning, took, lead, frame, held, note, open);

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
    // The week this parent last decided, and when. Between the finger lifting and the
    // rules coming back round the broker there is a second or two in which Home
    // Assistant still reports the old hours, and a poll landing inside it used to write
    // them back over the boxes that had just been drawn. They returned when the write
    // completed, so the grid blinked rather than lost the change — which is worse: it
    // reads as the panel refusing something it had in fact taken (#136).
    let wanted = null;
    let wantedAt = 0;

    WEEK.forEach((day, row) => {
      const label = el("button", "day", day[2]);
      label.type = "button";
      label.setAttribute("aria-label",
        phrase("Every half hour of {day}", {day: day[1]}));
      label.addEventListener("click", () => { whole(row); });
      labels.push(label);
      names.appendChild(label);
      const line = [];
      for (let slot = 0; slot < SLOTS; slot += 1) {
        const cell = el("button", ruled(slot));
        cell.type = "button";
        cell.tabIndex = -1;
        // Where a box is, on the box, because a pointer arrives as a point on the
        // screen and has to be turned back into a day and a half hour.
        cell.atDay = row;
        cell.atSlot = slot;
        cell.setAttribute("aria-pressed", "false");
        cell.setAttribute("aria-label",
          phrase("{day} {from} to {to}",
              {day: day[1], from: clock(slot), to: clock(slot + 1)}));
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

    /** Whether the week Home Assistant reports is the one that was drawn here. */
    function agrees(tv) {
      const given = (tv && tv.hours) || {};
      return WEEK.every((day) => {
        const there = given[day[0]] || [];
        const ours = wanted[day[0]] || [];
        return there.length === ours.length &&
          there.every((at, index) => at === ours[index]);
      });
    }

    /**
     * Whether the grid is the television's to draw on again.
     *
     * Three answers rather than two. The set agrees, and the week is its own once more.
     * The set has not been told yet because it is asleep and the integration is holding
     * the change (#135) — then what the parent drew stays exactly where they drew it,
     * with a line under the grid saying why, for as long as that takes. Or the set is
     * awake, nothing is being held, and the wait is up: it has read the rule
     * differently from this panel, and the one enforcing the hours is the one that gets
     * to say what they are.
     */
    function caught(tv) {
      if (!wanted) return true;
      if (agrees(tv)) wanted = null;
      else if (tv && tv.pending_rules) {
        held.textContent = phrase("These hours are drawn here and waiting: the " +
          "television is asleep, and they go to it the moment it is back.");
        held.hidden = false;
        return false;
      } else if (Date.now() - wantedAt < AGREE_MS) return false;
      else {
        // Awake, holding nothing, and still enforcing something else: it has read the
        // rule differently from this panel. The grid goes back to what is actually
        // being enforced — said out loud, because hours quietly changing back under a
        // parent who drew them is the complaint this whole hold exists to answer.
        wanted = null;
        say(note, phrase("The television is enforcing hours other than the ones " +
          "drawn here, so the grid has gone back to showing its own."), true);
      }
      held.hidden = true;
      return true;
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
     * Say what is being drawn, over the box it is being drawn on.
     *
     * A rectangle of ticked boxes is something to count; "Mon to Wed, 16:00 to 19:30"
     * is the decision itself, and it is the sentence a parent came here to write. Named
     * as the gesture moves rather than once it ends, because the point of saying it is
     * to be right before the finger lifts.
     */
    function speak(first, last, opens, shuts, on, where) {
      const days = first === last
        ? WEEK[first][1]
        : WEEK[first][2] + "\u2013" + WEEK[last][2];
      const span = clock(opens) + "\u2013" + clock(shuts + 1);
      // A finger crossing one box fires a dozen moves, and every one of them used to
      // build this sentence again. Only what it says can change what is on the screen.
      if (range.said !== days + span + on) {
        range.said = days + span + on;
        range.textContent = "";
        range.append(
          el("span", null, phrase(on ? "Allow" : "Clear") +
          " " + days + "\u00a0\u00b7\u00a0"),
          el("b", null, span),
        );
        range.classList.toggle("clearing", !on);
      }
      // Shown before it is measured, because a hidden box has no width and the very
      // first thing said would be placed as though it were a point.
      range.hidden = false;
      // Kept inside the window rather than centred on a pointer that may be at the
      // edge of it: a readout half off the screen is a readout that cannot be read.
      const edge = range.offsetWidth / 2 + PADDING;
      const wide = window.innerWidth || edge * 2;
      range.classList.toggle("below", where.y < LOW);
      range.style.left = Math.max(edge, Math.min(wide - edge, where.x)) + "px";
      range.style.top = where.y + "px";
    }

    /** Where to say it, for a gesture that arrives as a point on the screen. */
    function at(event) {
      return {x: event.clientX, y: event.clientY};
    }

    /** Where to say it, for one the keyboard is making, which has no pointer at all. */
    function above(row, slot) {
      const box = cells[row][slot].getBoundingClientRect();
      return {x: box.left + box.width / 2, y: box.top};
    }

    /** Nothing is being drawn, so nothing is said over the boxes. */
    function quiet() {
      range.hidden = true;
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
    function stretch(row, slot, where) {
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
      speak(first, last, opens, shuts, painting.on, where || above(row, slot));
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
      // Said for a keyed change as well as a dragged one, and about the box it landed
      // on: an arrow paints one half hour at a time, so one half hour is the decision.
      if (paint && !sealed()) speak(row, row, slot, slot, lately, above(row, slot));
      else quiet();
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
        quiet();
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
      // Held from here until the television reports these very hours back, so that the
      // poll `act` is about to make cannot write the old week over the new one.
      wanted = days;
      wantedAt = Date.now();
      // Every day every time, marked and unmarked alike: an unmarked half hour has no
      // other way of being said, so a day left out would be a day with no viewing.
      const answer = await act({id: view.id, action: "hours", days: days}, note, full
        ? phrase("Saved. A week with nothing refused is no restriction, so it clears.")
        : phrase("Hours saved"));
      // Refused, so what is on the grid is a rule nowhere at all. Letting go of it is
      // what snaps the week back to the television below.
      if (!answer || !answer.ok) {
        wanted = null;
        held.hidden = true;
      }
      // `act` has read the state back, so this is what the television has rather than
      // what was drawn at it. A refusal snaps the week back instead of leaving a grid
      // nobody is enforcing on the screen; anything still waiting keeps the boxes as
      // they were drawn.
      if (!painting && caught(view.tv)) draw(view.tv);
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
      stretch(cell.atDay, cell.atSlot, at(event));
    });

    week.addEventListener("pointermove", (event) => {
      if (!painting) return;
      const cell = under(document.elementFromPoint(event.clientX, event.clientY));
      if (cell) stretch(cell.atDay, cell.atSlot, at(event));
    });

    week.addEventListener("pointerup", () => {
      if (!painting) return;
      painting = null;
      quiet();
      commit();
    });

    week.addEventListener("pointercancel", () => {
      if (!painting) return;
      const was = painting.was;
      painting = null;
      quiet();
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
        speak(cell.atDay, cell.atDay, cell.atSlot, cell.atSlot, lately,
          above(cell.atDay, cell.atSlot));
        soon();
      }
    });

    /**
     * Take the hours back off the helper, which changes not one of them.
     *
     * Said in those words because that is the fear: a parent asked to give up a
     * schedule reads it as being asked to give up their evenings, and the evenings are
     * exactly what stays. `act` has read the state back by the time it returns, so the
     * banner is normally gone and the grid live already — and the keyboard is put into
     * the week, because the button that had it is no longer on the page. Where the
     * integration has not caught up, one more read shortly beats sitting in front of a
     * grid that still will not take a finger, wondering whether the button did
     * anything.
     */
    take.addEventListener("click", async () => {
      await act({id: view.id, action: "stop_following"}, took,
        phrase("The hours are yours to draw on, and not one of them has changed."));
      if (sealed()) setTimeout(poll, SETTLE_MS);
      else keyed.focus();
    });

    view.updates.push((tv) => {
      const followed = tv.following_schedule;
      const off = Boolean(followed);
      week.classList.toggle("off", off);
      labels.forEach((label) => { label.disabled = off; });
      cells.forEach((line) => line.forEach((cell) => { cell.disabled = off; }));
      lead.hidden = off;
      warning.hidden = !off;
      // A helper owns the hours now, so a week drawn here before that is not waiting
      // for anything: there is nowhere left for it to go.
      if (off) {
        wanted = null;
        held.hidden = true;
        quiet();
      }
      if (off) {
        sealedBy.textContent = phrase("Read from {helper} whenever it changes, so " +
          "the grid below is read-only.", {helper: followed});
      }
      // Nothing under a finger is written over, and neither is a week that has been
      // decided here and not yet reached the television.
      if (!busy() && caught(tv)) draw(tv);
    });
  }

  /**
   * What the notification setup looks like, asked apart from the state.
   *
   * A different question with a different answer: which phones this house has, and
   * which television already has an automation answering it. Asked once and again after
   * a change rather than every five seconds — a phone is not a thing that appears while
   * somebody is looking at a page, and this one costs a registry read.
   */
  async function askSetup() {
    let said = null;
    try {
      const back = await fetch("api/setup", {headers: {"Accept": "application/json"}});
      said = await back.json();
    } catch (failure) {
      said = {error: phrase("The panel could not reach the add-on.")};
    }
    wanting.forEach((one) => one(said));
  }

  function beat() {
    // A panel in a pocket is a panel nobody is reading, and a phone's battery is worth
    // more than a figure that is five seconds fresher than the moment it is looked at.
    if (!document.hidden) poll();
  }

  /**
   * The parts of the page that are markup rather than script, said in the language.
   *
   * They are written in the document because they are the same four destinations every
   * time and a browser can follow them on its own before any of this has run — which
   * is exactly why they are English until this puts them right. Done before the first
   * paint, so nothing is read in one language and then swapped in another.
   */
  function translate() {
    const lead = document.getElementById("lead");
    if (lead) {
      lead.textContent = phrase("Everything here comes from Home Assistant, which " +
        "is the only thing that talks to the televisions.");
    }
    const which = document.getElementById("which");
    if (which) which.textContent = phrase("Television");
    const rail = document.getElementById("rail");
    if (rail) rail.setAttribute("aria-label", phrase("Sections"));
    // Named one by one rather than built from the destination's own key: a sentence
    // spelled out is a sentence a catalogue can be checked against, and one assembled
    // from a variable is four words nothing can find.
    const NAMED = {
      now: phrase("Now"),
      today: phrase("Today"),
      rules: phrase("Rules"),
      apps: phrase("Apps"),
    };
    WHERE.forEach((one) => {
      const link = document.getElementById("go-" + one);
      const named = link && link.children ? link.children[1] : null;
      if (named) named.textContent = NAMED[one];
    });
  }

  window.addEventListener("hashchange", () => {
    route();
    // A destination is a fresh page to whoever asked for it, and being dropped halfway
    // down one is not that. Only on the way between two of them: on the first read the
    // browser is still restoring where the page was left, and this would undo it.
    if (window.scrollTo) window.scrollTo(0, 0);
  });
  translate();
  document.addEventListener("visibilitychange", beat);
  setInterval(beat, POLL_MS);
  route();
  poll();
  askSetup();
})();
"""


def render_shell(said: dict[str, str] | None = None, language: str = "en") -> str:
    """Return the whole document, which is the same every time in one language.

    Nothing else is interpolated: the page is a shell and the state arrives from
    `api/state` after it has loaded. Both addresses are relative, because an Ingress App
    is served under a path the Supervisor invents per session and an absolute one would
    leave the App altogether.

    The words go in ahead of the script rather than being fetched with the state,
    because the page says things before it has any state — the destinations in the rail
    and the sentence under the title are on the screen while Home Assistant is still
    being asked, and a rail that is briefly English is a rail that flickers.
    """
    # ASCII, so nothing in a translation can be a character this document has a meaning
    # for; and the one sequence that would still end the script early is escaped, which
    # in JSON is the same string written another way.
    catalogue = json.dumps(said or {}).replace("</", "<\\/")
    tongue = html.escape((language or "en").split("-")[0][:8], quote=True)
    return (
        "<!doctype html>\n"
        f'<html lang="{tongue}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>TV Sitter</title>\n"
        "<style>" + _STYLE + "</style>\n"
        "</head>\n"
        "<body>" + _BODY + "<script>const SAID = " + catalogue + ";</script>\n"
        "<script>" + _SCRIPT + "</script>\n"
        "</body>\n"
        "</html>\n"
    )
