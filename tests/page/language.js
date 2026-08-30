"use strict";
// The page, read in Polish, from the catalogue that ships with it.
//
// Every piece of this has its own test — the words are all there, the shell carries
// them, the lookup falls back — and none of them run the actual road: catalogue into
// the document, document into `SAID`, `SAID` through `phrase`, `phrase` onto a box a
// parent reads. A sentence can be translated, shipped and still come out in English.
//
// Run by tests/test_panel_grid.py, which hands over the page and the Polish words.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, fire, all} = require("./dom.js");

const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

function blank() {
  const hours = {};
  WEEK.forEach((day) => { hours[day] = []; });
  return hours;
}

const state = {
  televisions: [{
    id: "tv1", name: "TV Salon", reporting: false, screen: false, locked: true,
    playing: null, pin_set: false, used_today: 0, limit_today: null,
    remaining_today: null, bonus_today: 0, used_yesterday: null,
    last_reported: null, rules_revision: 3, daily_limit: 60, sleep_timer: null,
    warn_before: null, block_settings: false,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], week_by_app: [], allowed_apps: [], exempt_apps: [], windows: [],
    following_schedule: null, hours: blank(), pending_rules: null, trouble: [],
  }],
  error: null,
};

// The catalogue exactly as the document carries it, handed over by the test.
globalThis.SAID = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
globalThis.document = document;
globalThis.window = {
  location: {hash: "#rules"},
  addEventListener() {},
  scrollTo() {},
  innerWidth: 1200,
};
globalThis.setInterval = () => 0;
globalThis.fetch = async () => ({json: async () => JSON.parse(JSON.stringify(state))});

new Function(fs.readFileSync(process.argv[2], "utf8"))();

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
    (right ? "" : "\n         in   " + JSON.stringify(String(where).slice(0, 160))) +
    "\n");
}

async function main() {
  await settle();

  process.stdout.write("\nThe page the browser is handed\n");
  same("the destinations are named in Polish",
    ["now", "today", "rules", "apps"]
      .map((one) => document.getElementById("go-" + one).children[1].textContent)
      .join(" "),
    "Teraz Dziś Reguły Aplikacje");
  same("so is the television chooser",
    document.getElementById("which").textContent, "Telewizor");
  has("and the sentence under the title",
    document.getElementById("lead").textContent, "Wszystko tutaj pochodzi");

  process.stdout.write("\nThe cards a parent reads\n");
  // Every destination is built, not only the one on the screen, so this is the whole
  // page's worth of cards and the three that matter are read out of the middle of it.
  const titles = all(document, "card")
    .map((one) => (one.children[0] || {}).textContent)
    .filter(Boolean)
    .join(" | ");
  has("the three rules cards are named", titles,
    "Codziennie | Tydzień | Godziny");
  has("and so is the one the PIN is set in", titles, "PIN rodzica");

  const names = all(document, "names")[0].children
    .filter((one) => one.classList.contains("day"))
    .map((one) => one.textContent);
  same("the week heads its columns in Polish", names.join(" "),
    "Pon Wt Śr Czw Pt Sob Nd");

  const empty = all(document, "empty")
    .map((one) => one.textContent)
    .filter((one) => one.indexOf("półgodzina") >= 0);
  same("an empty grid explains itself in Polish", empty.length, 1);

  process.stdout.write("\nWhat is said over the boxes while they are drawn\n");
  const grid = all(document, "week")[0];
  const cells = grid.children.filter((one) => one.classList.contains("cell"));
  const range = all(grid.parentNode.parentNode, "range")[0];
  document.elementFromPoint = () => null;
  fire(cells[32], "pointerdown", {
    target: cells[32], pointerId: 1, clientX: 300, clientY: 400,
  });
  has("the readout is Polish too", range.textContent, "Zezwól Poniedziałek");
  fire(grid, "pointerup", {pointerId: 1});

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
