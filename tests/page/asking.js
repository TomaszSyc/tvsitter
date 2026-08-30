"use strict";
// Choosing which phone is asked when the child asks.
//
// The automation behind this card was the one thing left that a parent had to set up
// in YAML. The add-on could do all of it long before anything on a page called it, so
// what this drives is the half that was missing: the phones are offered, what is
// already chosen comes back chosen, and what is picked is what gets posted (#104).
//
// Run by tests/test_panel_grid.py, which hands over the page.
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
    id: "tv1", name: "TV Salon", reporting: true, screen: true, locked: false,
    playing: null, pin_set: true, used_today: 0, limit_today: null,
    remaining_today: null, bonus_today: 0, used_yesterday: null,
    last_reported: null, rules_revision: 1, daily_limit: 60, sleep_timer: null,
    warn_before: null, block_settings: false,
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], week_by_app: [], allowed_apps: [], exempt_apps: [], windows: [],
    following_schedule: null, hours: blank(), pending_rules: null, trouble: [],
  }],
  error: null,
};

// What `/api/setup` says, set per scene.
let offered = {
  notify: ["notify.mobile_app_pixel_9_pro", "notify.mobile_app_pixel_watch_4"],
  televisions: [{
    id: "tv1", name: "TV Salon", ready: true, configured: false,
    notify: null, also_notify: null,
  }],
  error: null,
};
let posted = null;
let refused = null;

globalThis.document = document;
globalThis.window = {
  location: {hash: "#now"},
  addEventListener() {},
  scrollTo() {},
  innerWidth: 1200,
};
globalThis.setInterval = () => 0;
globalThis.fetch = async (url, init) => {
  if (url === "api/setup" && init && init.method === "POST") {
    posted = JSON.parse(init.body);
    if (refused) return {json: async () => ({ok: false, error: refused})};
    // What was chosen is what the next read says, the way the real one would.
    const mine = offered.televisions[0];
    mine.configured = true;
    mine.notify = posted.notify || null;
    mine.also_notify = posted.also_notify || null;
    return {json: async () => ({ok: true})};
  }
  if (url === "api/setup") return {json: async () => JSON.parse(JSON.stringify(offered))};
  return {json: async () => JSON.parse(JSON.stringify(state))};
};

new Function(fs.readFileSync(process.argv[2], "utf8"))();

const settle = async () => {
  for (let turn = 0; turn < 16; turn += 1) {
    await new Promise((go) => setTimeout(go, 0));
  }
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

  // The card is the one that names the phones; the PIN card is its neighbour.
  const cards = all(document, "card")
    .filter((one) => (one.children[0] || {}).textContent === "Asking for more time");
  ok("the card is on the page", cards.length === 1);
  const box = cards[0];
  const pickers = all(box, "name").map((one) => one.children[1]);
  const row = all(box, "row")[0];
  const button = row.children.filter((one) => one.tagName === "BUTTON")[0];
  const note = all(box, "note")[0];
  const nothing = all(box, "empty")[0];

  process.stdout.write("\nThe phones this house has\n");
  same("both pickers are offered", pickers.length, 2);
  same("each one names the phones", pickers[0].children.map((one) => one.textContent),
    ["Nobody", "Pixel 9 pro", "Pixel watch 4"]);
  same("and the second says so", pickers[1].children[0].textContent, "Nobody else");
  same("nothing is chosen to begin with", [pickers[0].value, pickers[1].value],
    ["", ""]);
  ok("the row is offered", row.hidden === false);
  ok("and nothing is being explained away", nothing.hidden === true);

  process.stdout.write("\nChoosing a phone\n");
  pickers[0].value = "notify.mobile_app_pixel_9_pro";
  pickers[1].value = "notify.mobile_app_pixel_watch_4";
  fire(button, "click", {});
  await settle();
  same("what was chosen is what was sent", posted,
    {id: "tv1", notify: "notify.mobile_app_pixel_9_pro",
      also_notify: "notify.mobile_app_pixel_watch_4"});
  ok("and it says so", note.textContent.indexOf("Saved") >= 0);
  same("what came back is what stays chosen",
    [pickers[0].value, pickers[1].value],
    ["notify.mobile_app_pixel_9_pro", "notify.mobile_app_pixel_watch_4"]);

  process.stdout.write("\nA refusal\n");
  refused = "The second device has to be a different one.";
  fire(button, "click", {});
  await settle();
  ok("is put in front of the parent in Home Assistant's own words",
    note.textContent.indexOf("has to be a different one") > 0);

  process.stdout.write("\nA house with no phone in it\n");
  refused = null;
  offered = {notify: [], televisions: offered.televisions, error: null};
  fire(document, "visibilitychange", {});
  await settle();
  // The setup is not on the five-second poll, so it is asked for the way a change asks.
  pickers[0].value = "";
  fire(button, "click", {});
  await settle();
  ok("the pickers are put away", row.hidden === true);
  ok("and the reason is said", nothing.textContent.indexOf("No phone") === 0);

  process.stdout.write("\nA television from before there were time requests\n");
  offered = {
    notify: ["notify.mobile_app_pixel_9_pro"],
    televisions: [{id: "tv1", name: "TV Salon", ready: false, configured: false,
      notify: null, also_notify: null}],
    error: null,
  };
  fire(button, "click", {});
  await settle();
  ok("has nothing to offer either", row.hidden === true);
  ok("and says which of the two it is",
    nothing.textContent.indexOf("no time request") > 0);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
