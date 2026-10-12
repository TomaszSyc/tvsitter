"use strict";
// The Apps screen: the allow-list switch, the list, and the sheet behind each app.
//
// Driven through the shell the way a phone drives it. The checks are about what leaves
// the page — the whole allow-list every time, a limit as minutes and its removal as
// null — and about what stays on it while a poll lands every five seconds: a switch
// just turned, a sheet being used.
//
// Run by tests/test_panel_page.py, which hands over the new page's scripts, joined.
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

const NETFLIX = "tv.example.stream";
const VIDEO = "tv.example.video";
const SPORT = "tv.example.sport";
const GAMES = "tv.example.games";
const LAUNCHER = "tv.example.launcher";

function app(package_, name, minutes, limit, allowed) {
  return {package: package_, name: name, minutes: minutes, limit: limit,
    allowed: allowed === undefined ? true : allowed};
}

function television(extra) {
  return Object.assign({
    id: "tv1", name: "TV Lounge", reporting: true, screen: false, locked: false,
    playing: null, used_today: 0, limit_today: 120, remaining_today: 120,
    last_reported: "2026-10-12T18:43:00", daily_limit: 120, sleep_timer: null,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], allowed_apps: [], exempt_apps: [LAUNCHER], week_by_app: [],
    hours: {mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: []},
    following_schedule: null, pending_rules: null, pending_request: null,
  }, extra || {});
}

let state = {televisions: [television()], error: null};
// What the world does with a write: takes it at once, never lets the television say
// it back, or refuses it.
let world = "at once";
const sent = [];

function serve(body) {
  sent.push(body);
  const tv = state.televisions[0];
  if (world === "refused") return {ok: false, error: "Home Assistant said no."};
  if (world !== "at once") return {ok: true};
  if (body.action === "allowed_apps") {
    tv.allowed_apps = body.packages.slice();
    tv.apps.forEach((one) => {
      one.allowed = !tv.allowed_apps.length || tv.allowed_apps.includes(one.package);
    });
  }
  if (body.action === "app_limit") {
    const one = tv.apps.find((each) => each.package === body.package);
    one.limit = body.minutes === null || body.minutes === undefined ? null : body.minutes;
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
const plain = (words) => String(words).replace(/\u00a0/g, " ");

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
const sheet = () => all(document.body, "sheet")
  .find((one) => shown(one, document.body)) || null;
const rows = () => all(screen, "app");
const names = () => rows().map((one) => plain(all(one, "ellipsis")[0].textContent));
const row = (name) => rows().find((one) =>
  plain(all(one, "ellipsis")[0].textContent) === name);
const tagOf = (name) => plain(all(row(name), "tag")[0].textContent);
const toggle = () => find(screen, (one) => one.getAttribute &&
  one.getAttribute("role") === "switch");
const allowedSent = () => sent.filter((one) => one.action === "allowed_apps");
const lastAllowed = () => allowedSent()[allowedSent().length - 1];
const limitsSent = () => sent.filter((one) => one.action === "app_limit");

const LIST = [
  app(VIDEO, "Video Player", 27, null),
  app(NETFLIX, "Stream Plus", 48, 60),
  app(SPORT, "Sport Live", 0, null),
  app(GAMES, "Games Hub", 5, null),
];

async function show(extra) {
  state = {televisions: [television(extra)], error: null};
  sent.length = 0;
  world = "at once";
  if (TS.sheet) TS.sheet.close();
  // Elsewhere and back, which builds the screen afresh.
  TS.go("now");
  TS.go("apps");
  await beat();
  await settle();
}

async function main() {
  await settle();

  process.stdout.write("\nThe list is sorted by today's use\n");
  await show({apps: [LIST[3], LIST[0], LIST[2], LIST[1]]});
  same("most minutes first", names(),
    ["Stream Plus", "Video Player", "Games Hub", "Sport Live"]);
  same("a limit is the tag", tagOf("Stream Plus"), "1 h a day");
  same("no limit and no list is Allowed", tagOf("Video Player"), "Allowed");
  same("the tile is the first letter",
    plain(all(row("Stream Plus"), "app__tile")[0].textContent), "S");
  ok("a poll changes nothing", (await beat(), await settle(), true));
  same("and the list is the same list", names(),
    ["Stream Plus", "Video Player", "Games Hub", "Sport Live"]);

  process.stdout.write("\nExempt packages never appear\n");
  await show({apps: LIST.concat([app(LAUNCHER, "Home", 90, null)])});
  ok("the launcher is not listed", !names().includes("Home"));
  same("the rest are", names().length, 4);

  process.stdout.write("\nA long name does not push the tag off the row\n");
  await show({apps: [app(VIDEO,
    "A streaming service with a name that goes on and on past the edge", 3, null)]});
  const long = rows()[0];
  const nameBox = all(long, "ellipsis")[0];
  ok("the name is the one that truncates", nameBox);
  ok("and the tag is outside it", all(long, "tag")[0] &&
    !nameBox.contains(all(long, "tag")[0]));

  process.stdout.write("\nTurning the allow-list on sends every listed app\n");
  await show({apps: LIST});
  same("off to begin with", toggle().getAttribute("aria-checked"), "false");
  fire(toggle(), "click", {});
  await settle();
  same("the whole list goes", lastAllowed(), {id: "tv1", action: "allowed_apps",
    packages: [NETFLIX, VIDEO, GAMES, SPORT]});
  same("and the switch is on", toggle().getAttribute("aria-checked"), "true");
  fire(toggle(), "click", {});
  await settle();
  same("turning it off sends an empty list", lastAllowed().packages, []);
  same("and the switch is off", toggle().getAttribute("aria-checked"), "false");

  process.stdout.write("\nBlocking one app sends the list without it\n");
  await show({apps: LIST, allowed_apps: [NETFLIX, VIDEO, GAMES]});
  same("on, so the app outside the list is Blocked", tagOf("Sport Live"), "Blocked");
  fire(row("Video Player"), "click", {});
  ok("the sheet opens", sheet());
  fire(button(sheet(), "Blocked"), "click", {});
  await settle();
  same("the list without it", lastAllowed().packages, [NETFLIX, GAMES]);
  same("and the tag says so", tagOf("Video Player"), "Blocked");
  fire(button(sheet(), "Allowed"), "click", {});
  await settle();
  same("allowing it again adds it back", lastAllowed().packages,
    [NETFLIX, GAMES, VIDEO]);

  process.stdout.write("\nWith the list off, blocking turns it on for the others\n");
  await show({apps: LIST});
  fire(row("Video Player"), "click", {});
  fire(button(sheet(), "Blocked"), "click", {});
  await settle();
  same("every other listed app is allowed", lastAllowed().packages,
    [NETFLIX, GAMES, SPORT]);
  same("and the switch is on", toggle().getAttribute("aria-checked"), "true");

  process.stdout.write("\nThe last allowed app cannot be blocked\n");
  await show({apps: LIST, allowed_apps: [NETFLIX]});
  fire(row("Stream Plus"), "click", {});
  fire(button(sheet(), "Blocked"), "click", {});
  await settle();
  same("nothing is sent, an empty list would allow everything",
    allowedSent().length, 0);
  ok("and the sheet says why", plain(sheet().textContent).indexOf("at least one") >= 0);

  process.stdout.write("\nThe sheet sets and removes a daily limit\n");
  await show({apps: LIST});
  fire(row("Video Player"), "click", {});
  ok("today and this week are in the sheet",
    plain(sheet().textContent).indexOf("27 min") >= 0);
  ok("with nothing to remove", !button(sheet(), "Remove limit"));
  ok("and nothing to take away", button(sheet(), "−").disabled);
  fire(button(sheet(), "+"), "click", {});
  await settle();
  same("the first step is an hour", limitsSent()[0],
    {id: "tv1", action: "app_limit", package: VIDEO, minutes: 60});
  same("and the tag is the limit", tagOf("Video Player"), "1 h a day");
  fire(button(sheet(), "+"), "click", {});
  await settle();
  same("then fifteen minutes at a time", limitsSent()[1].minutes, 75);
  fire(button(sheet(), "Remove limit"), "click", {});
  await settle();
  same("removing sends null", limitsSent()[2],
    {id: "tv1", action: "app_limit", package: VIDEO, minutes: null});
  same("and the tag is Allowed again", tagOf("Video Player"), "Allowed");
  ok("the sheet is still open", sheet());

  process.stdout.write("\nZero minutes is Blocked\n");
  await show({apps: [app(VIDEO, "Video Player", 27, 15)]});
  fire(row("Video Player"), "click", {});
  fire(button(sheet(), "−"), "click", {});
  await settle();
  same("zero is sent", limitsSent()[0].minutes, 0);
  same("and read as Blocked", tagOf("Video Player"), "Blocked");
  ok("with nothing lower to go", button(sheet(), "−").disabled);

  process.stdout.write("\nWhat was just set stays until the television says it\n");
  await show({apps: LIST});
  world = "silent";
  fire(toggle(), "click", {});
  await settle();
  await beat();
  await settle();
  same("a poll does not flip the switch back",
    toggle().getAttribute("aria-checked"), "true");
  now += 13000;
  await beat();
  await settle();
  same("after the wait the television has the say",
    toggle().getAttribute("aria-checked"), "false");
  world = "silent";
  fire(row("Video Player"), "click", {});
  fire(button(sheet(), "+"), "click", {});
  await settle();
  await beat();
  await settle();
  same("nor the limit", tagOf("Video Player"), "1 h a day");
  now += 13000;
  await beat();
  await settle();
  same("until the wait is up", tagOf("Video Player"), "Allowed");
  TS.sheet.close();

  process.stdout.write("\nA poll leaves the screen and the sheet alone\n");
  await show({apps: LIST});
  const first = row("Stream Plus");
  // A tap focuses what it taps; the fake DOM does not.
  row("Video Player").focus();
  fire(row("Video Player"), "click", {});
  const open = sheet();
  await beat();
  await settle();
  ok("the sheet is the same sheet", sheet() === open);
  ok("the row is the same row", row("Stream Plus") === first);
  same("and there are no more of them", rows().length, 4);
  TS.sheet.close();
  ok("closing gives the focus to the row that opened it",
    document.activeElement === row("Video Player"));

  process.stdout.write("\nA refused change goes back and says why\n");
  await show({apps: LIST});
  world = "refused";
  fire(toggle(), "click", {});
  await settle();
  same("the switch is off again", toggle().getAttribute("aria-checked"), "false");
  ok("and the refusal is on the screen",
    plain(screen.textContent).indexOf("Home Assistant said no.") >= 0);

  process.stdout.write("\nNothing to allow-list yet\n");
  await show({apps: []});
  ok("the switch cannot be turned on", toggle().disabled);
  ok("and the list says it is empty", plain(screen.textContent).indexOf("No apps") >= 0);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main().catch((error) => {
  process.stdout.write("\n" + (error && error.stack || error) + "\n");
  process.exit(1);
});
