// The Apps screen: what the television can open, and what each app is allowed.
//
// A switch at the top turns the allow-list on, and under it every app the set knows,
// the one used most today first, with the state it is in: allowed, blocked, or the
// daily limit it has. Tapping an app opens a sheet to allow or block it and to set or
// remove its limit.
//
// The allow-list is one list on the television and every change sends the whole of it,
// so blocking an app is the list without it. An empty list means nothing is chosen and
// every app opens (D27), which is why the last allowed app cannot be blocked here: that
// would not block everything, it would allow everything.
//
// What a parent just set is kept on the screen until the television reports it back,
// the way the Rules screen keeps a limit, so a poll landing while the change travels
// does not put the old state back under a thumb. The sheet is built once and updated in
// place, and a poll never closes it.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;

  // The steps a limit moves in, and its ceiling: the same as a day's limit has.
  const STEP = 15;
  const MAX_LIMIT = 720;
  // Where a limit starts from when there is none to step from: an hour is a budget a
  // parent can see and correct, where fifteen minutes would lock an app mid-programme.
  const FIRST_LIMIT = 60;
  // How long a change made here stays on the screen while the television has yet to
  // report it back; the Rules screen's wait, for the same reasons.
  const AGREE_MS = 12000;

  // What was saved from here and has not come back yet, per television, so moving to
  // another tab and back inside the gap does not paint the old state either.
  const savedLists = {};
  const savedLimits = {};

  function element(tag, name, words) {
    const made = document.createElement(tag);
    if (name) made.className = name;
    if (words !== undefined) made.textContent = words;
    return made;
  }

  function pill(words, name) {
    const made = element("button", "pill" + (name ? " " + name : ""), words);
    made.setAttribute("type", "button");
    return made;
  }

  /** A line under a control: an error in rose, a plain report quietly. */
  function say(note, words, quiet) {
    note.textContent = words || "";
    note.hidden = !words;
    note.classList.toggle("note--quiet", Boolean(quiet));
  }

  /** The amber line that says a change shown here is waiting for the set. */
  function heldLine() {
    const made = element("p", "held-line",
      phrase("The television is asleep. The change goes when it wakes."));
    made.hidden = true;
    return made;
  }

  function note() {
    const made = element("p", "note");
    made.setAttribute("role", "status");
    made.hidden = true;
    return made;
  }

  // ---- What the television reports, with what was just set laid over it. ----

  /** The apps to list: today's, without what no rule reaches, the most used first. */
  function listed(tv) {
    const exempt = Array.isArray(tv.exempt_apps) ? tv.exempt_apps : [];
    const apps = Array.isArray(tv.apps) ? tv.apps : [];
    return apps
      .filter((one) => one && one.package && !exempt.includes(one.package))
      .map((one) => ({
        package: one.package,
        name: String(one.name || one.package),
        minutes: TS.number(one.minutes) || 0,
        limit: TS.number(one.limit),
      }))
      .sort((one, other) => other.minutes - one.minutes ||
        (one.name < other.name ? -1 : one.name > other.name ? 1 : 0));
  }

  function sameSet(one, other) {
    return one.length === other.length && one.every((item) => other.includes(item));
  }

  /** The allow-list the set has, or the one waiting for it when the set is asleep. */
  function listOf(tv) {
    const held = TS.held(tv, "apps_allowed");
    if (held !== undefined) return Array.isArray(held) ? held.map(String) : [];
    return Array.isArray(tv.allowed_apps) ? tv.allowed_apps : [];
  }

  /** An app's own limit in minutes as the set has it, or as a held change will have it. */
  function heldLimit(tv, one) {
    const held = TS.held(tv, "app_limits_s");
    if (held === undefined) return one.limit;
    // A null on the whole map is every app's budget removed.
    if (held === null) return null;
    if (typeof held !== "object" ||
      !Object.prototype.hasOwnProperty.call(held, one.package)) return one.limit;
    const seconds = TS.number(held[one.package]);
    return seconds === null ? null : seconds / 60;
  }

  /** Whether a held change says anything about this app. */
  function heldFor(tv, one) {
    if (TS.held(tv, "apps_allowed") !== undefined) return true;
    const held = TS.held(tv, "app_limits_s");
    return held === null || Boolean(held && typeof held === "object" &&
      Object.prototype.hasOwnProperty.call(held, one.package));
  }

  /** The allow-list as the screen shows it: the one just sent until the set says it. */
  function chosen(tv) {
    const reported = listOf(tv);
    const saved = savedLists[tv.id];
    if (!saved) return reported;
    if (sameSet(reported, saved.list) || Date.now() - saved.at >= AGREE_MS) {
      delete savedLists[tv.id];
      return reported;
    }
    return saved.list;
  }

  /** An app's limit as the screen shows it, with the one just set laid over it. */
  function limitOf(tv, one) {
    const reported = heldLimit(tv, one);
    const saved = (savedLimits[tv.id] || {})[one.package];
    if (!saved) return reported;
    if (saved.value === reported || Date.now() - saved.at >= AGREE_MS) {
      delete savedLimits[tv.id][one.package];
      return reported;
    }
    return saved.value;
  }

  function allowedOn(tv, one) {
    const list = chosen(tv);
    return !list.length || list.includes(one.package);
  }

  /** The state an app is in, as the tag says it and the way the tag is coloured. */
  function stateOf(tv, one) {
    const limit = limitOf(tv, one);
    if (!allowedOn(tv, one) || limit === 0) {
      return {words: phrase("Blocked"), kind: "no"};
    }
    if (limit !== null) {
      return {words: phrase("{time} a day", {time: TS.length(limit)}), kind: "lim"};
    }
    return {words: phrase("Allowed"), kind: "ok"};
  }

  /** The next limit a step away, on the quarter hours, or null when there is none. */
  function stepped(from, direction) {
    if (from === null) return direction > 0 ? FIRST_LIMIT : null;
    const next = direction > 0 ?
      Math.floor(from / STEP) * STEP + STEP :
      Math.ceil(from / STEP) * STEP - STEP;
    return Math.min(MAX_LIMIT, Math.max(0, next));
  }

  function today(one) {
    return one.minutes > 0 ?
      phrase("today {time}", {time: TS.length(one.minutes)}) :
      phrase("Not used today");
  }

  function weekMinutes(tv, package_) {
    const week = Array.isArray(tv.week_by_app) ? tv.week_by_app : [];
    const found = week.find((one) => one && one.package === package_);
    return found ? TS.number(found.minutes) || 0 : 0;
  }

  let view = null;

  // ---- Sending. ----

  /** Send the whole allow-list, holding it on the screen until the set says it back. */
  async function sendList(drawn, list, where) {
    const tv = drawn.tv;
    say(where, "");
    savedLists[tv.id] = {list: list, at: Date.now()};
    paint(drawn);
    const answer = await TS.api.act({id: tv.id, action: "allowed_apps", packages: list});
    if (!answer.ok) {
      delete savedLists[tv.id];
      say(where, answer.error);
    }
    if (view) paint(view);
  }

  function sendLimit(drawn, one, value, where) {
    const tv = drawn.tv;
    say(where, "");
    savedLimits[tv.id] = savedLimits[tv.id] || {};
    savedLimits[tv.id][one.package] = {value: value, at: Date.now()};
    paint(drawn);
    TS.api.act({id: tv.id, action: "app_limit", package: one.package, minutes: value})
      .then((answer) => {
        if (!answer.ok) {
          if (savedLimits[tv.id]) delete savedLimits[tv.id][one.package];
          say(where, answer.error);
        }
        if (view) paint(view);
      });
  }

  function toggleList(drawn) {
    const tv = drawn.tv;
    const on = chosen(tv).length > 0;
    // On means every app listed now: a switch that allowed nothing new would be an
    // empty list, and an empty list is the switch off.
    sendList(drawn, on ? [] : listed(tv).map((one) => one.package), drawn.note);
  }

  /**
   * Allow or block one app.
   *
   * A limit of zero is a block too, and the sheet says Blocked for it, so Allowed has to
   * lift it: the zero goes, and with the allow-list on the app joins the list as well.
   * Before, Allowed on such an app changed nothing and said nothing, with the switch off
   * because the list already allowed it, and the app stayed blocked by its zero.
   */
  function setAccess(drawn, one, allow, where) {
    const tv = drawn.tv;
    const list = chosen(tv);
    if (allow) {
      const zero = limitOf(tv, one) === 0;
      const onList = !list.length || list.includes(one.package);
      if (zero) sendLimit(drawn, one, null, where);
      if (!onList) sendList(drawn, list.concat([one.package]), where);
      if (!zero && onList) say(where, phrase("It is allowed already."), true);
      return;
    }
    const next = !list.length ?
      listed(tv).map((each) => each.package).filter((each) => each !== one.package) :
      list.filter((each) => each !== one.package);
    if (!next.length) {
      say(where, phrase("Keep at least one app allowed, or turn the switch off."));
      return;
    }
    sendList(drawn, next, where);
  }

  // ---- The sheet. ----

  function segment(words, onTap) {
    const made = pill(words, "pill--small pill--outline");
    made.addEventListener("click", onTap);
    return made;
  }

  function openSheet(drawn, package_) {
    TS.sheet.open((body) => {
      const sheet = {package: package_, body: body, last: null};
      const head = element("div", "sheet__head");
      sheet.tile = element("span", "app__tile");
      const who = element("div", "sheet__who");
      sheet.title = element("h2", "sheet__title ellipsis");
      sheet.sub = element("p", "sheet__sub");
      who.append(sheet.title, sheet.sub);
      head.append(sheet.tile, who);

      const here = () => sheet.last || {package: package_};
      sheet.note = note();

      const access = element("div", "sheet__row");
      const seg = element("div", "seg");
      seg.setAttribute("role", "group");
      seg.setAttribute("aria-label", phrase("Access"));
      sheet.allow = segment(phrase("Allowed"), () =>
        setAccess(drawn, here(), true, sheet.note));
      sheet.block = segment(phrase("Blocked"), () =>
        setAccess(drawn, here(), false, sheet.note));
      seg.append(sheet.allow, sheet.block);
      access.append(element("span", "sheet__label", phrase("Access")), seg);

      const limit = element("div", "sheet__row");
      const step = element("div", "step");
      sheet.less = element("button", "stepper__button", "−");
      sheet.less.setAttribute("type", "button");
      sheet.less.setAttribute("aria-label", phrase("15 minutes less"));
      sheet.figure = element("b", "step__figure");
      sheet.more = element("button", "stepper__button", "+");
      sheet.more.setAttribute("type", "button");
      sheet.more.setAttribute("aria-label", phrase("15 minutes more"));
      const nudge = (direction) => {
        const one = here();
        const next = stepped(limitOf(drawn.tv, one), direction);
        if (next !== null && next !== limitOf(drawn.tv, one)) {
          sendLimit(drawn, one, next, sheet.note);
        }
      };
      sheet.less.addEventListener("click", () => { if (!sheet.less.disabled) nudge(-1); });
      sheet.more.addEventListener("click", () => { if (!sheet.more.disabled) nudge(1); });
      step.append(sheet.less, sheet.figure, sheet.more);
      limit.append(element("span", "sheet__label", phrase("Daily limit")), step);

      const foot = element("div", "sheet__row sheet__row--last");
      foot.appendChild(element("p", "sheet__hint",
        phrase("No limit means only the television's own limit applies.")));
      sheet.remove = pill(phrase("Remove limit"), "pill--small pill--outline");
      sheet.remove.addEventListener("click", () =>
        sendLimit(drawn, here(), null, sheet.note));
      foot.appendChild(sheet.remove);

      sheet.held = heldLine();
      body.append(head, access, limit, foot, sheet.held, sheet.note);
      drawn.sheet = sheet;
      fillSheet(drawn);
    });
  }

  /** The sheet, redrawn by a poll — unless it has been put away since. */
  function paintSheet(drawn) {
    if (!drawn.sheet) return;
    if (!document.contains(drawn.sheet.body)) {
      drawn.sheet = null;
      return;
    }
    fillSheet(drawn);
  }

  /** The sheet, from what is reported now. In place: nothing here is ever rebuilt. */
  function fillSheet(drawn) {
    const sheet = drawn.sheet;
    const tv = drawn.tv;
    const found = listed(tv).find((one) => one.package === sheet.package);
    // An app that has gone from the list while its sheet is open keeps the sheet it had.
    if (found) sheet.last = found;
    const one = sheet.last;
    if (!one) return;
    sheet.tile.textContent = TS.tile(one.name).textContent;
    sheet.title.textContent = one.name;
    sheet.sub.textContent = phrase("today {today} · this week {week}", {
      today: TS.length(one.minutes),
      week: TS.length(weekMinutes(tv, one.package)),
    });
    // Blocked by a zero limit reads as blocked here too, so Allowed is the way out of it.
    const allowed = allowedOn(tv, one) && limitOf(tv, one) !== 0;
    sheet.held.hidden = !heldFor(tv, one);
    sheet.allow.setAttribute("aria-pressed", String(allowed));
    sheet.block.setAttribute("aria-pressed", String(!allowed));
    sheet.allow.classList.toggle("seg--on", allowed);
    sheet.block.classList.toggle("seg--on", !allowed);
    const limit = limitOf(tv, one);
    sheet.figure.textContent = limit === null ? phrase("No limit") :
      limit === 0 ? phrase("Blocked") : TS.length(limit);
    sheet.less.disabled = limit === null || limit <= 0;
    sheet.more.disabled = limit !== null && limit >= MAX_LIMIT;
    sheet.remove.hidden = limit === null;
  }

  // ---- The screen. ----

  function build(root) {
    const made = {root: root, tv: null, rows: new Map(), sheet: null};

    made.switchRow = element("div", "mode");
    const label = element("span", "mode__label", phrase("Only chosen apps"));
    made.switch = element("button", "switch");
    made.switch.setAttribute("type", "button");
    made.switch.setAttribute("role", "switch");
    made.switch.setAttribute("aria-label", phrase("Only chosen apps"));
    made.switch.appendChild(element("span", "switch__knob"));
    made.switch.addEventListener("click", () => {
      if (!made.switch.disabled) toggleList(made);
    });
    made.switchRow.append(label, made.switch);
    made.hint = element("p", "hint");
    made.held = heldLine();
    made.note = note();
    made.list = element("div", "apps");
    made.empty = element("p", "empty", phrase("No apps to list yet."));
    made.empty.hidden = true;

    root.replaceChildren(made.switchRow, made.hint, made.held, made.note, made.list,
      made.empty);
    return made;
  }

  function buildRow(drawn, one) {
    const made = element("button", "app");
    made.setAttribute("type", "button");
    // Kept apart from the button: `title` is a property of every element in a browser,
    // and an element written over it becomes a string.
    const parts = {
      tile: TS.tile(""),
      title: element("span", "app__title ellipsis"),
      sub: element("span", "app__sub"),
      tag: element("span", "tag"),
    };
    const text = element("span", "app__text");
    text.append(parts.title, parts.sub);
    made.append(parts.tile, text, parts.tag);
    made.addEventListener("click", () => openSheet(drawn, one.package));
    return {button: made, parts: parts};
  }

  function paintRow(drawn, row, one) {
    const parts = row.parts;
    parts.tile.textContent = TS.tile(one.name).textContent;
    parts.title.textContent = one.name;
    parts.sub.textContent = today(one);
    const state = stateOf(drawn.tv, one);
    parts.tag.textContent = state.words;
    parts.tag.className = "tag tag--" + state.kind;
  }

  function paint(drawn) {
    if (!drawn.root.contains(drawn.switchRow)) return;
    const tv = drawn.tv;
    const apps = listed(tv);
    const on = chosen(tv).length > 0;

    drawn.switch.setAttribute("aria-checked", String(on));
    drawn.switch.classList.toggle("switch--on", on);
    drawn.switch.disabled = !on && !apps.length;
    drawn.held.hidden = TS.held(tv, "apps_allowed") === undefined &&
      TS.held(tv, "app_limits_s") === undefined;
    drawn.hint.textContent = on ?
      phrase("Only the apps allowed below open. New apps stay blocked until you allow them.") :
      phrase("Every app can be opened. Turn this on to allow only the ones you choose.");

    // Rows are kept by package and updated where they stand, so an app with the focus
    // keeps it through a poll; they move only when the order itself has changed.
    const keep = new Set(apps.map((one) => one.package));
    drawn.rows.forEach((row, package_) => {
      if (keep.has(package_)) return;
      row.button.remove();
      drawn.rows.delete(package_);
    });
    apps.forEach((one) => {
      let row = drawn.rows.get(one.package);
      if (!row) {
        row = buildRow(drawn, one);
        drawn.rows.set(one.package, row);
      }
      paintRow(drawn, row, one);
    });
    const wanted = apps.map((one) => drawn.rows.get(one.package).button);
    const there = Array.from(drawn.list.children);
    if (wanted.length !== there.length || wanted.some((made, at) => made !== there[at])) {
      wanted.forEach((made) => drawn.list.appendChild(made));
    }
    drawn.empty.hidden = apps.length > 0;

    paintSheet(drawn);
  }

  window.TS.screens.apps = {
    render(root, tv) {
      if (!view || view.root !== root || !root.contains(view.switchRow)) {
        // A screen built afresh is a different visit: its sheet belongs to the last one.
        TS.sheet.close();
        view = build(root);
      } else if (view.tv && view.tv.id !== tv.id) {
        TS.sheet.close();
        view.sheet = null;
      }
      view.tv = tv;
      paint(view);
    },
  };
})();
