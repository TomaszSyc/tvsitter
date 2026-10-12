"use strict";
// The shell around the screens: the header, the four tabs, the polling and the line
// that says Home Assistant has gone quiet.
//
// The screens themselves are stand-ins here — each one only notes that it was asked to
// draw, and for which television. What is checked is what the shell promises every
// screen: it is drawn into the same place, with the television the parent picked, again
// on every poll, but never while somebody is typing into it and never with an empty
// state because one poll failed.
//
// Run by tests/test_page_drivers.py, which hands over the new page's scripts, joined.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

const fs = require("fs");
const {document, fire} = require("./dom.js");

function television(id, name) {
  return {
    id: id, name: name, reporting: true, screen: true, locked: false,
    playing: null, apps: [],
  };
}

let state = {televisions: [television("tv1", "TV Lounge")], error: null};
const sent = [];
let failing = false;

globalThis.document = document;
globalThis.window = {location: {hash: ""}, addEventListener() {}};
let beat = null;
let every = null;
globalThis.setInterval = (run, ms) => { beat = run; every = ms; return 1; };
globalThis.fetch = async (url, options) => {
  sent.push({url: url, options: options || {}});
  if (failing) throw new TypeError("Failed to fetch");
  if (url === "api/do") return {json: async () => ({ok: true})};
  return {json: async () => JSON.parse(JSON.stringify(state))};
};

new Function(fs.readFileSync(process.argv[2], "utf8"))();
const TS = window.TS;

// Stand-ins for the screens, put in before the first poll lands.
const drawn = [];
["now", "rules", "apps", "history", "settings"].forEach((name) => {
  TS.screens[name].render = (root, tv) => {
    drawn.push({name: name, root: root, tv: tv});
    const mark = document.createElement("p");
    mark.textContent = name + ":" + tv.id;
    root.appendChild(mark);
  };
});

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

const header = document.getElementById("ts-header");
const offline = document.getElementById("ts-offline");
const screen = document.getElementById("ts-screen");
const bar = document.getElementById("ts-bar");

function find(node, test) {
  if (test(node)) return node;
  for (const one of node.children) {
    const found = find(one, test);
    if (found) return found;
  }
  return null;
}
const tab = (name) => find(bar, (one) => one.tagName === "BUTTON" &&
  one.getAttribute("data-tab") === name);
const current = () => ["now", "rules", "apps", "history"].filter((name) =>
  tab(name).getAttribute("aria-current") === "page");
const chooser = () => find(header, (one) => one.tagName === "SELECT");
const last = () => drawn[drawn.length - 1];

async function main() {
  await settle();

  process.stdout.write("\nThe shell as it first opens\n");
  same("polls every five seconds", every, 5000);
  same("four tabs, Now first and current", current().join(","), "now");
  same("each tab is labelled", ["now", "rules", "apps", "history"].map((name) =>
    tab(name).textContent).join(","), "Now,Rules,Apps,History");
  const gear = find(header, (one) => one.tagName === "BUTTON");
  same("the gear says what it opens", gear && gear.getAttribute("aria-label"),
    "Settings");
  same("one television is a name, not a choice", chooser(), null);
  same("the name is in the header", header.textContent.indexOf("TV Lounge") >= 0,
    true);
  same("Now is drawn for that television", last() && last().name + ":" +
    last().tv.id, "now:tv1");
  same("into the screen area", last() && last().root, screen);
  same("nothing says the connection is lost", offline.hidden, true);

  process.stdout.write("\nMoving between tabs\n");
  fire(tab("rules"), "click");
  same("Rules becomes current", current().join(","), "rules");
  same("Rules is drawn", last().name, "rules");
  same("the screen holds only Rules", screen.textContent, "rules:tv1");

  process.stdout.write("\nA poll while somebody types\n");
  const field = document.createElement("input");
  screen.appendChild(field);
  field.focus();
  let before = drawn.length;
  await beat();
  await settle();
  same("the screen is left alone", drawn.length, before);
  field.blur();
  await beat();
  await settle();
  same("and drawn again once they stop", drawn.length, before + 1);

  process.stdout.write("\nA poll that fails\n");
  const kept = screen.textContent;
  before = drawn.length;
  failing = true;
  await beat();
  await settle();
  failing = false;
  same("a line says so", offline.hidden, false);
  same("in words", offline.textContent, "No connection to Home Assistant");
  same("the television is kept", TS.state.televisions.length, 1);
  same("the screen is not redrawn", drawn.length, before);
  same("and keeps what it had", screen.textContent, kept);
  await beat();
  await settle();
  same("the line goes once Home Assistant answers", offline.hidden, true);

  process.stdout.write("\nAn answer that carries no televisions and a reason\n");
  const good = state;
  state = {televisions: [],
    error: "Home Assistant did not answer. It may still be starting."};
  await beat();
  await settle();
  same("the reason is the line", offline.textContent,
    "Home Assistant did not answer. It may still be starting.");
  same("the last televisions are kept", TS.state.televisions.length, 1);
  state = good;
  await beat();
  await settle();

  process.stdout.write("\nTwo televisions\n");
  state = {televisions: [television("tv1", "TV Lounge"),
    television("tv2", "TV Study")], error: null};
  await beat();
  await settle();
  const select = chooser();
  same("the name becomes a choice", Boolean(select), true);
  same("of both", select && select.children.map((one) => one.textContent).join(","),
    "TV Lounge,TV Study");
  same("showing the one being looked at", select && select.value, "tv1");
  select.value = "tv2";
  fire(select, "change");
  same("choosing switches the television", TS.state.current, "tv2");
  same("and the screen is drawn for it", last().tv.id, "tv2");
  same("from empty", screen.textContent, "rules:tv2");
  await beat();
  await settle();
  same("a poll keeps the choice", TS.state.current, "tv2");

  process.stdout.write("\nSettings, from the gear, and back\n");
  fire(find(header, (one) => one.tagName === "BUTTON"), "click");
  same("settings are drawn", last().name, "settings");
  same("no tab is current", current().join(","), "");
  TS.back();
  same("back returns to the tab it came from", last().name, "rules");
  same("which is current again", current().join(","), "rules");

  process.stdout.write("\nA change sent\n");
  sent.length = 0;
  const answer = await TS.api.act({action: "lock", id: "tv2"});
  same("goes to api/do", sent[0].url, "api/do");
  same("as a POST", sent[0].options.method, "POST");
  same("carrying the change", sent[0].options.body,
    JSON.stringify({action: "lock", id: "tv2"}));
  same("and the state is read back before answering", sent.length >= 2 &&
    sent[1].url, "api/state");
  same("the answer is handed back", answer.ok, true);
  sent.length = 0;
  failing = true;
  const lost = await TS.api.act({action: "lock", id: "tv2"});
  failing = false;
  same("an unreachable add-on is an answer, not an exception", lost.ok, false);
  same("with a reason in words", lost.error,
    "The panel could not reach the add-on.");

  process.stdout.write("\nA panel in a pocket\n");
  document.hidden = true;
  sent.length = 0;
  await beat();
  await settle();
  same("asks nothing", sent.length, 0);
  document.hidden = false;

  process.stdout.write("\nEvery television removed\n");
  state = {televisions: [], error: null};
  await beat();
  await settle();
  same("says what to do", screen.textContent,
    "No televisions yet: add the TV Sitter integration first.");

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall good\n");
  process.exit(failures ? 1 : 0);
}

main().catch((failure) => {
  process.stdout.write(String(failure && failure.stack || failure) + "\n");
  process.exit(1);
});
