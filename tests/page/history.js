"use strict";
// The History screen: today by app and the last seven days by app.
//
// Driven through the shell. What is checked is what a parent reads — the order, the
// totals, what is left out — and that a television with no week to show, or none
// watched, says so in a sentence and never leaves a blank screen. A poll draws it
// again every five seconds, so what it draws must not pile up.
//
// Run by tests/test_page_drivers.py, which hands over the new page's scripts, joined.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, all} = require("./dom.js");

const LAUNCHER = "tv.example.launcher";

function television(extra) {
  return Object.assign({
    id: "tv1", name: "TV Lounge", reporting: true, screen: false, locked: false,
    playing: null, used_today: 0, used_yesterday: null, limit_today: 120,
    remaining_today: 120, last_reported: "2026-10-12T18:43:00", daily_limit: 120,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], allowed_apps: [], exempt_apps: [LAUNCHER], week_by_app: [],
    hours: {mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: []},
    following_schedule: null, pending_rules: null, pending_request: null,
  }, extra || {});
}

let state = {televisions: [television()], error: null};

globalThis.document = document;
globalThis.window = {location: {hash: ""}, addEventListener() {}, scrollTo() {}};
let beat = null;
globalThis.setInterval = (run) => { beat = run; return 1; };
globalThis.fetch = async () => ({json: async () => JSON.parse(JSON.stringify(state))});

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

const screen = document.getElementById("ts-screen");
const plain = (words) => String(words).replace(/ /g, " ");

/** The lists as read: each heading, its total, then its rows as "name time". */
function lists() {
  const out = [];
  all(screen, "history").forEach((root) => {
    root.children.forEach((one) => {
      if (one.classList.contains("history__head")) {
        out.push({head: plain(one.children[0].textContent),
          total: one.children[1] ? plain(one.children[1].textContent) : null,
          rows: [], says: []});
      } else if (one.classList.contains("app")) {
        out[out.length - 1].rows.push(
          plain(all(one, "ellipsis")[0].textContent) + " " +
          plain(all(one, "app__value")[0].textContent));
      } else {
        out[out.length - 1].says.push(plain(one.textContent));
      }
    });
  });
  return out;
}

async function show(extra) {
  state = {televisions: [television(extra)], error: null};
  TS.go("now");
  TS.go("history");
  await beat();
  await settle();
}

const A = (package_, name, minutes) => ({package: package_, name: name, minutes: minutes});

async function main() {
  await settle();

  process.stdout.write("\nToday and seven days are listed, longest first\n");
  await show({
    used_today: 75, used_yesterday: 90,
    apps: [A("tv.example.games", "Games Hub", 5), A("tv.example.stream", "Stream Plus", 48),
      A("tv.example.video", "Video Player", 27), A("tv.example.sport", "Sport Live", 0)],
    week_by_app: [A("tv.example.video", "Video Player", 130),
      A("tv.example.stream", "Stream Plus", 400), A("tv.example.games", "Games Hub", 20)],
  });
  const read = lists();
  same("two lists", read.map((one) => one.head), ["Today", "Last seven days"]);
  same("today, longest first, without what was not watched", read[0].rows,
    ["Stream Plus 48 min", "Video Player 27 min", "Games Hub 5 min"]);
  same("today's total is the television's own count", read[0].total, "1 h 15 min");
  same("the week, longest first", read[1].rows,
    ["Stream Plus 6 h 40 min", "Video Player 2 h 10 min", "Games Hub 20 min"]);
  same("the week's total is the sum", read[1].total, "9 h 10 min");
  same("yesterday is a line when it is known", read[1].says, ["Yesterday 1 h 30 min"]);
  same("the tile is the first letter",
    plain(all(all(screen, "app")[0], "app__tile")[0].textContent), "S");

  process.stdout.write("\nA poll draws it again and nothing piles up\n");
  await beat();
  await settle();
  same("the same lists", lists(), read);
  same("and the same number of rows", all(screen, "app").length, 6);

  process.stdout.write("\nWhat no rule reaches is left out of both\n");
  await show({
    apps: [A(LAUNCHER, "Home", 90), A("tv.example.video", "Video Player", 3)],
    week_by_app: [A(LAUNCHER, "Home", 500), A("tv.example.video", "Video Player", 9)],
  });
  same("today", lists()[0].rows, ["Video Player 3 min"]);
  same("the week", lists()[1].rows, ["Video Player 9 min"]);
  same("the total is of what is listed when the count is missing",
    [lists()[0].total, lists()[1].total], ["3 min", "9 min"]);

  process.stdout.write("\nOdd numbers are read, not trusted\n");
  await show({
    used_today: null, used_yesterday: "unavailable",
    apps: [A("tv.example.video", "Video Player", "12"), A("tv.example.stream", "Stream Plus", "x"),
      {package: "tv.example.games", minutes: 4}],
    week_by_app: [A("tv.example.video", "Video Player", "30")],
  });
  same("strings are numbers and rubbish is nothing, a nameless app has its package",
    lists()[0].rows, ["Video Player 12 min", "tv.example.games 4 min"]);
  same("no yesterday line when it is not a number", lists()[1].says, []);

  process.stdout.write("\nNothing watched says so in a sentence\n");
  await show({});
  same("today", lists()[0].says, ["Nothing watched yet today."]);
  same("and the week", lists()[1].says, ["Nothing watched in the last seven days."]);
  same("no totals where there is nothing to total",
    [lists()[0].total, lists()[1].total], [null, null]);
  await show({used_yesterday: 0});
  same("yesterday at nought is still said", lists()[1].says[0], "Yesterday 0 min");

  process.stdout.write("\nAn old integration has no week at all\n");
  await show({week_by_app: undefined, apps: [A("tv.example.video", "Video Player", 5)]});
  same("it says so in one sentence",
    lists()[1].says, ["The last seven days are not available from this television yet."]);
  same("and today is still there", lists()[0].rows, ["Video Player 5 min"]);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
