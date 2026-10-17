"use strict";
// The Now screen, in each of the four states a parent can find a television in.
//
// Driven through the shell, the way a phone drives it: a poll lands, the screen draws,
// a button is tapped and the change goes out. What is checked is what the parent sees
// and what is sent — the figure that is left, which buttons there are and in which
// order, that a request is answered with the amounts on its buttons and not the ones
// the child asked for, and that a screen redrawn every five seconds stays the screen a
// thumb is already on.
//
// The clock is held still, so "allowed until" and "a minute ago" are the same on every
// machine that runs this.
//
// Run by tests/test_page_drivers.py, which hands over the new page's scripts, joined.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, fire, all} = require("./dom.js");

// Monday 12 October 2026, 18:44 on whatever clock this machine keeps.
const RealDate = Date;
const NOW = new RealDate(2026, 9, 12, 18, 44, 0).getTime();
class StillDate extends RealDate {
  constructor(...given) {
    if (given.length) super(...given);
    else super(NOW);
  }
  static now() { return NOW; }
}
globalThis.Date = StillDate;

const EMPTY_WEEK = {mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: []};

function television(extra) {
  return Object.assign({
    id: "tv1", name: "TV Lounge", reporting: true, screen: true, locked: false,
    playing: "tv.example.video", used_today: 75, limit_today: 120,
    remaining_today: 45, bonus_today: 0, last_reported: "2026-10-12T18:43:00",
    apps: [
      {package: "tv.example.video", name: "Video", minutes: 48, limit: null,
        allowed: true},
      {package: "tv.example.tube", name: "Tube", minutes: 27, limit: null,
        allowed: true},
      {package: "tv.example.games", name: "Games", minutes: 0, limit: null,
        allowed: true},
    ],
    pending_request: null, lock_reason: null, until_s: 2700, version: "0.11.25",
    hours: EMPTY_WEEK,
  }, extra || {});
}

let state = {televisions: [television()], error: null};
const sent = [];
let failing = false;
// While set, a change is not answered until the test says so.
let holding = null;

globalThis.document = document;
globalThis.window = {location: {hash: ""}, addEventListener() {}};
let beat = null;
globalThis.setInterval = (run) => { beat = run; return 1; };
globalThis.fetch = async (url, options) => {
  sent.push({url: url, options: options || {}});
  if (url === "api/do") {
    if (holding) await holding.promise;
    return {json: async () => ({ok: true})};
  }
  if (failing) throw new TypeError("Failed to fetch");
  return {json: async () => JSON.parse(JSON.stringify(state))};
};

function hold() {
  let open = null;
  const promise = new Promise((go) => { open = go; });
  holding = {promise: promise, open: () => { holding = null; open(); }};
  return holding;
}

new Function(fs.readFileSync(process.argv[2], "utf8"))();

const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((go) => setTimeout(go, 0));
  }
};

let failures = 0;
function same(name, got, want) {
  const right = got === want;
  if (!right) failures += 1;
  process.stdout.write((right ? "  ok   " : "  FAIL ") + name +
    (right ? "" : "\n         got  " + JSON.stringify(got) +
      "\n         want " + JSON.stringify(want)) + "\n");
}

const screen = document.getElementById("ts-screen");
const offline = document.getElementById("ts-offline");
const header = document.getElementById("ts-header");

function find(node, test) {
  if (test(node)) return node;
  for (const one of node.children) {
    const found = find(one, test);
    if (found) return found;
  }
  return null;
}
/** Whether a node is on the page: attached under the screen and nothing above it hidden. */
function shown(node) {
  for (let at = node; at; at = at.parentNode) {
    if (at.hidden) return false;
    if (at === screen) return true;
  }
  return false;
}
// The page puts a hard space between a number and its unit; a reader sees a space.
const plain = (words) => String(words).replace(/ /g, " ");
const text = () => plain(screen.textContent);
const button = (label) => find(screen, (one) => one.tagName === "BUTTON" &&
  plain(one.textContent) === label && shown(one));
const actions = () => {
  const row = all(screen, "actions").find(shown);
  return row ? row.children.filter((one) => !one.hidden)
    .map((one) => plain(one.textContent)).join(",") : "";
};
const asking = () => all(screen, "ask").find(shown) || null;
/** The large figure of the hero, as a parent reads it. */
const figure = () => {
  const one = all(screen, "hero__figure").find(shown);
  return one ? plain(one.textContent) : null;
};
const status = () => find(header, (one) => one.classList.contains("status"));
const changes = () => sent.filter((one) => one.url === "api/do")
  .map((one) => JSON.parse(one.options.body));
/** One change, its keys in order, so two spellings of the same change compare equal. */
const sorted = (body) => body ? JSON.stringify(Object.keys(body).sort()
  .reduce((into, key) => { into[key] = body[key]; return into; }, {})) : null;
const lastChange = () => sorted(changes()[changes().length - 1]);

async function show(one) {
  state = {televisions: [one], error: null};
  await beat();
  await settle();
}

async function tap(label) {
  const target = button(label);
  if (!target) throw new Error("no button " + JSON.stringify(label) + " in " + text());
  fire(target, "click");
  await settle();
}

async function main() {
  await settle();

  process.stdout.write("\nwatching shows what is left and four actions\n");
  same("what is left, large", text().indexOf("45 min") >= 0, true);
  same("against the day's limit", text().indexOf("of 2 h") >= 0, true);
  same("and when viewing has to stop", text().indexOf("allowed until 19:29") >= 0,
    true);
  same("four actions, adding time first", actions(),
    "+15 min,+30 min,Lock,No limit today");
  same("today's apps, most watched first", text().indexOf("Video48 min") >= 0 &&
    text().indexOf("Tube27 min") > text().indexOf("Video48 min"), true);
  same("an app nobody opened today is left out", text().indexOf("Games"), -1);
  same("the header says what is playing", plain(status().textContent),
    "Video · 48 min today");
  same("in mint", status().getAttribute("data-tone"), "on");
  await tap("+30 min");
  same("+30 min adds half an hour", lastChange(),
    sorted({action: "add_time", id: "tv1", minutes: 30}));
  await tap("Lock");
  same("Lock locks", lastChange(), sorted({action: "lock", id: "tv1", on: true}));
  await tap("No limit today");
  same("No limit today sets today's limit aside, not the rule", lastChange(),
    sorted({action: "skip_limit_today", id: "tv1"}));
  const kept = button("+15 min");
  const count = screen.children.length;
  await beat();
  await settle();
  same("a poll keeps the same buttons", button("+15 min"), kept);
  same("and adds nothing", screen.children.length, count);
  await show(television({limit_today: null, remaining_today: null, until_s: null}));
  same("no limit says so", text().indexOf("No limit") >= 0, true);
  same("and offers only the lock: added minutes would change nothing", actions(),
    "Lock");
  same("nothing to be allowed until", text().indexOf("allowed until"), -1);
  await show(television({until_s: "not a number"}));
  same("an odd until_s is left out", text().indexOf("allowed until"), -1);
  // Half an hour granted against a parent's lock, on a day with no limit: the lock comes
  // back at the end of it, so "no limit" would be the wrong answer to "how long is left".
  await show(television({limit_today: null, remaining_today: null, until_s: 1800}));
  same("time until a lock comes back is what is left, not no limit", figure(), "30 min");
  same("and it says until when", text().indexOf("allowed until 19:14") >= 0, true);
  // The hours closing before the budget runs out end the evening first.
  await show(television({until_s: 1200}));
  same("whichever ends first is the figure, not the budget it outruns", figure(),
    "20 min");
  same("nor is it a share of a limit it is not", text().indexOf("of 2 h"), -1);

  process.stdout.write("\na waiting request comes first\n");
  const request = {id: "ab12", asked_minutes: 20, asked_at: NOW - 60000,
    app_name: "Video"};
  await show(television({pending_request: request}));
  const panel = asking();
  same("an amber panel", Boolean(panel), true);
  same("first on the screen", screen.children[0], panel);
  same("saying what was asked", panel && plain(panel.textContent)
    .indexOf("20 min more, in Video") >= 0, true);
  same("and when", panel && plain(panel.textContent).indexOf("1 min ago") >= 0, true);
  same("answered with fixed amounts", panel && find(panel, (one) =>
    one.classList.contains("actions")).children.map((one) => one.textContent)
    .join(","), "Give 15,Give 30,Not now");
  const give = button("Give 15");
  await beat();
  await settle();
  same("a poll leaves the panel as it is", asking(), panel);
  same("and its buttons", button("Give 15"), give);
  await tap("Give 15");
  same("Give 15 grants a quarter of an hour", lastChange(),
    sorted({action: "grant", id: "tv1", req_id: "ab12", minutes: 15}));
  await tap("Give 30");
  same("Give 30 grants half an hour", lastChange(),
    sorted({action: "grant", id: "tv1", req_id: "ab12", minutes: 30}));
  await tap("Not now");
  same("Not now refuses it", lastChange(),
    sorted({action: "deny", id: "tv1", req_id: "ab12"}));

  process.stdout.write("\na request that cannot be waiting any more is not shown\n");
  await show(television({pending_request: Object.assign({}, request,
    {asked_at: NOW - 10 * 60000})}));
  same("not once its ten minutes are up", asking(), null);
  await show(television({pending_request: Object.assign({}, request,
    {asked_at: NOW - 9 * 60000})}));
  same("but still a minute before", Boolean(asking()), true);
  await show(television({pending_request: Object.assign({}, request, {asked_at: 0})}));
  same("not with no time of asking", asking(), null);
  await show(television({pending_request: Object.assign({}, request,
    {asked_at: "soon"})}));
  same("nor with a time that is not one", asking(), null);
  await show(television({reporting: false, pending_request: request}));
  same("nor on a set that has stopped reporting", asking(), null);

  process.stdout.write("\nrequest answered elsewhere drops the panel\n");
  await show(television());
  same("no amber panel", asking(), null);
  same("no answer buttons", button("Give 15"), null);
  same("the quick actions stay", actions(), "+15 min,+30 min,Lock,No limit today");

  process.stdout.write("\na second tap while sending does nothing\n");
  const before = changes().length;
  const gate = hold();
  fire(button("+15 min"), "click");
  fire(button("+15 min"), "click");
  await settle();
  same("one add_time sent", changes().length - before, 1);
  same("of fifteen minutes", lastChange(),
    sorted({action: "add_time", id: "tv1", minutes: 15}));
  same("the button is disabled while it goes", button("+15 min").disabled, true);
  same("and so is the rest of the row", button("Lock").disabled, true);
  gate.open();
  await settle();
  same("and comes back once it has gone", button("+15 min").disabled, false);

  process.stdout.write("\nlocked offers unlock first\n");
  const evenings = Object.assign({}, EMPTY_WEEK,
    {mon: ["16:00", "16:30"], tue: ["16:00", "16:30", "17:00"]});
  await show(television({locked: true, lock_reason: "outside_window", until_s: null,
    playing: null, hours: evenings}));
  same("outside the hours only Unlock, which sets the evening's hours aside", actions(),
    "Unlock");
  same("says it is locked", text().indexOf("Locked") >= 0, true);
  same("and why", text().indexOf("Outside the allowed hours") >= 0, true);
  same("and when viewing is allowed again", text()
    .indexOf("Allowed again tomorrow at 16:00") >= 0, true);
  same("and what was watched today", text().indexOf("1 h 15 min watched today") >= 0,
    true);
  same("the header gives the reason", plain(status().textContent),
    "Outside the allowed hours");
  same("in amber", status().getAttribute("data-tone"), "warn");
  await tap("Unlock");
  same("Unlock lifts the lock", lastChange(),
    sorted({action: "lock", id: "tv1", on: false}));
  await show(television({locked: true, lock_reason: "outside_window", until_s: null,
    hours: Object.assign({}, EMPTY_WEEK, {mon: ["16:00", "19:30", "20:00"]})}));
  same("a window later today is today", text().indexOf("Allowed again at 19:30") >= 0,
    true);
  await show(television({locked: true, lock_reason: "daily_limit", until_s: null}));
  same("the day's time used up", text().indexOf("Today's time is used up") >= 0,
    true);
  same("is allowed again tomorrow", text().indexOf("Allowed again tomorrow") >= 0,
    true);
  await show(television({locked: true, lock_reason: "daily_limit", until_s: null,
    hours: evenings}));
  same("with hours, the day's time comes back when tomorrow's hours open", text()
    .indexOf("Allowed again tomorrow at 16:00") >= 0, true);
  await show(television({locked: true, lock_reason: "sleep_timer", until_s: null,
    hours: evenings}));
  same("and so does a sleep timer's", text()
    .indexOf("Allowed again tomorrow at 16:00") >= 0, true);
  await show(television({locked: true, lock_reason: "manual", until_s: null}));
  same("a parent's own lock", text().indexOf("Locked by a parent") >= 0, true);
  await show(television({locked: true, lock_reason: "something_new", until_s: null}));
  same("a reason nobody knows is just locked", plain(status().textContent), "Locked");
  same("and offers the one thing the set does with any lock", actions(), "Unlock");

  process.stdout.write("\neach lock offers only what lifts it\n");
  await show(television({locked: true, lock_reason: "daily_limit", until_s: null,
    remaining_today: 0}));
  same("the day's time: unlock, minutes, or no limit today", actions(),
    "Unlock,+15 min,+30 min,No limit today");
  await tap("+15 min");
  same("+15 min is fifteen minutes", lastChange(),
    sorted({action: "add_time", id: "tv1", minutes: 15}));
  await tap("No limit today");
  same("No limit today is for today", lastChange(),
    sorted({action: "skip_limit_today", id: "tv1"}));
  await show(television({locked: true, lock_reason: "manual", until_s: null}));
  same("a parent's lock: unlock, or minutes it stands down for", actions(),
    "Unlock,+15 min,+30 min");
  await tap("+30 min");
  same("+30 min is half an hour", lastChange(),
    sorted({action: "add_time", id: "tv1", minutes: 30}));
  await show(television({locked: true, lock_reason: "sleep_timer", until_s: null}));
  same("a bedtime: unlock, or minutes that move it on", actions(),
    "Unlock,+15 min,+30 min");
  await show(television({locked: true, lock_reason: "app_limit", until_s: null}));
  same("an app's own budget: nothing here lifts it", actions(), "");
  same("so no row of dead buttons", all(screen, "actions").some(shown), false);
  same("but the reason", text().indexOf("This app's time is used up") >= 0, true);
  same("and what can still be watched", text()
    .indexOf("Other apps can still be watched") >= 0, true);
  await show(television({locked: true, lock_reason: "app_not_allowed", until_s: null}));
  same("an app not allowed: nothing either", actions(), "");
  same("with the reason", text().indexOf("This app is not allowed") >= 0, true);

  process.stdout.write("\nnot reachable still takes a lock, and nothing else\n");
  await show(television({reporting: false, playing: null,
    last_reported: "2026-10-12T17:05:00"}));
  same("when it was last seen", text().indexOf("Last seen") >= 0 &&
    text().indexOf("17:05") >= 0, true);
  same("and that its rules keep working", text()
    .indexOf("Its rules keep working on the television.") >= 0, true);
  same("only Lock is offered", actions(), "Lock");
  same("and it can be pressed", button("Lock").disabled, false);
  same("with what waits and what does not", text()
    .indexOf("A lock waits until it is back; the rest needs it on.") >= 0, true);
  same("the header says since when", plain(status().textContent),
    "Not reachable since 17:05");
  same("in amber", status().getAttribute("data-tone"), "warn");
  await tap("Lock");
  same("Lock goes to the switch, which holds it", lastChange(),
    sorted({action: "lock", id: "tv1", on: true}));
  await show(television({reporting: false, playing: null, locked: true,
    lock_pending: "lock", last_reported: "2026-10-12T17:05:00"}));
  same("a held lock can be taken back", actions(), "Unlock");
  same("and says it is waiting", text()
    .indexOf("It will lock as soon as it is back.") >= 0, true);
  await show(television({reporting: false, playing: null, locked: false,
    lock_pending: "unlock", last_reported: "2026-10-12T17:05:00"}));
  same("a held unlock says how long it waits", text()
    .indexOf("It will unlock if it is back within 15 minutes.") >= 0, true);
  await show(television({reporting: false, playing: null,
    apps: [{package: "tv.example.blip", name: "Blip", minutes: 0.3}],
    last_reported: "2026-10-12T17:05:00"}));
  same("a few seconds in an app is not a row", text().indexOf("Blip") < 0, true);
  await show(television({reporting: false, last_reported: null}));
  same("a set that never reported says so", text().indexOf("Never reported") >= 0,
    true);

  process.stdout.write("\na failed poll keeps the screen and says so\n");
  await show(television());
  const drawn = text();
  failing = true;
  await beat();
  await settle();
  failing = false;
  same("the Now content is unchanged", text(), drawn);
  same("and the line says so", offline.hidden === false &&
    offline.textContent, "No connection to Home Assistant");

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall good\n");
  process.exit(failures ? 1 : 0);
}

main().catch((failure) => {
  process.stdout.write(String(failure && failure.stack || failure) + "\n");
  process.exit(1);
});
