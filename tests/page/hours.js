"use strict";
// Draw on the weekly grid the way a parent does, and check what is left on it.
//
// The one that mattered: a run is drawn, the write goes, and a poll lands in the gap
// before the television has reported anything back. That poll used to write the old
// week over the new one, and the boxes returned a second or two later when the write
// completed — so nothing was ever lost, and it read as the panel refusing a change it
// had in fact taken (#136).
//
// Run by tests/test_panel_grid.py, which hands it the page as the browser gets it.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only
// the gap before the television has said anything back.

const fs = require("fs");
const path = require("path");
const {document, fire, all} = require("./dom.js");

const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const SLOTS = 48;

function blank() {
  const hours = {};
  WEEK.forEach((day) => { hours[day] = []; });
  return hours;
}

function television() {
  return {
    id: "tv1", name: "TV Salon", reporting: true, screen: false, locked: false,
    playing: null, pin_set: true, used_today: 0, limit_today: null,
    remaining_today: null, bonus_today: 0, used_yesterday: null,
    last_reported: null, rules_revision: 1, daily_limit: 60, sleep_timer: null,
    warn_before: null, block_settings: false,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], week_by_app: [], allowed_apps: [], exempt_apps: [], windows: [],
    following_schedule: null, hours: blank(), pending_rules: null, trouble: [],
  };
}

let state = {televisions: [television()], error: null};
// What the world does with a write, set per scene: the television takes it at once,
// takes it late, holds it because it is asleep, or refuses it outright.
let world = "at once";
let sent = null;

function serve(body) {
  if (body.action !== "hours") return {ok: true};
  sent = body.days;
  const tv = state.televisions[0];
  if (world === "refused") {
    return {ok: false, error: "TV Salon takes its hours from schedule.evenings."};
  }
  if (world === "asleep") {
    tv.pending_rules = {windows: [{id: "held", from: "16:00", to: "19:30"}]};
    return {ok: true};
  }
  if (world === "at once") {
    const hours = blank();
    WEEK.forEach((day) => { hours[day] = (body.days[day] || []).slice().sort(); });
    tv.hours = hours;
  }
  // "late" leaves the state exactly as it was: the write is away, and Home Assistant
  // is still reporting what the set had before it.
  return {ok: true};
}

// A clock that only moves when this moves it, so the wait a drawn week is given can
// be lived through in a test without anybody sitting out twelve real seconds.
let clock = 1750000000000;
const Real = Date;
globalThis.Date = class extends Real {
  static now() { return clock; }
};

globalThis.document = document;
globalThis.window = {
  location: {hash: "#rules"},
  addEventListener() {},
  scrollTo() {},
  innerWidth: 1200,
};
globalThis.setInterval = () => 0;
globalThis.fetch = async (url, init) => {
  if (url === "api/do") return {json: async () => serve(JSON.parse(init.body))};
  return {json: async () => JSON.parse(JSON.stringify(state))};
};

const source = fs.readFileSync(process.argv[2], "utf8");
new Function(source)();

const settle = async () => {
  for (let turn = 0; turn < 14; turn += 1) {
    await new Promise((go) => setTimeout(go, 0));
  }
};
const sleep = (ms) => new Promise((go) => setTimeout(go, ms));
const forcePoll = async () => {
  fire(document, "visibilitychange", {});
  await settle();
};

let failures = 0;
function ok(name, held) {
  if (!held) failures += 1;
  process.stdout.write((held ? "  ok   " : "  FAIL ") + name + "\n");
}
function same(name, got, want) {
  const right = JSON.stringify(got) === JSON.stringify(want);
  if (!right) failures += 1;
  process.stdout.write((right ? "  ok   " : "  FAIL ") + name +
    (right ? "" : "\n         got  " + JSON.stringify(got) +
      "\n         want " + JSON.stringify(want)) + "\n");
}

async function main() {
  await settle();

  const grid = all(document, "week")[0];
  const cells = grid.children.filter((one) => one.classList.contains("cell"));
  const hoursCard = grid.parentNode.parentNode.parentNode;
  const range = all(hoursCard, "range")[0];
  const held = all(hoursCard, "held")[0];
  // Two of them in this card — the take-over speaks in the first, the grid in
  // the second — and it is the grid's answers this is about.
  const note = all(hoursCard, "note")[1];
  const ticks = all(document, "ticks")[0];

  const box = (row, slot) => cells[row * SLOTS + slot];
  const on = (row) => cells.slice(row * SLOTS, row * SLOTS + SLOTS)
    .map((one, slot) => (one.classList.contains("on") ? slot : -1))
    .filter((slot) => slot >= 0);

  // 16:00 is the thirty-second half hour of the day; 19:00 the thirty-eighth, which
  // with 19:30 marked as well makes a run that ends at 19:30.
  const OPENS = 32;
  const SHUTS = 38;
  const RUN = [];
  for (let slot = OPENS; slot <= SHUTS; slot += 1) RUN.push(slot);

  async function drag(row, from, to, world_) {
    world = world_;
    document.elementFromPoint = () => null;
    fire(box(row, from), "pointerdown", {
      target: box(row, from), pointerId: 1, clientX: 300, clientY: 400,
    });
    for (let slot = from + 1; slot <= to; slot += 1) {
      document.elementFromPoint = () => box(row, slot);
      fire(grid, "pointermove", {pointerId: 1, clientX: 300 + slot, clientY: 400});
    }
    fire(grid, "pointerup", {pointerId: 1});
    await settle();
  }

  process.stdout.write("\nWhat is being drawn is named as it is drawn\n");
  world = "at once";
  fire(box(4, OPENS), "pointerdown", {
    target: box(4, OPENS), pointerId: 1, clientX: 300, clientY: 400,
  });
  ok("the readout is showing", range.hidden === false);
  same("one box is one half hour", range.textContent,
    "Allow Friday · 16:00–16:30");
  document.elementFromPoint = () => box(4, SHUTS);
  fire(grid, "pointermove", {pointerId: 1, clientX: 340, clientY: 400});
  same("the run is named as it grows", range.textContent,
    "Allow Friday · 16:00–19:30");
  document.elementFromPoint = () => box(6, SHUTS);
  fire(grid, "pointermove", {pointerId: 1, clientX: 340, clientY: 460});
  same("days are named as a span too", range.textContent,
    "Allow Fri–Sun · 16:00–19:30");
  ok("it is placed above the pointer", range.classList.contains("below") === false);
  ok("and kept inside the window", Number(String(range.style.left).replace("px", ""))
    <= 1200 - 78);
  fire(grid, "pointerup", {pointerId: 1});
  await settle();
  ok("and gone once the finger lifts", range.hidden === true);

  process.stdout.write("\nA run drawn and taken at once\n");
  state = {televisions: [television()], error: null};
  await forcePoll();
  await drag(0, OPENS, SHUTS, "at once");
  same("Monday holds the run", on(0), RUN);
  await forcePoll();
  same("and holds it after a poll", on(0), RUN);
  ok("nothing says it is waiting", held.hidden === true);

  process.stdout.write("\nA run the television has not reported back yet\n");
  state = {televisions: [television()], error: null};
  await forcePoll();
  await drag(0, OPENS, SHUTS, "late");
  same("the boxes stay where they were drawn", on(0), RUN);
  await forcePoll();
  same("a poll landing in the gap does not wipe them", on(0), RUN);
  await forcePoll();
  same("nor does the next one", on(0), RUN);
  // The television reports them at last, and the grid is its own again.
  const arrived = blank();
  arrived.mon = RUN.map((slot) =>
    String(Math.floor(slot / 2)).padStart(2, "0") + (slot % 2 ? ":30" : ":00"));
  state.televisions[0].hours = arrived;
  await forcePoll();
  same("and they are still there once it does", on(0), RUN);

  process.stdout.write("\nA run drawn at a television that is asleep\n");
  state = {televisions: [television()], error: null};
  await forcePoll();
  await drag(1, OPENS, SHUTS, "asleep");
  same("Tuesday holds the run", on(1), RUN);
  ok("and the card says it is waiting", held.hidden === false);
  ok("in so many words", held.textContent.indexOf("asleep") > 0);
  await forcePoll();
  same("a poll does not take it away", on(1), RUN);
  await sleep(60);
  await forcePoll();
  same("and neither does time passing", on(1), RUN);

  process.stdout.write("\nA run the television refuses\n");
  state = {televisions: [television()], error: null};
  await forcePoll();
  await drag(2, OPENS, SHUTS, "refused");
  same("the week snaps back to what is enforced", on(2), []);
  ok("and the refusal is on the screen",
    note.textContent.indexOf("schedule.evenings") > 0);
  ok("with nothing claiming to be waiting", held.hidden === true);

  process.stdout.write("\nA television that is awake and enforcing something else\n");
  state = {televisions: [television()], error: null};
  await forcePoll();
  await drag(3, OPENS, SHUTS, "late");
  same("Thursday holds the run to begin with", on(3), RUN);
  // Awake, holding nothing, and still saying the hours are empty: it has read the rule
  // differently from the panel, and the one enforcing them gets to say what they are.
  clock += 13000;
  await forcePoll();
  same("the television has it back once the wait is up", on(3), []);
  ok("and taking it back is said out loud",
    note.textContent.indexOf("other than the ones drawn here") > 0);

  process.stdout.write("\nThe grid reads as a time of day\n");
  same("the hour is named every two hours", ticks.children.length, 12);
  same("the first is midnight", ticks.children[0].textContent, "00:00");
  same("and one of them is noon", ticks.children[6].textContent, "12:00");
  ok("midnight carries a line", box(0, 0).classList.contains("noon"));
  ok("so does noon", box(0, 24).classList.contains("noon"));
  ok("every named hour carries one", box(0, 4).classList.contains("mark"));
  ok("and the ones between do not", box(0, 5).classList.contains("mark") === false);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
