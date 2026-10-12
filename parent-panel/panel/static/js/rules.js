// The Rules screen: one day at a time, how much and when.
//
// How much is the day's budget; when is the window it can be spent in. They are two
// different rules on the television and two different questions to a parent, so they
// are drawn apart and changed apart — a limit never moves the hours, and a block of
// hours never changes the limit. Where the budget is bigger than the window, the
// screen says so rather than leaving a parent to work out why two and a half hours
// were never watched.
//
// The hours travel as the whole week of half hours the old grid sent (`hours`), which
// is the one shape the add-on turns back into windows. A day is edited as blocks, and
// saving a block sends every day, the six that were not touched exactly as they were.
//
// Drawn again on every poll into the same root. Built once and changed in place; the
// blocks are rebuilt only when the hours themselves change, so a block with the focus
// keeps it, and the sheet a block opens lives outside the screen altogether.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;

  // The week in the order a week is read, keyed the way the state keys it.
  const WEEK = [
    ["mon", phrase("Monday"), phrase("Mon")],
    ["tue", phrase("Tuesday"), phrase("Tue")],
    ["wed", phrase("Wednesday"), phrase("Wed")],
    ["thu", phrase("Thursday"), phrase("Thu")],
    ["fri", phrase("Friday"), phrase("Fri")],
    ["sat", phrase("Saturday"), phrase("Sat")],
    ["sun", phrase("Sunday"), phrase("Sun")],
  ];
  const DAYS = WEEK.map((day) => day[0]);
  // The same days in the order `Date.getDay()` counts them.
  const BY_DATE = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

  const COPIES = [
    {label: phrase("weekdays"), days: ["mon", "tue", "wed", "thu", "fri"]},
    {label: phrase("the weekend"), days: ["sat", "sun"]},
    {label: phrase("the whole week"), days: DAYS},
  ];

  const MINUTES_PER_HOUR = 60;
  const MS_PER_MINUTE = 60 * 1000;
  // The rules are written in half hours, so the blocks are too.
  const HALF = 30;
  const DAY_MINUTES = 24 * MINUTES_PER_HOUR;
  // The axis starts where a child's day does. Hours before it are rare and are still
  // drawn, pinned to the top with their real times on them.
  const AXIS_FROM = 6 * MINUTES_PER_HOUR;
  // Tall enough that half an hour is a line of text, short enough that the evening
  // and the button under it are on a phone's first screen.
  const PX_PER_HOUR = 32;
  const LABEL_EVERY = 2;

  // The steps a limit moves in, and its ceiling, which is the number entities' own.
  const STEP = 15;
  const MAX_LIMIT = 720;
  // Where a limit starts from when there is none to step from: an hour is a budget a
  // parent can see and correct, where fifteen minutes would lock a set mid-programme.
  const FIRST_LIMIT = 60;

  // What a new block covers before it is moved: an hour, from the time tapped or from
  // the afternoon a school day is free in.
  const NEW_FROM = 16 * MINUTES_PER_HOUR;
  const NEW_LENGTH = MINUTES_PER_HOUR;

  // The lengths the sleep timer offers, up to the four hours the television takes.
  const SLEEP_MAX = 240;
  const SLEEP_FIRST = 60;

  // How long a change made here stays on the screen while the television has yet to
  // report it back. Long enough to cover the write, the broker and a set that is
  // thinking about it; short enough that a television which read the rule differently
  // does not leave a picture of hours nobody is enforcing. A set that is asleep is not
  // on this clock at all: what is waiting for it is in `pending_rules`, and is shown.
  const AGREE_MS = 12000;

  // ---- Half hours and blocks, which are two spellings of the same hours. ----

  /** `HH:MM` as minutes past midnight, `24:00` included; null when it is not a time. */
  function minuteOf(at) {
    const parts = /^(\d{2}):(\d{2})$/.exec(String(at));
    if (!parts) return null;
    const minute = Number(parts[1]) * MINUTES_PER_HOUR + Number(parts[2]);
    return Number(parts[2]) < MINUTES_PER_HOUR && minute <= DAY_MINUTES ? minute : null;
  }

  function timeOf(minute) {
    const two = (value) => String(value).padStart(2, "0");
    return two(Math.floor(minute / MINUTES_PER_HOUR)) + ":" + two(minute % MINUTES_PER_HOUR);
  }

  /** A day's half hours as the blocks they make, touching ones joined. */
  function blocks(slots) {
    const starts = Array.from(new Set((Array.isArray(slots) ? slots : [])
      .map(minuteOf)
      .filter((minute) => minute !== null && minute < DAY_MINUTES)
      .map((minute) => minute - (minute % HALF))))
      .sort((one, other) => one - other);
    const made = [];
    starts.forEach((start) => {
      const last = made[made.length - 1];
      if (last && last.to === start) last.to = start + HALF;
      else made.push({from: start, to: start + HALF});
    });
    return made.map((one) => ({from: timeOf(one.from), to: timeOf(one.to)}));
  }

  /**
   * Blocks back into a day's half hours. Overlapping and touching blocks come out as
   * one run, so what goes to the television is never two windows over the same time.
   */
  function slots(list) {
    const marked = new Set();
    (Array.isArray(list) ? list : []).forEach((one) => {
      const from = minuteOf(one && one.from);
      const to = minuteOf(one && one.to);
      if (from === null || to === null || from >= DAY_MINUTES) return;
      for (let at = from - (from % HALF); at < to; at += HALF) marked.add(at);
    });
    return Array.from(marked).sort((one, other) => one - other).map(timeOf);
  }

  // ---- The week as the screen shows it. ----

  function weekOf(hours) {
    const week = {};
    DAYS.forEach((day) => {
      week[day] = hours && Array.isArray(hours[day]) ? hours[day].slice() : [];
    });
    return week;
  }

  function sameWeek(one, other) {
    return DAYS.every((day) => JSON.stringify(one[day]) === JSON.stringify(other[day]));
  }

  /**
   * Whether the television reports the week that was saved here. A week with every
   * half hour marked is no restriction, which the add-on writes as no windows at all —
   * and reads back as an empty week, which is the same thing said the other way.
   */
  function agrees(given, wanted) {
    if (sameWeek(given, wanted)) return true;
    const whole = DAYS.every((day) => wanted[day].length === DAY_MINUTES / HALF);
    return whole && DAYS.every((day) => !given[day].length);
  }

  // What was saved from here and has not come back yet, per television, so moving to
  // another tab and back inside the gap does not paint the old hours either.
  const savedHours = {};
  const savedLimits = {};

  /**
   * Whether the hours saved here are still the ones to show.
   *
   * Three answers rather than two, the old grid's: the set agrees, and the week is its
   * own again; a sleeping set is holding the change, and it stays; or the set is awake,
   * holding nothing, and the wait is up — it has read the rule differently, and the
   * one enforcing the hours is the one that gets to say what they are.
   */
  function caught(drawn, tv) {
    const saved = savedHours[tv.id];
    if (!saved) return;
    if (tv.following_schedule || agrees(weekOf(tv.hours), saved.days)) {
      delete savedHours[tv.id];
    } else if (!tv.pending_rules && Date.now() - saved.at >= AGREE_MS) {
      delete savedHours[tv.id];
      say(drawn.hoursNote, phrase("The television is enforcing other hours, so these " +
        "are its own."), "error");
    }
  }

  function shownWeek(tv) {
    const saved = savedHours[tv.id];
    return saved ? saved.days : weekOf(tv.hours);
  }

  /** A limit as the television reports it, with any change waiting for it laid over. */
  function reported(tv, key) {
    const waiting = tv.pending_rules;
    if (key === "daily_limit") {
      if (waiting && Object.prototype.hasOwnProperty.call(waiting, "daily_limit_s")) {
        const seconds = TS.number(waiting.daily_limit_s);
        return seconds === null ? null : seconds / 60;
      }
      return TS.number(tv.daily_limit);
    }
    const day = key.slice("limit_".length);
    if (waiting && Object.prototype.hasOwnProperty.call(waiting, "days")) {
      const days = waiting.days;
      // A null in the change is a removal: every day back on the daily limit.
      if (days === null) return null;
      if (days && typeof days === "object" &&
        Object.prototype.hasOwnProperty.call(days, day)) {
        const seconds = TS.number(days[day]);
        return seconds === null ? null : seconds / 60;
      }
    }
    return TS.number((tv.week || {})[day]);
  }

  /** A limit as the screen shows it: the one just set here until the set says it back. */
  function limit(tv, key) {
    const saved = (savedLimits[tv.id] || {})[key];
    const now = reported(tv, key);
    if (!saved) return now;
    if (now === saved.value || Date.now() - saved.at >= AGREE_MS) {
      delete savedLimits[tv.id][key];
      return now;
    }
    return saved.value;
  }

  /** The next limit a step away, on the quarter hours, or null when there is none. */
  function stepped(from, direction) {
    if (from === null) return direction > 0 ? FIRST_LIMIT : null;
    const next = direction > 0 ?
      Math.floor(from / STEP) * STEP + STEP :
      Math.ceil(from / STEP) * STEP - STEP;
    return Math.min(MAX_LIMIT, Math.max(0, next));
  }

  // ---- Drawing. ----

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

  /** A line under a control: an error in rose, anything else quietly. */
  function say(note, words, tone) {
    note.textContent = words || "";
    note.hidden = !words;
    note.classList.toggle("note--quiet", tone !== "error");
  }

  function note() {
    const made = element("p", "note");
    made.setAttribute("role", "status");
    made.hidden = true;
    return made;
  }

  function stepper(onStep) {
    const box = element("div", "stepper");
    const less = element("button", "stepper__button", "−");
    less.setAttribute("type", "button");
    less.setAttribute("aria-label", phrase("15 minutes less"));
    const more = element("button", "stepper__button", "+");
    more.setAttribute("type", "button");
    more.setAttribute("aria-label", phrase("15 minutes more"));
    less.addEventListener("click", () => { if (!less.disabled) onStep(-1); });
    more.addEventListener("click", () => { if (!more.disabled) onStep(1); });
    box.append(less, more);
    return {box: box, less: less, more: more};
  }

  let view = null;

  /** Send one change from this screen, and say what came of it under `where`. */
  async function send(drawn, body, where, done) {
    const tv = drawn.tv;
    say(where, "");
    const answer = await TS.api.act(Object.assign({id: tv.id}, body));
    if (!answer.ok) say(where, answer.error, "error");
    else if (done) say(where, done);
    if (view) paint(view);
    return answer;
  }

  function sendLimit(drawn, key, value, body) {
    const tv = drawn.tv;
    savedLimits[tv.id] = savedLimits[tv.id] || {};
    savedLimits[tv.id][key] = {value: value, at: Date.now()};
    paint(drawn);
    const where = key === "daily_limit" ? drawn.dailyNote : drawn.limitNote;
    send(drawn, body, where).then((answer) => {
      if (answer.ok || !savedLimits[tv.id]) return;
      delete savedLimits[tv.id][key];
      if (view) paint(view);
    });
  }

  /** Save a whole week, holding it on the screen until the television says it back. */
  async function sendWeek(drawn, days, done) {
    const tv = drawn.tv;
    if (sameWeek(days, shownWeek(tv))) return;
    say(drawn.hoursNote, "");
    savedHours[tv.id] = {days: days, at: Date.now()};
    paint(drawn);
    // Every day every time: a day left out would be read as a day with no hours.
    const answer = await TS.api.act({id: tv.id, action: "hours", days: days});
    if (!answer.ok) {
      // Refused, so what was drawn is a rule nowhere at all: back to what is enforced.
      delete savedHours[tv.id];
      say(drawn.hoursNote, answer.error, "error");
    } else if (done) {
      say(drawn.hoursNote, done);
    }
    if (view) paint(view);
    return answer;
  }

  function emptyWeek(week) {
    return DAYS.every((day) => !week[day].length);
  }

  /** One day's hours with one block taken out and another put in. */
  async function changeDay(drawn, day, was, now) {
    const week = shownWeek(drawn.tv);
    const first = emptyWeek(week);
    const days = weekOf(week);
    const gone = new Set(was ? slots([was]) : []);
    const kept = days[day].filter((at) => !gone.has(at));
    days[day] = slots(blocks(kept).concat(now ? [now] : []));
    const answer = await sendWeek(drawn, days);
    // The first hours of an unrestricted week turn every other day into a day with no
    // hours, which is a locked day (D27) — on a screen that shows one day at a time.
    // So the days that just locked are named, next to the way of giving them hours.
    if (first && answer && answer.ok && drawn.day === day) {
      drawn.lockedAfter = day;
      if (view) paint(view);
    }
  }

  function options(select, first, last) {
    for (let at = first; at <= last; at += HALF) {
      const option = element("option", null, timeOf(at));
      option.value = timeOf(at);
      select.appendChild(option);
    }
  }

  function wheel(words, edge, first, last, value) {
    const box = element("label", "wheel");
    const select = element("select", "wheel__select");
    select.setAttribute("data-edge", edge);
    options(select, first, last);
    select.value = value;
    box.append(element("span", "wheel__label", words), select);
    return {box: box, select: select};
  }

  /** The sheet for one block, or for a new one when `was` is null. */
  function edit(drawn, was, from) {
    if (sealed(drawn.tv)) return;
    const day = drawn.day;
    const named = WEEK[DAYS.indexOf(day)][1];
    const start = was ? minuteOf(was.from) : from;
    const end = was ? minuteOf(was.to) : Math.min(DAY_MINUTES, from + NEW_LENGTH);
    TS.sheet.open((body) => {
      const title = element("h2", "sheet__title", phrase("{day} · hours", {day: named}));
      const opens = wheel(phrase("From"), "from", 0, DAY_MINUTES - HALF, timeOf(start));
      const shuts = wheel(phrase("To"), "to", HALF, DAY_MINUTES, timeOf(end));
      const wheels = element("div", "wheels");
      wheels.append(opens.box, shuts.box);
      const said = note();
      // Said before the save rather than after: the hours of one day are about to
      // decide the other six.
      const warn = element("p", "sheet__warn", phrase("The other days will be locked " +
        "unless they get hours too."));
      warn.hidden = Boolean(was) || !emptyWeek(shownWeek(drawn.tv));
      // A start moved onto or past the end takes the end with it, half an hour on,
      // rather than leaving a block that ends before it begins.
      opens.select.addEventListener("change", () => {
        const first = minuteOf(opens.select.value);
        if (minuteOf(shuts.select.value) <= first) shuts.select.value = timeOf(first + HALF);
      });
      const row = element("div", "actions sheet__actions");
      if (was) {
        const remove = pill(phrase("Delete"), "pill--danger");
        remove.addEventListener("click", () => {
          TS.sheet.close();
          changeDay(drawn, day, was, null);
        });
        row.appendChild(remove);
      }
      const cancel = pill(phrase("Cancel"), "pill--outline");
      cancel.addEventListener("click", () => TS.sheet.close());
      const save = pill(phrase("Save"), "pill--accent");
      save.addEventListener("click", () => {
        const now = {from: opens.select.value, to: shuts.select.value};
        if (minuteOf(now.to) <= minuteOf(now.from)) {
          say(said, phrase("The end has to be after the start."), "error");
          return;
        }
        TS.sheet.close();
        changeDay(drawn, day, was, now);
      });
      row.append(cancel, save);
      body.append(title, wheels, warn, said, row);
    });
  }

  function sealed(tv) {
    return Boolean(tv && tv.following_schedule);
  }

  function buildAxis(made) {
    const axis = element("div", "axis");
    const hours = (DAY_MINUTES - AXIS_FROM) / MINUTES_PER_HOUR;
    axis.style.height = hours * PX_PER_HOUR + "px";
    const marks = element("div", "axis__marks");
    marks.setAttribute("aria-hidden", "true");
    for (let hour = AXIS_FROM / MINUTES_PER_HOUR; hour <= 24; hour += 1) {
      const mark = element("div", "axis__mark");
      mark.style.top = (hour - AXIS_FROM / MINUTES_PER_HOUR) * PX_PER_HOUR + "px";
      if (hour % LABEL_EVERY === 0) {
        mark.appendChild(element("span", "axis__time", timeOf(hour * MINUTES_PER_HOUR)));
      }
      marks.appendChild(mark);
    }
    // The empty time between blocks: a tap there adds a block at the half hour tapped.
    // Out of the reading order, because "Add hours" under the axis does the same for a
    // keyboard or a screen reader.
    made.lane = element("div", "axis__lane");
    made.lane.addEventListener("click", (event) => {
      const target = event.target;
      if (!view || sealed(view.tv)) return;
      if (target && target.closest && target.closest(".block")) return;
      const top = made.lane.getBoundingClientRect().top;
      const half = Math.floor((Number(event.clientY) - top) / (PX_PER_HOUR / 2));
      if (!Number.isFinite(half)) return;
      const minute = Math.min(DAY_MINUTES - HALF, Math.max(AXIS_FROM, AXIS_FROM + half * HALF));
      edit(view, null, minute);
    });
    axis.append(marks, made.lane);
    return axis;
  }

  function build(root) {
    const made = {root: root, tv: null, day: BY_DATE[new Date().getDay()], drawnBlocks: null};

    // The change a sleeping television has not had yet. On top, because it changes how
    // everything under it is read.
    made.held = element("div", "held");
    made.held.setAttribute("role", "status");
    made.heldText = element("p", "held__text",
      phrase("The television is asleep. The change goes when it wakes."));
    made.undo = element("button", "held__undo", phrase("Undo"));
    made.undo.setAttribute("type", "button");
    made.undo.addEventListener("click", () => {
      const tv = made.tv;
      delete savedHours[tv.id];
      delete savedLimits[tv.id];
      send(made, {action: "forget_pending"}, made.hoursNote);
    });
    made.held.append(made.heldText, made.undo);

    made.chips = element("div", "days");
    made.chips.setAttribute("role", "group");
    made.chips.setAttribute("aria-label", phrase("Day"));
    made.chip = {};
    WEEK.forEach(([day, long, short]) => {
      const chip = element("button", "day", short);
      chip.setAttribute("type", "button");
      chip.setAttribute("data-day", day);
      chip.setAttribute("aria-label", long);
      chip.addEventListener("click", () => {
        made.day = day;
        say(made.limitNote, "");
        say(made.hoursNote, "");
        made.lockedAfter = null;
        paint(made);
      });
      made.chip[day] = chip;
      made.chips.appendChild(chip);
    });

    // How much.
    const much = element("section", "limit");
    made.figure = element("p", "limit__figure");
    made.figure.setAttribute("aria-live", "polite");
    made.dayStep = stepper((direction) => {
      const day = made.day;
      const own = limit(made.tv, "limit_" + day);
      const value = stepped(own !== null ? own : limit(made.tv, "daily_limit"), direction);
      if (value === null) return;
      sendLimit(made, "limit_" + day, value,
        {action: "number", key: "limit_" + day, value: value});
    });
    const figureRow = element("div", "limit__row");
    figureRow.append(made.figure, made.dayStep.box);
    made.dailyLine = element("p", "limit__sub");
    made.windowLine = element("p", "limit__sub");
    made.warn = element("p", "limit__warn");
    made.asDaily = pill(phrase("Use the daily limit"), "pill--outline pill--small");
    made.asDaily.addEventListener("click", () => {
      const day = made.day;
      // Without minutes, which is what the rules read as "this day has none of its own".
      sendLimit(made, "limit_" + day, null, {action: "schedule", day: day});
    });
    made.limitNote = note();
    much.append(element("h2", "heading", phrase("How much")), figureRow, made.dailyLine,
      made.windowLine, made.warn, made.asDaily, made.limitNote);

    // When.
    const when = element("section", "when");
    made.readOnly = element("p", "when__sealed");
    made.add = pill(phrase("Add hours"), "pill--outline");
    made.add.addEventListener("click", () => edit(made, null, NEW_FROM));
    made.copy = element("div", "copy");
    const copyLabel = element("span", "copy__label", phrase("Copy these hours to"));
    copyLabel.id = "ts-copy-label";
    made.copy.setAttribute("role", "group");
    made.copy.setAttribute("aria-labelledby", copyLabel.id);
    made.copy.appendChild(copyLabel);
    COPIES.forEach((copy) => {
      const chip = pill(copy.label, "pill--outline pill--small");
      chip.addEventListener("click", () => {
        const days = weekOf(shownWeek(made.tv));
        copy.days.forEach((day) => { days[day] = days[made.day].slice(); });
        sendWeek(made, days, phrase("Copied"));
      });
      made.copy.appendChild(chip);
    });
    made.locked = element("p", "when__locked");
    made.locked.setAttribute("role", "status");
    made.locked.hidden = true;
    made.hoursNote = note();
    when.append(element("h2", "heading", phrase("When")), made.readOnly, buildAxis(made),
      made.add, made.locked, made.copy, made.hoursNote);

    // Every day: the limit a day without its own takes.
    const every = element("section", "daily");
    made.dailyFigure = element("p", "setting__value");
    made.dailyStep = stepper((direction) => {
      const value = stepped(limit(made.tv, "daily_limit"), direction);
      if (value === null) return;
      sendLimit(made, "daily_limit", value,
        {action: "number", key: "daily_limit", value: value});
    });
    const dailyRow = element("div", "setting");
    const dailyName = element("div", "setting__name");
    dailyName.append(element("p", "setting__title", phrase("Daily limit")),
      element("p", "setting__hint", phrase("For days without their own.")));
    dailyRow.append(dailyName, made.dailyFigure, made.dailyStep.box);
    made.noLimit = pill(phrase("Remove the limit"), "pill--outline pill--small");
    made.noLimit.addEventListener("click", () => {
      sendLimit(made, "daily_limit", null, {action: "clear_limit"});
    });
    made.dailyNote = note();
    every.append(element("h2", "heading", phrase("Every day")), dailyRow, made.noLimit,
      made.dailyNote);

    // Today: the sleep timer, one evening's decision rather than a rule.
    const tonight = element("section", "sleep");
    made.sleep = element("select", "setting__select");
    made.sleep.setAttribute("aria-label", phrase("Sleep timer"));
    for (let minutes = STEP; minutes <= SLEEP_MAX; minutes += STEP) {
      const option = element("option", null, TS.length(minutes));
      option.value = String(minutes);
      made.sleep.appendChild(option);
    }
    made.sleep.value = String(SLEEP_FIRST);
    const sleepRow = element("div", "setting");
    const sleepName = element("div", "setting__name");
    sleepName.append(element("p", "setting__title", phrase("Sleep timer")),
      element("p", "setting__hint", phrase("Turns the television off after this long.")));
    sleepRow.append(sleepName, made.sleep);
    made.start = pill(phrase("Start"), "pill--accent pill--small");
    made.start.addEventListener("click", () => {
      if (made.start.disabled) return;
      const minutes = Number(made.sleep.value);
      const off = new Date(Date.now() + minutes * MS_PER_MINUTE);
      send(made, {action: "number", key: "sleep_timer", value: minutes}, made.sleepNote,
        phrase("The television turns off at {clock}.", {clock: TS.clock(off)}));
    });
    made.stop = pill(phrase("Cancel the timer"), "pill--outline pill--small");
    made.stop.addEventListener("click", () => {
      if (made.stop.disabled) return;
      send(made, {action: "number", key: "sleep_timer", value: 0}, made.sleepNote,
        phrase("The sleep timer is off."));
    });
    const sleepActions = element("div", "actions setting__actions");
    sleepActions.append(made.start, made.stop);
    made.why = element("p", "why", phrase("These need the television to be on and connected."));
    made.sleepNote = note();
    tonight.append(element("h2", "heading", phrase("Today")), sleepRow, sleepActions,
      made.why, made.sleepNote);

    root.replaceChildren(made.held, made.chips, much, when, every, tonight);
    return made;
  }

  /** The blocks of the day on the axis, rebuilt only when they change. */
  function paintBlocks(drawn, list, locked) {
    const key = drawn.day + JSON.stringify(list) + locked;
    if (drawn.drawnBlocks === key) return;
    drawn.drawnBlocks = key;
    const perMinute = PX_PER_HOUR / MINUTES_PER_HOUR;
    drawn.lane.replaceChildren(...list.map((one) => {
      const from = minuteOf(one.from);
      const to = minuteOf(one.to);
      const words = one.from + "–" + one.to;
      const made = element("button", "block", words);
      made.setAttribute("type", "button");
      // Before the axis starts: pinned to its top, half an hour tall at the least.
      const top = Math.max(from, AXIS_FROM);
      const early = to <= AXIS_FROM;
      made.style.top = (top - AXIS_FROM) * perMinute + "px";
      made.style.height = (early ? HALF : to - top) * perMinute + "px";
      made.classList.toggle("block--clipped", from < AXIS_FROM);
      made.classList.toggle("block--short", to - top <= HALF || early);
      if (locked) {
        made.disabled = true;
      } else {
        made.setAttribute("aria-label", phrase("Edit the hours from {from} to {to}",
          {from: one.from, to: one.to}));
        made.addEventListener("click", () => {
          // Where the focus goes back to once the sheet is put away.
          made.focus({preventScroll: true});
          edit(drawn, one);
        });
      }
      return made;
    }));
  }

  function paintLimit(drawn, week) {
    const tv = drawn.tv;
    const own = limit(tv, "limit_" + drawn.day);
    const daily = limit(tv, "daily_limit");
    const spent = own !== null ? own : daily;
    drawn.figure.textContent = own !== null ? TS.length(own) : phrase("As daily");
    drawn.dailyLine.textContent = daily !== null ?
      phrase("The daily limit: {time}", {time: TS.length(daily)}) :
      phrase("No daily limit is set");
    drawn.dailyLine.hidden = own !== null;
    drawn.asDaily.hidden = own === null;
    drawn.dayStep.less.disabled = spent === null || spent <= 0;
    drawn.dayStep.more.disabled = spent !== null && spent >= MAX_LIMIT;

    const open = week[drawn.day].length * HALF;
    const anyHours = DAYS.some((day) => week[day].length);
    if (!anyHours) {
      drawn.windowLine.textContent =
        phrase("No hours are marked on any day, so it can be spent at any time.");
    } else if (!open) {
      drawn.windowLine.textContent = phrase("No hours on this day: the television stays locked.");
    } else {
      drawn.windowLine.textContent = phrase("To be spent within the marked hours " +
        "(window: {time}).", {time: TS.length(open)});
    }
    const over = anyHours && open > 0 && spent !== null && spent > open;
    drawn.warn.hidden = !over;
    drawn.warn.textContent = over ? phrase("The hours come to only {time}, so no more " +
      "than that can be watched.", {time: TS.length(open)}) : "";
  }

  function paint(drawn) {
    if (!drawn.root.contains(drawn.held)) return;
    const tv = drawn.tv;
    caught(drawn, tv);
    const week = shownWeek(tv);
    const locked = sealed(tv);

    drawn.held.hidden = !tv.pending_rules;
    DAYS.forEach((day) => {
      const on = day === drawn.day;
      drawn.chip[day].setAttribute("aria-pressed", String(on));
      drawn.chip[day].classList.toggle("day--on", on);
    });

    paintLimit(drawn, week);

    drawn.readOnly.hidden = !locked;
    drawn.readOnly.textContent = locked ?
      phrase("Read-only: the hours come from {helper}.", {helper: tv.following_schedule}) :
      "";
    paintBlocks(drawn, blocks(week[drawn.day]), locked);
    drawn.add.hidden = locked;
    drawn.copy.hidden = locked;
    const shut = DAYS.filter((day) => !week[day].length);
    if (drawn.lockedAfter && (locked || !shut.length || drawn.lockedAfter !== drawn.day)) {
      drawn.lockedAfter = null;
    }
    drawn.locked.hidden = !drawn.lockedAfter;
    drawn.locked.textContent = drawn.lockedAfter ?
      phrase("No hours on {days}, so the television stays locked on them.",
        {days: shut.map((day) => WEEK[DAYS.indexOf(day)][2]).join(", ")}) : "";

    const daily = limit(tv, "daily_limit");
    drawn.dailyFigure.textContent = daily !== null ? TS.length(daily) : phrase("No limit");
    drawn.dailyStep.less.disabled = daily === null || daily <= 0;
    drawn.dailyStep.more.disabled = daily !== null && daily >= MAX_LIMIT;
    drawn.noLimit.hidden = daily === null;

    // The timer is a command, not a rule: it is not held for a set that is away.
    const away = !tv.reporting;
    drawn.start.disabled = away;
    drawn.stop.disabled = away;
    drawn.why.hidden = !away;
  }

  TS.rules = {blocks: blocks, slots: slots, PX_PER_HOUR: PX_PER_HOUR};

  TS.screens.rules = {
    render(root, tv) {
      if (!view || view.root !== root || !root.contains(view.held)) view = build(root);
      view.tv = tv;
      paint(view);
    },
  };
})();
