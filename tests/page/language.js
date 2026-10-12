"use strict";
// The panel, read in Polish, from the catalogue that ships with it.
//
// Every piece of this has its own test — the words are all there, the shell carries
// them, the lookup falls back — and none of them run the actual road: catalogue into
// the document, document into `SAID`, `SAID` through `phrase`, `phrase` onto what a
// parent reads. A sentence can be translated, shipped and still come out in English.
//
// So the shell is driven with the Polish words in place and each screen is read: the
// four tabs, the chooser, Now, Rules, Apps, History and Settings.
//
// Run by tests/test_page_drivers.py, which hands over the new page's scripts, joined, and
// the Polish words.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, all} = require("./dom.js");

const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

function blank() {
  const hours = {};
  WEEK.forEach((day) => { hours[day] = []; });
  return hours;
}

function television(id, name, extra) {
  return Object.assign({
    id: id, name: name, reporting: true, screen: true, locked: false,
    playing: "tv.example.video", pin_set: false, used_today: 45, limit_today: 120,
    remaining_today: 75, bonus_today: 0, used_yesterday: 90,
    last_reported: "2026-10-12T18:43:00", rules_revision: 3, daily_limit: 120,
    sleep_timer: null, warn_before: null, block_settings: false,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [{package: "tv.example.video", name: "Video Player", minutes: 45, limit: null,
      allowed: true}],
    week_by_app: [{package: "tv.example.video", name: "Video Player", minutes: 200}],
    allowed_apps: [], exempt_apps: [], windows: [], following_schedule: null,
    hours: blank(), pending_rules: null, pending_request: null, trouble: [],
  }, extra || {});
}

const state = {
  televisions: [television("tv1", "TV Lounge"), television("tv2", "TV Study")],
  error: null,
};

// The catalogue exactly as the document carries it, handed over by the test.
globalThis.SAID = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
globalThis.document = document;
globalThis.window = {
  location: {hash: ""},
  addEventListener() {},
  scrollTo() {},
  innerWidth: 1200,
};
let beat = null;
globalThis.setInterval = (run) => { beat = run; return 1; };
globalThis.fetch = async () => ({json: async () => JSON.parse(JSON.stringify(state))});

new Function(fs.readFileSync(process.argv[2], "utf8"))();
const TS = globalThis.window.TS;

const settle = async () => {
  for (let turn = 0; turn < 14; turn += 1) {
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
function has(name, where, words) {
  const right = String(where).indexOf(words) >= 0;
  if (!right) failures += 1;
  process.stdout.write((right ? "  ok   " : "  FAIL ") + name +
    (right ? "" : "\n         in   " + JSON.stringify(String(where).slice(0, 200))) +
    "\n");
}

const screen = document.getElementById("ts-screen");
const bar = document.getElementById("ts-bar");
const plain = (words) => String(words).replace(/ /g, " ");

/** Show one tab and say what the screen reads, a hard space read as a space. */
async function read(tab) {
  TS.go("now");
  TS.go(tab);
  await beat();
  await settle();
  return plain(screen.textContent);
}

async function main() {
  await settle();

  process.stdout.write("\nThe page the browser is handed\n");
  same("the destinations are named in Polish",
    bar.children.map((one) => one.textContent).join(" "),
    "Teraz Reguły Aplikacje Historia");
  const choice = all(document, "name").find((one) => one.tagName === "SELECT");
  same("so is the television chooser", choice.getAttribute("aria-label"), "Telewizor");
  same("and the gear",
    all(document.getElementById("ts-header"), "gear")[0].getAttribute("aria-label"),
    "Ustawienia");

  process.stdout.write("\nNow\n");
  const now = await read("now");
  has("the largest figure is named", now, "Zostało dziś");
  has("the day's list is headed", now, "Dziś");
  has("and it lists the app", now, "Video Player");
  has("with the minutes in the television's own length", now, "45 min");

  process.stdout.write("\nRules\n");
  const rules = await read("rules");
  has("the three sections are named", rules, "Ile");
  has("the hours", rules, "Kiedy");
  has("and the day's own", rules, "Codziennie");
  const chips = all(screen, "day");
  same("the week heads its chips in Polish",
    chips.map((one) => plain(one.textContent)).join(" "), "Pon Wt Śr Czw Pt Sob Nd");
  same("and a screen reader reads the whole name",
    chips.map((one) => one.getAttribute("aria-label")).join(" "),
    "Poniedziałek Wtorek Środa Czwartek Piątek Sobota Niedziela");
  has("an empty week explains itself in Polish", rules, "o każdej porze");

  process.stdout.write("\nApps\n");
  const apps = await read("apps");
  has("an allowed app is tagged in Polish", apps, "Dozwolona");
  has("and today's time is said", apps, "dziś 45 min");

  process.stdout.write("\nHistory\n");
  const history = await read("history");
  has("today is headed", history, "Dziś");
  has("and the week", history, "Ostatnie siedem dni");
  has("yesterday is said in Polish", history, "Wczoraj 1 h 30 min");
  state.televisions[0].week_by_app = [];
  has("an empty week says so", await read("history"),
    "W ostatnich siedmiu dniach nic nie oglądano.");
  delete state.televisions[0].week_by_app;
  has("and so does a television with no week at all", await read("history"),
    "nie podaje jeszcze danych");

  process.stdout.write("\nSettings\n");
  const settings = await read("settings");
  has("the PIN is named", settings, "PIN rodzica");

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
