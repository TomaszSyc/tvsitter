"use strict";
// The Rules screen, one day at a time: how much on that day, and when.
//
// Driven through the shell the way a phone drives it. The checks are about what leaves
// the page — a block saved next to another goes out as one window, an edit on Wednesday
// sends Wednesday changed and the other six days exactly as they were, a limit sends a
// limit and never the hours — and about what stays on it while a poll lands every five
// seconds: an open sheet, hours just saved that the television has not reported back.
//
// The last part is the old weekly grid's lesson, carried over (#136): between a write
// and the television saying it back there is a gap, and a poll landing in it used to
// paint the old hours over the ones just drawn.
//
// Run by tests/test_page_drivers.py, which hands over the new page's scripts, joined.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, fire, all} = require("./dom.js");

// Monday 12 October 2026, 18:44, and a clock that moves only when this moves it.
const RealDate = Date;
let now = new RealDate(2026, 9, 12, 18, 44, 0).getTime();
class StillDate extends RealDate {
  constructor(...given) {
    if (given.length) super(...given);
    else super(now);
  }
  static now() { return now; }
}
globalThis.Date = StillDate;

const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

function blank() {
  const hours = {};
  WEEK.forEach((day) => { hours[day] = []; });
  return hours;
}

/** The half hours from one time up to another, the way the state names them. */
function span(from, to) {
  const minute = (at) => Number(at.slice(0, 2)) * 60 + Number(at.slice(3));
  const out = [];
  for (let at = minute(from); at < minute(to); at += 30) {
    out.push(String(Math.floor(at / 60)).padStart(2, "0") + ":" +
      String(at % 60).padStart(2, "0"));
  }
  return out;
}

function television(extra) {
  return Object.assign({
    id: "tv1", name: "TV Lounge", reporting: true, screen: false, locked: false,
    playing: null, used_today: 0, limit_today: 120, remaining_today: 120,
    last_reported: "2026-10-12T18:43:00", daily_limit: 120, sleep_timer: null,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], following_schedule: null, hours: blank(), pending_rules: null,
    pending_request: null,
  }, extra || {});
}

let state = {televisions: [television()], error: null};
// What the world does with a write: takes it at once, takes it late, holds it for a
// sleeping set, or refuses it.
let world = "at once";
const sent = [];

function serve(body) {
  sent.push(body);
  const tv = state.televisions[0];
  if (body.action !== "hours") return {ok: true};
  if (world === "refused") {
    return {ok: false, error: "TV Lounge takes its hours from schedule.evenings."};
  }
  if (world === "asleep") {
    tv.pending_rules = {windows: [{id: "held", from: "16:00", to: "19:30"}]};
  }
  if (world === "at once" || world === "asleep") {
    const hours = blank();
    WEEK.forEach((day) => { hours[day] = (body.days[day] || []).slice().sort(); });
    tv.hours = hours;
  }
  return {ok: true};
}

globalThis.document = document;
globalThis.window = {location: {hash: ""}, addEventListener() {}, scrollTo() {}};
let beat = null;
globalThis.setInterval = (run) => { beat = run; return 1; };
globalThis.fetch = async (url, options) => {
  if (url === "api/do") {
    const body = JSON.parse(options.body);
    return {json: async () => serve(body)};
  }
  return {json: async () => JSON.parse(JSON.stringify(state))};
};

new Function(fs.readFileSync(process.argv[2], "utf8"))();
const TS = globalThis.window.TS;

const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((go) => setTimeout(go, 0));
  }
};

let failures = 0;
function same(name, got, want) {
  const right = JSON.stringify(got) === JSON.stringify(want);
  if (!right) failures += 1;
  process.stdout.write((right ? "  ok   " : "  FAIL ") + name +
    (right ? "" : "\n         got  " + JSON.stringify(got) +
      "\n         want " + JSON.stringify(want)) + "\n");
}
const ok = (name, held) => same(name, Boolean(held), true);

const screen = document.getElementById("ts-screen");
const plain = (words) => String(words).replace(/ /g, " ");

function find(node, test) {
  if (test(node)) return node;
  for (const one of node.children) {
    const found = find(one, test);
    if (found) return found;
  }
  return null;
}
function shown(node, top) {
  for (let at = node; at; at = at.parentNode) {
    if (at.hidden) return false;
    if (at === top) return true;
  }
  return false;
}
const button = (top, label) => find(top, (one) => one.tagName === "BUTTON" &&
  plain(one.textContent) === label && shown(one, top));
const chip = (day) => find(screen, (one) => one.getAttribute &&
  one.getAttribute("data-day") === day);
/** The blocks on the axis, as the times they say. */
const blocks = () => all(screen, "block").filter((one) => shown(one, screen))
  .map((one) => plain(one.textContent));
const block = (label) => all(screen, "block").find((one) =>
  plain(one.textContent) === label);
const sheet = () => all(document.body, "sheet")
  .find((one) => shown(one, document.body)) || null;
const edge = (name) => find(sheet(), (one) => one.tagName === "SELECT" &&
  one.getAttribute("data-edge") === name);
function choose(name, value) {
  const select = edge(name);
  select.value = value;
  fire(select, "change", {});
}
const hoursSent = () => sent.filter((one) => one.action === "hours");
const lastHours = () => hoursSent()[hoursSent().length - 1];
const warning = () => all(screen, "limit__warn").find((one) => shown(one, screen));

async function show(one) {
  state = {televisions: [one], error: null};
  sent.length = 0;
  world = "at once";
  if (TS.sheet) TS.sheet.close();
  // Elsewhere and back, which builds the screen afresh on today.
  TS.go("now");
  TS.go("rules");
  await beat();
  await settle();
}

async function main() {
  await settle();

  process.stdout.write("\nHalf hours and blocks are the same hours\n");
  same("slots become blocks and back",
    TS.rules.blocks(["16:00", "16:30", "17:00"]), [{from: "16:00", to: "17:30"}]);
  same("and back again", TS.rules.slots([{from: "16:00", to: "17:30"}]),
    ["16:00", "16:30", "17:00"]);
  same("out of order is still one block",
    TS.rules.blocks(["17:00", "16:00", "16:30"]), [{from: "16:00", to: "17:30"}]);
  same("a gap makes two", TS.rules.blocks(["08:00", "16:00"]),
    [{from: "08:00", to: "08:30"}, {from: "16:00", to: "16:30"}]);
  same("the last half hour ends at midnight", TS.rules.blocks(["23:30"]),
    [{from: "23:30", to: "24:00"}]);
  same("overlapping blocks are one set of half hours",
    TS.rules.slots([{from: "16:00", to: "17:00"}, {from: "16:30", to: "18:00"}]),
    span("16:00", "18:00"));
  same("midnight is an end and never a start",
    TS.rules.slots([{from: "24:00", to: "24:00"}, {from: "23:00", to: "24:00"}]),
    ["23:00", "23:30"]);

  process.stdout.write("\nThe screen opens on today\n");
  await show(television());
  same("Monday is the day shown", chip("mon").getAttribute("aria-pressed"), "true");
  same("and only Monday", WEEK.filter((day) =>
    chip(day).getAttribute("aria-pressed") === "true"), ["mon"]);
  ok("How much is a heading", find(screen, (one) => one.textContent === "How much"));
  ok("and When is one", find(screen, (one) => one.textContent === "When"));

  process.stdout.write("\nTouching blocks become one\n");
  const evening = blank();
  evening.mon = span("17:00", "19:00");
  await show(television({hours: evening}));
  same("one block to begin with", blocks(), ["17:00–19:00"]);
  fire(button(screen, "Add hours"), "click", {});
  ok("adding opens the sheet", sheet());
  ok("a new block has nothing to delete", !button(sheet(), "Delete"));
  choose("from", "16:00");
  choose("to", "17:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  ok("saving closes the sheet", !sheet());
  same("one window goes out", TS.rules.blocks(lastHours().days.mon),
    [{from: "16:00", to: "19:00"}]);
  same("and the axis shows one block", blocks(), ["16:00–19:00"]);

  process.stdout.write("\nThe first block warns that other days lock\n");
  const lockWarn = () => sheet() && all(sheet(), "sheet__warn")
    .find((one) => shown(one, document.body));
  await show(television());
  fire(button(screen, "Add hours"), "click", {});
  ok("the first block of an empty week warns",
    lockWarn() && plain(lockWarn().textContent).indexOf("locked") >= 0);
  TS.sheet.close();
  await show(television({hours: evening}));
  fire(button(screen, "Add hours"), "click", {});
  ok("a week that already has hours does not", !lockWarn());
  TS.sheet.close();
  fire(block("17:00–19:00"), "click", {});
  ok("nor does editing a block", !lockWarn());
  TS.sheet.close();

  process.stdout.write("\nAfter the first block the locked days are named\n");
  const lockedNote = () => all(screen, "when__locked").find((one) => shown(one, screen));
  await show(television());
  ok("nothing is named before", !lockedNote());
  fire(button(screen, "Add hours"), "click", {});
  choose("from", "16:00");
  choose("to", "17:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  ok("the note is there", lockedNote());
  ok("naming Tuesday to Sunday", lockedNote() &&
    plain(lockedNote().textContent).indexOf("Tue, Wed, Thu, Fri, Sat, Sun") >= 0);
  ok("and not Monday", lockedNote() &&
    plain(lockedNote().textContent).indexOf("Mon") < 0);
  ok("the copy chips are beside it", button(screen, "the whole week"));
  fire(button(screen, "the whole week"), "click", {});
  await settle();
  same("whole week sends all seven days equal",
    WEEK.map((day) => lastHours().days[day]), WEEK.map(() => span("16:00", "17:00")));
  ok("and the note goes", !lockedNote());
  await show(television());
  fire(button(screen, "Add hours"), "click", {});
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  ok("named again after another first block", lockedNote());
  fire(chip("tue"), "click", {});
  ok("and gone when the day is switched", !lockedNote());

  process.stdout.write("\nEditing a block sends the whole week, one day changed\n");
  const week = blank();
  week.mon = span("16:00", "18:00");
  week.wed = span("15:00", "17:00");
  week.sat = span("09:00", "12:00").concat(span("14:00", "20:00"));
  week.sun = span("10:00", "12:00");
  await show(television({hours: JSON.parse(JSON.stringify(week))}));
  fire(chip("wed"), "click", {});
  same("Wednesday's hours are on the axis", blocks(), ["15:00–17:00"]);
  fire(block("15:00–17:00"), "click", {});
  ok("tapping a block opens the sheet", sheet());
  same("from is where the block starts", edge("from").value, "15:00");
  same("and to where it ends", edge("to").value, "17:00");
  choose("to", "20:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  const edited = lastHours();
  same("it is the hours action", edited.action, "hours");
  same("for this television", edited.id, "tv1");
  same("Wednesday is changed", edited.days.wed, span("15:00", "20:00"));
  same("and every other day is byte for byte what it was",
    JSON.stringify(WEEK.filter((day) => day !== "wed").map((day) => edited.days[day])),
    JSON.stringify(WEEK.filter((day) => day !== "wed").map((day) => week[day])));

  process.stdout.write("\nDeleting a block\n");
  fire(chip("sat"), "click", {});
  same("Saturday has two blocks", blocks(), ["09:00–12:00", "14:00–20:00"]);
  fire(block("09:00–12:00"), "click", {});
  fire(button(sheet(), "Delete"), "click", {});
  await settle();
  same("only the other block is sent", lastHours().days.sat, span("14:00", "20:00"));
  same("and drawn", blocks(), ["14:00–20:00"]);

  process.stdout.write("\nCancel and Escape leave everything as it was\n");
  const before = sent.length;
  const tapped = block("14:00–20:00");
  fire(tapped, "click", {});
  choose("from", "13:00");
  fire(button(sheet(), "Cancel"), "click", {});
  await settle();
  ok("Cancel closes the sheet", !sheet());
  same("and sends nothing", sent.length, before);
  ok("the focus is back on the block", document.activeElement === tapped);
  fire(tapped, "click", {});
  fire(edge("from"), "keydown", {key: "Escape"});
  ok("Escape closes it too", !sheet());
  fire(tapped, "click", {});
  fire(all(document.body, "sheet__backdrop")[0], "click", {});
  ok("and so does a tap outside it", !sheet());
  same("still nothing sent", sent.length, before);

  process.stdout.write("\nAn end before the start is not saved\n");
  fire(tapped, "click", {});
  choose("from", "20:00");
  same("moving the start onto the end moves the end", edge("to").value, "20:30");
  choose("to", "17:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  ok("the sheet stays open", sheet());
  ok("and says why", plain(sheet().textContent).indexOf("after the start") >= 0);
  same("nothing sent", sent.length, before);
  TS.sheet.close();

  process.stdout.write("\nTapping empty time adds a block there\n");
  await show(television());
  const lane = all(screen, "axis__lane")[0];
  // The fake DOM puts every box at y = 200; each hour is PX_PER_HOUR tall from 06:00.
  const perHour = TS.rules.PX_PER_HOUR;
  fire(lane, "click", {target: lane, clientY: 200 + 10 * perHour + 2});
  ok("the sheet opens", sheet());
  same("from the half hour tapped", edge("from").value, "16:00");
  same("for an hour", edge("to").value, "17:00");
  TS.sheet.close();

  process.stdout.write("\nThe limit never moves the hours\n");
  await show(television({hours: JSON.parse(JSON.stringify(week)),
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: 150, sun: null}}));
  fire(chip("sat"), "click", {});
  same("Saturday's own limit is shown", plain(all(screen, "limit__figure")[0]
    .textContent), "2 h 30 min");
  fire(button(screen, "−"), "click", {});
  await settle();
  same("one change goes out", sent.length, 1);
  same("and it is Saturday's limit, fifteen minutes less", sent[0],
    {id: "tv1", action: "number", key: "limit_sat", value: 135});
  same("the figure follows at once", plain(all(screen, "limit__figure")[0]
    .textContent), "2 h 15 min");
  fire(chip("sun"), "click", {});
  same("a day without its own says so", plain(all(screen, "limit__figure")[0]
    .textContent), "As daily");
  fire(button(screen, "+"), "click", {});
  await settle();
  same("and steps from the daily limit", sent[sent.length - 1],
    {id: "tv1", action: "number", key: "limit_sun", value: 135});
  same("no hours were sent", hoursSent().length, 0);

  process.stdout.write("\nNever below nothing\n");
  await show(television({week: {mon: 0, tue: null, wed: null, thu: null, fri: null,
    sat: null, sun: null}}));
  ok("minus is off at zero", button(screen, "−").disabled);
  fire(button(screen, "−"), "click", {});
  await settle();
  same("and sends nothing", sent.length, 0);

  process.stdout.write("\nA limit over the window is said\n");
  const narrow = blank();
  narrow.mon = span("16:00", "19:30");
  await show(television({hours: narrow,
    week: {mon: 240, tue: null, wed: null, thu: null, fri: null, sat: null, sun: null}}));
  ok("the amber note is there", warning());
  ok("naming the window", plain(warning().textContent).indexOf("3 h 30 min") >= 0);
  ok("the window is said anyway",
    plain(screen.textContent).indexOf("(window: 3 h 30 min)") >= 0);
  await show(television({hours: narrow,
    week: {mon: 120, tue: null, wed: null, thu: null, fri: null, sat: null, sun: null}}));
  ok("and not while the limit fits", !warning());

  process.stdout.write("\nCopy to weekdays\n");
  await show(television({hours: JSON.parse(JSON.stringify(week))}));
  fire(chip("sat"), "click", {});
  fire(button(screen, "weekdays"), "click", {});
  await settle();
  const copied = lastHours();
  same("Monday to Friday get Saturday's hours",
    ["mon", "tue", "wed", "thu", "fri"].map((day) => copied.days[day]),
    ["mon", "tue", "wed", "thu", "fri"].map(() => week.sat));
  same("and the weekend is untouched", [copied.days.sat, copied.days.sun],
    [week.sat, week.sun]);
  fire(chip("mon"), "click", {});
  fire(button(screen, "the weekend"), "click", {});
  await settle();
  same("the weekend takes Monday's", [lastHours().days.sat, lastHours().days.sun],
    [week.sat, week.sat]);

  process.stdout.write("\nThe axis draws the waiting hours\n");
  const waiting = blank();
  waiting.mon = span("18:00", "20:00");
  await show(television({reporting: false, hours: waiting,
    pending_rules: {windows: [{id: "w", from: "18:00", to: "20:00", days: ["mon"]}]}}));
  same("the waiting hours are on the axis", blocks(), ["18:00–20:00"]);
  const bar = all(screen, "held")[0];
  ok("the amber bar is up", bar && shown(bar, screen));
  fire(button(bar, "Undo"), "click", {});
  await settle();
  same("Undo forgets the waiting change", sent[sent.length - 1],
    {id: "tv1", action: "forget_pending"});
  state.televisions[0].pending_rules = null;
  state.televisions[0].hours = blank();
  await beat();
  ok("and the bar goes with it", !shown(bar, screen));

  process.stdout.write("\nHours from a schedule are read-only\n");
  await show(television({following_schedule: "schedule.evenings",
    hours: JSON.parse(JSON.stringify(week))}));
  ok("there is no Add hours", !button(screen, "Add hours"));
  ok("no copying either", !button(screen, "weekdays"));
  fire(block("16:00–18:00"), "click", {});
  ok("a block does not open the sheet", !sheet());
  fire(all(screen, "axis__lane")[0], "click",
    {target: all(screen, "axis__lane")[0], clientY: 200 + 2 * perHour});
  ok("nor does empty time", !sheet());
  ok("the note says where they come from", plain(screen.textContent)
    .indexOf("Read-only: the hours come from schedule.evenings.") >= 0);

  process.stdout.write("\nA poll while the sheet is open\n");
  await show(television({hours: JSON.parse(JSON.stringify(week))}));
  fire(block("16:00–18:00"), "click", {});
  choose("from", "15:00");
  const open = sheet();
  state.televisions[0].hours.mon = span("10:00", "11:00");
  state.televisions[0].daily_limit = 90;
  await beat();
  await settle();
  ok("leaves the sheet open", sheet() === open);
  same("with the start the parent chose", edge("from").value, "15:00");
  same("and the end it had", edge("to").value, "18:00");
  TS.sheet.close();

  process.stdout.write("\nHours the television has not reported back yet\n");
  await show(television());
  world = "late";
  fire(button(screen, "Add hours"), "click", {});
  choose("from", "16:00");
  choose("to", "19:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  same("the block stays where it was put", blocks(), ["16:00–19:00"]);
  await beat();
  same("a poll in the gap does not wipe it", blocks(), ["16:00–19:00"]);
  state.televisions[0].hours.mon = span("16:00", "19:00");
  await beat();
  same("and it is still there once the set reports it", blocks(), ["16:00–19:00"]);

  process.stdout.write("\nHours saved for a television that is asleep\n");
  await show(television({reporting: false}));
  world = "asleep";
  fire(chip("tue"), "click", {});
  fire(button(screen, "Add hours"), "click", {});
  choose("from", "16:00");
  choose("to", "19:30");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  same("Tuesday holds the block", blocks(), ["16:00–19:30"]);
  ok("and the amber bar says it is waiting", shown(all(screen, "held")[0], screen));
  await beat();
  same("a poll does not take it away", blocks(), ["16:00–19:30"]);
  now += 60000;
  await beat();
  same("and neither does time passing", blocks(), ["16:00–19:30"]);

  process.stdout.write("\nHours an awake television never takes\n");
  await show(television());
  world = "late";
  fire(button(screen, "Add hours"), "click", {});
  choose("from", "16:00");
  choose("to", "19:00");
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  same("drawn to begin with", blocks(), ["16:00–19:00"]);
  now += 13000;
  await beat();
  same("the axis is the television's again once the wait is up", blocks(), []);
  ok("and that is said", plain(screen.textContent)
    .indexOf("The television is enforcing other hours") >= 0);

  process.stdout.write("\nHours the television refuses\n");
  await show(television());
  world = "refused";
  fire(button(screen, "Add hours"), "click", {});
  fire(button(sheet(), "Save"), "click", {});
  await settle();
  same("the axis snaps back", blocks(), []);
  ok("and the refusal is on the screen",
    plain(screen.textContent).indexOf("schedule.evenings") >= 0);

  process.stdout.write("\nEvery day, and today\n");
  await show(television());
  const daily = all(screen, "daily")[0];
  fire(button(daily, "+"), "click", {});
  await settle();
  same("the daily limit steps by fifteen", sent[sent.length - 1],
    {id: "tv1", action: "number", key: "daily_limit", value: 135});
  fire(button(screen, "Start"), "click", {});
  await settle();
  same("the sleep timer starts at the length chosen", sent[sent.length - 1],
    {id: "tv1", action: "number", key: "sleep_timer", value: 60});
  await show(television({reporting: false}));
  ok("and cannot while the set is away", button(screen, "Start").disabled);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main().catch((error) => {
  process.stdout.write("\n" + (error && error.stack || error) + "\n");
  process.exit(1);
});
