// The shell around the screens: the header, the four tabs, and the beat that keeps the
// page true.
//
// Last in the load order, because it is the one script that calls all the others. A
// screen is a `render(root, tv)` and nothing more; this decides which one is shown, for
// which television, and when it is drawn again.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;
  const SVG = "http://www.w3.org/2000/svg";
  const TABS = ["now", "rules", "apps", "history"];

  // Spelled out one by one, so the catalogue test can find each name in the source.
  const LABELS = {
    now: phrase("Now"),
    rules: phrase("Rules"),
    apps: phrase("Apps"),
    history: phrase("History"),
  };

  const header = document.getElementById("ts-header");
  const offline = document.getElementById("ts-offline");
  const screen = document.getElementById("ts-screen");
  const bar = document.getElementById("ts-bar");

  // The television's mark: a ring with a wedge of the dial filled, on a mint disc.
  const DIAL = [
    ["circle", {cx: 16, cy: 16, r: 16, fill: "currentColor", "fill-opacity": 0.18}],
    ["circle", {cx: 16, cy: 16, r: 9, fill: "none", stroke: "currentColor",
      "stroke-width": 2.5}],
    ["path", {d: "M16 16V10A6 6 0 0 1 21.2 19Z", fill: "currentColor"}],
  ];

  const LINE = {fill: "none", stroke: "currentColor", "stroke-width": 1.8,
    "stroke-linecap": "round", "stroke-linejoin": "round"};
  const ICONS = {
    now: [["rect", {x: 3, y: 5, width: 18, height: 12, rx: 2}], ["path", {d: "M8 21h8"}]],
    rules: [["circle", {cx: 12, cy: 12, r: 9}], ["path", {d: "M12 7v5l3 2"}]],
    apps: [[4, 4], [14, 4], [4, 14], [14, 14]].map(([x, y]) =>
      ["rect", {x: x, y: y, width: 6, height: 6, rx: 1.5}]),
    history: [["path", {d: "M5 20v-7M12 20V5M19 20v-10"}]],
  };

  /** A cog of eight teeth, worked out rather than copied from an icon set. */
  function cog() {
    const at = (radius, degrees) => {
      const turn = (degrees * Math.PI) / 180;
      return (12 + radius * Math.sin(turn)).toFixed(2) + " " +
        (12 - radius * Math.cos(turn)).toFixed(2);
    };
    const points = [];
    for (let tooth = 0; tooth < 8; tooth += 1) {
      const middle = tooth * 45;
      points.push(at(7.4, middle - 17), at(10, middle - 8), at(10, middle + 8),
        at(7.4, middle + 17));
    }
    return [["path", {d: "M" + points.join("L") + "Z"}],
      ["circle", {cx: 12, cy: 12, r: 3}]];
  }

  /** Draw a mark from shapes. Static geometry only: nothing read from anywhere. */
  function mark(shapes, box, style) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", box);
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    Object.keys(style || {}).forEach((name) => svg.setAttribute(name, style[name]));
    shapes.forEach(([tag, values]) => {
      const shape = document.createElementNS(SVG, tag);
      Object.keys(values).forEach((name) => shape.setAttribute(name, values[name]));
      svg.appendChild(shape);
    });
    return svg;
  }

  function element(tag, name) {
    const made = document.createElement(tag);
    if (name) made.className = name;
    return made;
  }

  let tab = "now";
  let cameFrom = "now";
  let drawnFor = null;
  let named = "";

  // The header. Built once; only the name and the status change afterwards.
  const dial = mark(DIAL, "0 0 32 32");
  dial.classList.add("dial");
  const who = element("div", "who");
  const title = element("h1", "title name");
  const said = element("p", "status");
  said.hidden = true;
  const gear = element("button", "gear");
  gear.setAttribute("type", "button");
  gear.setAttribute("aria-label", phrase("Settings"));
  gear.appendChild(mark(cog(), "0 0 24 24", LINE));
  gear.addEventListener("click", () => TS.go("settings"));
  who.append(title, said);
  header.replaceChildren(dial, who, gear);

  // The tabs, under the thumb.
  bar.setAttribute("aria-label", phrase("Sections"));
  const buttons = {};
  TABS.forEach((name) => {
    const button = element("button", "tab");
    button.setAttribute("type", "button");
    button.setAttribute("data-tab", name);
    const label = element("span");
    label.textContent = LABELS[name];
    button.append(mark(ICONS[name], "0 0 24 24", LINE), label);
    button.addEventListener("click", () => TS.go(name));
    buttons[name] = button;
  });
  bar.replaceChildren(...TABS.map((name) => buttons[name]));

  /**
   * What the set is doing, in the fewest words: one line under its name.
   *
   * Amber for the two states a parent may need to act on — a set that is locked and
   * one that has stopped answering — so the header says so on every screen, not only
   * on Now. A lock gives its reason, which is what anybody looking wants to know next.
   */
  TS.status = function status(tv) {
    if (!tv.reporting) {
      const seen = TS.seen(tv.last_reported);
      return {words: seen ? phrase("Not reachable since {when}", {when: seen}) :
        phrase("Not reporting"), tone: "warn"};
    }
    if (tv.locked) return {words: TS.screens.now.reason(tv), tone: "warn"};
    if (tv.playing) {
      const app = (tv.apps || []).find((one) => one.package === tv.playing);
      const named = (app && app.name) || String(tv.playing);
      const minutes = app ? TS.number(app.minutes) : null;
      return {words: minutes ? phrase("{app} \u00b7 {time} today",
        {app: named, time: TS.length(minutes)}) : named, tone: "on"};
    }
    return {words: phrase(tv.screen ? "Screen on" : "Screen off"),
      tone: tv.screen ? "on" : "off"};
  };

  /**
   * The name in the header, or a choice of names when there is more than one set.
   *
   * Rebuilt only when the televisions themselves change, and never while the choice
   * has the focus: a poll landing while the list is open would close it under a thumb.
   */
  function name(list, tv) {
    const key = list.map((one) => one.id + "\u0000" + one.name).join("\u0001");
    const choice = title.children[0];
    if (key === named) {
      if (choice && document.activeElement !== choice) choice.value = TS.state.current;
      return;
    }
    if (choice && document.activeElement === choice) return;
    named = key;
    if (list.length < 2) {
      title.className = "title name";
      title.textContent = tv ? tv.name : "";
      return;
    }
    const select = element("select", "name");
    select.setAttribute("aria-label", phrase("Television"));
    list.forEach((one) => {
      const option = element("option");
      option.value = one.id;
      option.textContent = one.name;
      select.appendChild(option);
    });
    select.value = TS.state.current;
    select.addEventListener("change", () => {
      TS.state.current = select.value;
      paint(false);
      draw(true);
    });
    title.className = "title";
    title.replaceChildren(select);
  }

  /** Whether somebody is typing into the screen, which a redraw would take from them. */
  function typing() {
    const active = document.activeElement;
    return Boolean(active && active !== document.body && screen.contains(active) &&
      /^(INPUT|SELECT|TEXTAREA)$/.test(active.tagName));
  }

  /**
   * Draw the current screen for the current television.
   *
   * From empty when the parent has gone somewhere else; otherwise on top of what is
   * there, because a screen redraws itself in place and keeps what a parent is
   * holding — an open choice, a half-made change.
   */
  function draw(fresh) {
    const tv = TS.tv();
    if (!tv) {
      drawnFor = null;
      if (!TS.state.loaded) return;
      const none = element("p", "empty");
      none.textContent = phrase("No televisions yet: add the TV Sitter integration first.");
      screen.replaceChildren(none);
      return;
    }
    if (fresh || drawnFor !== tv.id) screen.replaceChildren();
    drawnFor = tv.id;
    TS.screens[tab].render(screen, tv);
  }

  /** Put what was read on the page; redraw the screen only when something new was. */
  function paint(read) {
    offline.textContent = TS.state.error || "";
    offline.hidden = !TS.state.error;
    const tv = TS.tv();
    name(TS.state.televisions, tv);
    const now = tv ? TS.status(tv) : null;
    said.textContent = now ? now.words : "";
    said.setAttribute("data-tone", now ? now.tone : "off");
    said.hidden = !now;
    // The mark goes grey with a set that has stopped answering, as the lock screen's
    // dial does with a television that is off.
    dial.classList.toggle("dial--away", Boolean(tv && !tv.reporting));
    if (read && !typing()) draw(false);
  }

  /** Show one screen: a tab, or the settings behind the gear. */
  TS.go = function go(where) {
    if (!TS.screens[where]) return;
    if (where === "settings" && tab !== "settings") cameFrom = tab;
    tab = where;
    TS.tab = where;
    TABS.forEach((one) => {
      if (one === where) buttons[one].setAttribute("aria-current", "page");
      else buttons[one].removeAttribute("aria-current");
    });
    draw(true);
    // A screen is a fresh page to whoever asked for it, and being dropped halfway down
    // one is not that.
    if (window.scrollTo) window.scrollTo(0, 0);
  };

  /** Leave the settings for the tab they were opened from. */
  TS.back = function back() {
    TS.go(cameFrom);
  };

  /** Read the state and put it on the page; what `act` waits for before it answers. */
  TS.refresh = async function refresh() {
    paint(await TS.api.state());
  };

  function beat() {
    // A panel in a pocket is a panel nobody is reading, and a phone's battery is worth
    // more than a figure that is five seconds fresher than the moment it is looked at.
    if (document.hidden) return undefined;
    return TS.refresh();
  }

  TS.go("now");
  document.addEventListener("visibilitychange", beat);
  setInterval(beat, TS.api.POLL_MS);
  TS.refresh();
})();
