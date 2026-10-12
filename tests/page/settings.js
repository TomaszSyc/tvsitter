"use strict";
// The Settings screen behind the gear: the parent's PIN and where requests go, the
// television's own switches, and what it last said about itself.
//
// Driven through the shell the way a phone drives it. It carries over what the old
// notification card was checked for — the phones offered, what is chosen coming back
// chosen, a refusal in Home Assistant's words — and adds what is new here: a PIN that
// is four digits before it leaves, never kept in its field, and a removal that asks
// twice. The setup is read from its own address and not from the five-second poll.
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
const now = new RealDate(2026, 9, 12, 18, 44, 0).getTime();
class StillDate extends RealDate {
  constructor(...given) {
    if (given.length) super(...given);
    else super(now);
  }
  static now() { return now; }
}
globalThis.Date = StillDate;

function television(extra) {
  return Object.assign({
    id: "tv1", name: "TV Lounge", reporting: true, screen: false, locked: false,
    playing: null, pin_set: true, used_today: 0, limit_today: 120,
    remaining_today: 120, last_reported: "2026-10-12T18:43:40", daily_limit: 120,
    sleep_timer: null, warn_before: 5, block_settings: true, version: "0.11.19",
    week: {mon: null, tue: null, wed: null, thu: null, fri: null, sat: null,
      sun: null},
    apps: [], allowed_apps: [], exempt_apps: [], week_by_app: [],
    hours: {mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: []},
    following_schedule: null, pending_rules: null, pending_request: null,
  }, extra || {});
}

let state = {televisions: [television()], error: null};
// What `/api/setup` says, set per scene.
let offered = null;
let posted = null;
let refused = null;
let setups = 0;
const sent = [];

const phones = () => ({
  notify: ["notify.mobile_app_phone", "notify.mobile_app_watch"],
  televisions: [{id: "tv1", name: "TV Lounge", ready: true, configured: false,
    notify: null, also_notify: null}],
  error: null,
});

function serve(body) {
  sent.push(body);
  const tv = state.televisions[0];
  if (body.action === "block_settings") tv.block_settings = Boolean(body.on);
  if (body.action === "number") tv[body.key] = body.value;
  if (body.action === "set_pin") tv.pin_set = true;
  if (body.action === "clear_pin") tv.pin_set = false;
  if (body.action === "stop_following") tv.following_schedule = null;
  return {ok: true};
}

globalThis.document = document;
globalThis.window = {location: {hash: ""}, addEventListener() {}, scrollTo() {}};
globalThis.setInterval = () => 0;
globalThis.fetch = async (url, init) => {
  if (url === "api/do") return {json: async () => serve(JSON.parse(init.body))};
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
  if (url === "api/setup") {
    setups += 1;
    return {json: async () => JSON.parse(JSON.stringify(offered))};
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
const button = (label) => find(screen, (one) => one.tagName === "BUTTON" &&
  plain(one.textContent) === label && shown(one, screen));
const labelled = (label) => find(screen, (one) => one.getAttribute &&
  one.getAttribute("aria-label") === label);
const texts = (name) => all(screen, name).map((one) => plain(one.textContent));
// The value on the row that carries a title, as a parent reads the pair.
const valueOf = (title) => {
  const row = all(screen, "set").find((one) =>
    plain(all(one, "set__title")[0].textContent) === title);
  return row ? plain(all(row, "set__value")[0].textContent) : null;
};
const noteOf = (name) => all(screen, name).filter((one) => shown(one, screen))
  .map((one) => plain(one.textContent)).join("|");

async function open(extra, setup) {
  state = {televisions: [television(extra)], error: null};
  offered = setup || phones();
  sent.length = 0;
  posted = null;
  refused = null;
  setups = 0;
  await TS.refresh();
  TS.go("rules");
  TS.go("settings");
  await settle();
}

async function main() {
  await settle();

  process.stdout.write("\nThe screen\n");
  await open();
  same("three groups, in order", texts("group"), ["Parent", "Television", "Status"]);
  same("the gear opens it with no tab current", TS.tab, "settings");
  same("the setup is read once when it opens", setups, 1);
  await TS.refresh();
  await settle();
  same("and not again on a poll", setups, 1);
  same("a poll does not draw it twice", texts("group").length, 3);

  process.stdout.write("\nThe phones this house has\n");
  const first = labelled("Send time requests to");
  const second = labelled("Second device");
  ok("both pickers are offered", first && second);
  same("each one names the phones", first.children.map((one) => one.textContent),
    ["Nobody", "Phone", "Watch"]);
  same("and the second says so", second.children[0].textContent, "Nobody else");
  same("nothing is chosen to begin with", [first.value, second.value], ["", ""]);
  ok("the pickers are offered", shown(first, screen));
  same("and nothing is being explained away", noteOf("empty"), "");

  process.stdout.write("\nChoosing a phone\n");
  first.value = "notify.mobile_app_phone";
  second.value = "notify.mobile_app_watch";
  fire(button("Save"), "click", {});
  await settle();
  same("what was chosen is what was sent", posted,
    {id: "tv1", notify: "notify.mobile_app_phone",
      also_notify: "notify.mobile_app_watch"});
  ok("and it says so", noteOf("note").indexOf("Saved") >= 0);
  same("what came back is what stays chosen", [first.value, second.value],
    ["notify.mobile_app_phone", "notify.mobile_app_watch"]);
  first.value = "notify.mobile_app_watch";
  second.value = "";
  fire(button("Save"), "click", {});
  await settle();
  same("a second device can be taken away again", posted,
    {id: "tv1", notify: "notify.mobile_app_watch", also_notify: ""});

  process.stdout.write("\nNobody is refused in words\n");
  refused = "The second device has to be a different one.";
  second.value = "notify.mobile_app_watch";
  fire(button("Save"), "click", {});
  await settle();
  ok("Home Assistant's own words reach the parent",
    noteOf("note").indexOf("has to be a different one") >= 0);
  refused = "A device to ask has to be chosen first.";
  first.value = "";
  fire(button("Save"), "click", {});
  await settle();
  ok("and so does being asked to choose one",
    noteOf("note").indexOf("has to be chosen first") >= 0);

  process.stdout.write("\nA house with no phone in it\n");
  await open(null, {notify: [], televisions: phones().televisions, error: null});
  ok("the pickers are put away", !shown(labelled("Send time requests to"), screen));
  ok("and the reason is said", noteOf("empty").indexOf("No phone") === 0);

  process.stdout.write("\nA television from before there were time requests\n");
  const old = phones();
  old.televisions[0].ready = false;
  await open(null, old);
  ok("has nothing to offer either", !shown(labelled("Send time requests to"), screen));
  ok("and says which of the two it is", noteOf("empty").indexOf("no time request") > 0);

  process.stdout.write("\nAn add-on that does not answer\n");
  await open(null, {error: "The panel could not reach the add-on."});
  ok("says so instead of offering nothing silently",
    noteOf("empty").indexOf("could not reach") >= 0);

  process.stdout.write("\nA PIN is four digits before it is sent\n");
  await open();
  const pin = labelled("New PIN");
  same("it is a password field that asks for digits",
    [pin.type, pin.inputMode, pin.autocomplete], ["password", "numeric", "off"]);
  pin.value = "12a4";
  fire(button("Set the PIN"), "click", {});
  await settle();
  same("letters are refused and nothing is sent", sent, []);
  ok("in words", noteOf("note").indexOf("A PIN is four digits.") >= 0);
  same("and the field is emptied", pin.value, "");
  pin.value = "123";
  fire(button("Set the PIN"), "click", {});
  await settle();
  same("three digits are refused too", sent, []);
  pin.value = "1234";
  fire(button("Set the PIN"), "click", {});
  await settle();
  same("four digits are sent as a PIN", sent,
    [{id: "tv1", action: "set_pin", pin: "1234"}]);
  same("and the field is emptied again", pin.value, "");
  ok("the PIN is said to be set", noteOf("note").indexOf("PIN set") >= 0);
  same("the row says so as well", valueOf("Parent PIN"), "Set");
  pin.value = "98";
  await TS.refresh();
  await settle();
  same("a poll leaves what is being typed", pin.value, "98");

  process.stdout.write("\nRemoving the PIN asks twice\n");
  sent.length = 0;
  fire(button("Remove the PIN"), "click", {});
  await settle();
  same("one tap sends nothing", sent, []);
  ok("and asks", button("Yes, remove it") && button("Keep it"));
  fire(button("Keep it"), "click", {});
  await settle();
  same("keeping it sends nothing", sent, []);
  ok("and puts the question away", !button("Yes, remove it"));
  fire(button("Remove the PIN"), "click", {});
  fire(button("Yes, remove it"), "click", {});
  await settle();
  same("the second tap removes it", sent, [{id: "tv1", action: "clear_pin"}]);
  same("the row says there is none", valueOf("Parent PIN"), "Not set");
  ok("and there is nothing left to remove", !button("Remove the PIN"));

  process.stdout.write("\nThe television's switches\n");
  await open();
  const warn = labelled("Warning before the end");
  same("the warning is what the television has", warn.value, "5");
  warn.value = "10";
  fire(warn, "change", {});
  await settle();
  same("a new warning goes out as minutes", sent,
    [{id: "tv1", action: "number", key: "warn_before", value: 10}]);
  const block = labelled("Block Settings on the television");
  same("blocking is on, as the television says",
    [block.getAttribute("role"), block.getAttribute("aria-checked")],
    ["switch", "true"]);
  fire(block, "click", {});
  await settle();
  same("turning it off is sent as off", sent[1],
    {id: "tv1", action: "block_settings", on: false});
  same("and the switch follows what the television then says",
    labelled("Block Settings on the television").getAttribute("aria-checked"),
    "false");
  await open({warn_before: 7});
  same("a warning the list does not offer is still shown",
    labelled("Warning before the end").value, "7");

  process.stdout.write("\nA choice made in a list lets go of the focus\n");
  await open();
  const chosen = labelled("Warning before the end");
  // A phone's web view keeps the focus on a list after a choice, and the shell then
  // took the parent for somebody still typing and stopped drawing the screen.
  chosen.focus();
  chosen.value = "10";
  fire(chosen, "change", {});
  await settle();
  ok("the list no longer holds the focus", document.activeElement !== chosen);
  state.televisions[0].warn_before = 15;
  state.televisions[0].version = "0.11.40";
  await TS.refresh();
  await settle();
  same("so the next read is drawn", valueOf("Version on the television"), "0.11.40");
  same("and the list shows what the television now says",
    labelled("Warning before the end").value, "15");

  process.stdout.write("\nA change held for a sleeping set is what is shown\n");
  const heldLine = () => all(screen, "held-line").filter((one) => shown(one, screen));
  await open();
  same("nothing held, no amber line", heldLine().length, 0);
  await open({reporting: false,
    pending_rules: {warn_before_s: 600, block_settings: false}});
  same("the held warning is the one shown",
    labelled("Warning before the end").value, "10");
  same("the held switch is the one shown",
    labelled("Block Settings on the television").getAttribute("aria-checked"), "false");
  same("with the amber line", heldLine().map((one) => plain(one.textContent)),
    ["The television is asleep. The change goes when it wakes."]);
  await open({reporting: false, block_settings: false,
    pending_rules: {block_settings: true}});
  same("a held block turns the switch on",
    labelled("Block Settings on the television").getAttribute("aria-checked"), "true");
  await open({reporting: false, pending_rules: {daily_limit_s: 3600}});
  same("a change to another rule draws no line here", heldLine().length, 0);

  process.stdout.write("\nHours from a schedule\n");
  await open();
  same("not followed, it says off", valueOf("Hours from a Home Assistant schedule"), "Off");
  ok("and offers nothing to stop", !button("Stop following"));
  await open({following_schedule: "schedule.viewing_hours"});
  same("followed, it names the helper", valueOf("Hours from a Home Assistant schedule"),
    "schedule.viewing_hours");
  fire(button("Stop following"), "click", {});
  await settle();
  same("stopping goes out as stopping", sent,
    [{id: "tv1", action: "stop_following"}]);
  same("and it is off afterwards", valueOf("Hours from a Home Assistant schedule"), "Off");

  process.stdout.write("\nStatus\n");
  await open();
  same("the version on the television", valueOf("Version on the television"),
    "0.11.19");
  same("the last report is said as a time ago", valueOf("Last report"), "just now");
  await open({last_reported: "2026-10-12T18:39:00"});
  same("five minutes", valueOf("Last report"), "5 min ago");
  await open({last_reported: null, version: null});
  same("nothing reported is a dash", valueOf("Last report"), "—");
  same("and so is no version", valueOf("Version on the television"), "—");

  process.stdout.write("\nBack\n");
  await open();
  TS.go("apps");
  TS.go("settings");
  fire(button("Back"), "click", {});
  same("returns to the tab it came from", TS.tab, "apps");
  ok("and the settings are gone from the screen", texts("group").length === 0);

  process.stdout.write(failures ? "\n" + failures + " failed\n" : "\nall held\n");
  process.exit(failures ? 1 : 0);
}

main();
