// The Now screen: the first thing a parent sees, and the one they act from.
//
// One screen whose top changes with the television: what is left today while somebody
// watches, a lock and when it ends while the set is locked, when it was last seen while
// it does not answer — and above any of them, a request for more time waiting to be
// answered. The amounts on every button are fixed at 15 and 30 minutes, whatever the
// child asked for: a parent answering from a pocket should not have to read the
// buttons first.
//
// Drawn again on every poll into the same root. The parts are built once and kept, and
// only what they say is changed, so a thumb on a button never finds it gone.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;
  const SVG = "http://www.w3.org/2000/svg";
  const MINUTE_MS = 60 * 1000;
  const MINUTES_PER_HOUR = 60;
  const MS_PER_SECOND = 1000;
  const SECONDS_PER_MINUTE = 60;
  const DAYS_AHEAD = 8;
  // How long the television waits for an answer (docs/mqtt-contract.md). A set switched
  // off inside it leaves its last state saying a request waits, all evening.
  const REQUEST_MS = 10 * MINUTE_MS;
  // The days the way `hours` names them, in the order `Date.getDay()` counts them.
  const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

  // Why the screen is covered, in the contract's words (`lock_reason`). Short enough to
  // stand as the header's status line as well as under the lock on the screen.
  const REASONS = {
    daily_limit: phrase("Today's time is used up"),
    outside_window: phrase("Outside the allowed hours"),
    sleep_timer: phrase("The sleep timer ran out"),
    manual: phrase("Locked by a parent"),
    app_limit: phrase("This app's time is used up"),
    app_not_allowed: phrase("This app is not allowed"),
  };

  /** Why a television is locked, or just that it is when the reason is a new one. */
  function reason(tv) {
    const said = tv && tv.lock_reason;
    return Object.prototype.hasOwnProperty.call(REASONS, said) ? REASONS[said] :
      phrase("Locked");
  }

  function element(tag, name, words) {
    const made = document.createElement(tag);
    if (name) made.className = name;
    if (words !== undefined) made.textContent = words;
    return made;
  }

  /** A padlock, drawn from fixed shapes. */
  function padlock() {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    [["rect", {x: 5, y: 10.5, width: 14, height: 10, rx: 2.5}],
      ["path", {d: "M8 10.5V8a4 4 0 0 1 8 0v2.5"}]].forEach(([tag, values]) => {
      const shape = document.createElementNS(SVG, tag);
      Object.keys(values).forEach((name) => shape.setAttribute(name, values[name]));
      shape.setAttribute("fill", "none");
      shape.setAttribute("stroke", "currentColor");
      shape.setAttribute("stroke-width", "2");
      svg.appendChild(shape);
    });
    return svg;
  }

  /** A half hour of the grid, as minutes into its day. */
  function minuteOf(slot) {
    const parts = /^(\d{1,2}):(\d{2})$/.exec(String(slot));
    return parts ? Number(parts[1]) * MINUTES_PER_HOUR + Number(parts[2]) : null;
  }

  /**
   * The first allowed half hour after `from`, and how many days ahead it is.
   *
   * Null when the week has no hours at all, which is no restriction rather than a
   * closed week, or when nothing opens in the week ahead.
   */
  function opening(tv, from) {
    const hours = tv.hours || {};
    const week = DAYS.map((day) => (Array.isArray(hours[day]) ? hours[day] : []));
    if (week.every((day) => !day.length)) return null;
    for (let ahead = 0; ahead < DAYS_AHEAD; ahead += 1) {
      const day = new Date(from.getFullYear(), from.getMonth(), from.getDate() + ahead);
      const starts = week[day.getDay()].map(minuteOf)
        .filter((minute) => minute !== null)
        .sort((one, other) => one - other);
      for (const minute of starts) {
        const at = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, minute);
        if (at > from) return {ahead: ahead, at: at};
      }
    }
    return null;
  }

  /** When viewing is allowed again, as far as the rules on the page can tell. */
  function again(tv) {
    const now = new Date();
    switch (tv.lock_reason) {
      case "outside_window": {
        const next = opening(tv, now);
        if (!next || next.ahead > 1) return null;
        return next.ahead === 0 ?
          phrase("Allowed again at {clock}", {clock: TS.clock(next.at)}) :
          phrase("Allowed again tomorrow at {clock}", {clock: TS.clock(next.at)});
      }
      case "daily_limit":
      case "sleep_timer": {
        // A new day is a new allowance; it starts when tomorrow's first hours do. Asked
        // from the last instant of today, so tomorrow is one day ahead of it.
        const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        const next = opening(tv, new Date(midnight.getTime() - 1));
        if (!next) return phrase("Allowed again tomorrow");
        return next.ahead === 1 ?
          phrase("Allowed again tomorrow at {clock}", {clock: TS.clock(next.at)}) : null;
      }
      case "app_limit":
      case "app_not_allowed":
        return phrase("Other apps can still be watched");
      default:
        return null;
    }
  }

  /** How long ago a request was made, the way a notification says it. */
  function ago(askedAt) {
    const at = TS.number(askedAt);
    if (at === null) return null;
    const minutes = Math.floor((Date.now() - at) / MINUTE_MS);
    if (minutes < 1) return phrase("just now");
    if (minutes < MINUTES_PER_HOUR) return phrase("{count} min ago", {count: minutes});
    return phrase("at {clock}", {clock: TS.clock(new Date(at))});
  }

  // The one screen being drawn. Rebuilt when the shell has emptied its root, which it
  // does on moving between tabs and televisions; kept otherwise.
  let view = null;
  // A change on its way. One at a time: a second tap on a phone that has not answered
  // yet is the same tap again, and fifteen minutes given twice is half an hour.
  let sending = false;

  function pill(words, send) {
    const made = element("button", "pill", words);
    made.setAttribute("type", "button");
    made.addEventListener("click", () => {
      if (!made.disabled) act(send());
    });
    return made;
  }

  async function act(body) {
    if (sending || !view) return;
    const drawn = view;
    sending = true;
    drawn.note.hidden = true;
    paint(drawn);
    const answer = await TS.api.act(Object.assign({id: drawn.tv.id}, body));
    sending = false;
    // The screen the answer lands on, which a tab or television switched while it was
    // on its way may have built afresh.
    if (!view) return;
    if (!answer.ok && view === drawn) {
      view.note.textContent = answer.error;
      view.note.hidden = false;
    }
    paint(view);
  }

  function build(root) {
    const made = {root: root, tv: null, request: null};

    made.ask = element("section", "ask");
    made.ask.setAttribute("aria-labelledby", "ts-ask-title");
    const title = element("p", "ask__title", phrase("Asking for more time"));
    title.id = "ts-ask-title";
    made.detail = element("p", "ask__detail");
    made.answers = {
      give15: pill(phrase("Give 15"), () =>
        ({action: "grant", req_id: made.request.id, minutes: 15})),
      give30: pill(phrase("Give 30"), () =>
        ({action: "grant", req_id: made.request.id, minutes: 30})),
      deny: pill(phrase("Not now"), () => ({action: "deny", req_id: made.request.id})),
    };
    made.answers.give15.classList.add("pill--warn");
    made.answers.deny.classList.add("pill--outline");
    const answering = element("div", "actions");
    answering.append(made.answers.give15, made.answers.give30, made.answers.deny);
    made.ask.append(title, made.detail, answering);

    made.hero = element("section", "hero");
    made.row = element("div", "actions quick");
    made.buttons = {
      unlock: pill(phrase("Unlock"), () => ({action: "lock", on: false})),
      add15: pill(phrase("+15 min"), () => ({action: "add_time", minutes: 15})),
      add30: pill(phrase("+30 min"), () => ({action: "add_time", minutes: 30})),
      lock: pill(phrase("Lock"), () => ({action: "lock", on: true})),
      unlimited: pill(phrase("No limit today"), () => ({action: "skip_limit_today"})),
    };
    made.why = element("p", "why");
    made.note = element("p", "note");
    made.note.setAttribute("role", "status");
    made.note.hidden = true;
    made.today = element("section", "today");

    root.replaceChildren(made.hero, made.row, made.why, made.note, made.today);
    return made;
  }

  /**
   * Whether a request can still be answered: the set is reporting, the question has a
   * believable time of asking, and its ten minutes are not up. The same reading Home
   * Assistant's attribute makes, so the two never disagree about what waits.
   */
  function stillWaiting(tv, request) {
    if (!tv.reporting || !request || typeof request !== "object" || !request.id) {
      return false;
    }
    const at = TS.number(request.asked_at);
    return at !== null && at > 0 && Date.now() - at < REQUEST_MS;
  }

  /** The request panel: on top while one waits, gone once it has been answered. */
  function paintRequest(drawn) {
    const request = drawn.tv.pending_request;
    const waiting = stillWaiting(drawn.tv, request);
    drawn.request = waiting ? request : null;
    if (!waiting) {
      drawn.ask.remove();
      return;
    }
    if (drawn.root.children[0] !== drawn.ask) {
      drawn.root.insertBefore(drawn.ask, drawn.root.children[0] || null);
    }
    const asked = TS.number(request.asked_minutes);
    const app = request.app_name ? String(request.app_name) : "";
    let what = null;
    if (asked !== null) {
      what = app ? phrase("{minutes} min more, in {app}", {minutes: asked, app: app}) :
        phrase("{minutes} min more", {minutes: asked});
    } else if (app) {
      what = app;
    }
    drawn.detail.textContent = [what, ago(request.asked_at)].filter(Boolean)
      .join(" · ");
  }

  function line(name, words) {
    return element("p", name, words);
  }

  function heroWatching(tv) {
    const left = TS.number(tv.remaining_today);
    const limit = TS.number(tv.limit_today);
    const until = TS.number(tv.until_s);
    // Whatever ends viewing first is what is left: the hours closing, bedtime, or a lock
    // coming back when the time granted against it is up. The day's budget is the answer
    // only when nothing ends sooner, and "no limit" never was while a lock was coming back.
    const sooner = until !== null && (left === null || until / SECONDS_PER_MINUTE < left);
    const parts = [line("hero__label", phrase("Left today"))];
    if (sooner) {
      parts.push(line("hero__figure", TS.length(until / SECONDS_PER_MINUTE)));
    } else {
      parts.push(left === null ?
        line("hero__figure hero__figure--word", phrase("No limit")) :
        line("hero__figure", TS.length(left)));
    }
    const under = [];
    // "20 min of 2 h" would read as a share of the limit, which a closing window is not.
    if (limit !== null && !sooner) {
      under.push(phrase("of {time}", {time: TS.length(limit)}));
    }
    if (until !== null) {
      const end = new Date(Date.now() + Math.max(0, until) * MS_PER_SECOND);
      under.push(phrase("allowed until {clock}", {clock: TS.clock(end)}));
    }
    if (under.length) parts.push(line("hero__sub", under.join(" · ")));
    if (limit !== null && limit > 0) {
      const used = TS.number(tv.used_today);
      const spent = used !== null ? used : limit - (left || 0);
      const meter = element("div", "meter");
      meter.setAttribute("aria-hidden", "true");
      const fill = element("span");
      fill.style.width = Math.min(100, Math.max(0, (spent / limit) * 100)).toFixed(1) +
        "%";
      meter.appendChild(fill);
      parts.push(meter);
    }
    return parts;
  }

  function heroLocked(tv) {
    const badge = element("div", "badge");
    badge.appendChild(padlock());
    const parts = [badge, line("hero__figure hero__figure--word", phrase("Locked"))];
    if (Object.prototype.hasOwnProperty.call(REASONS, tv.lock_reason)) {
      parts.push(line("hero__reason", REASONS[tv.lock_reason]));
    }
    const used = TS.number(tv.used_today);
    const under = [again(tv),
      used === null ? null : phrase("{time} watched today", {time: TS.length(used)})];
    if (under.some(Boolean)) {
      parts.push(line("hero__sub", under.filter(Boolean).join(" · ")));
    }
    return parts;
  }

  function heroAway(tv) {
    const seen = TS.seen(tv.last_reported);
    return [
      line("hero__label", phrase("Last seen")),
      tv.last_reported ?
        line("hero__figure hero__figure--clock", seen || "—") :
        line("hero__figure hero__figure--word", phrase("Never reported.")),
      line("hero__sub", phrase("Switched off or without a network.") + " " +
        phrase("Its rules keep working on the television.")),
      line("hero__sub", phrase("Changes will wait until it is back.")),
    ];
  }

  /**
   * The buttons for this state, in order, the first of them the one most wanted.
   *
   * Only the ones that change something on the television for this lock: a button that
   * sends a command the set then ignores tells a parent the child is covered by
   * something that did nothing. Added minutes are a bonus on the day's limit, a parent's
   * lock standing down, or a bedtime moved on; "No limit today" sets the day's limit
   * aside and nothing else; Unlock lifts a parent's lock, the bedtime, or the hours and
   * the limit for the rest of the day. Nothing here reaches an app's own budget or the
   * allow-list, so a lock for those offers no button at all.
   */
  function quick(tv, away) {
    const limited = TS.number(tv.limit_today) !== null;
    // A set that is not listening still takes a lock: the switch holds it and sends it
    // the moment the set is back, which is when a parent most wants it (#48). Nothing
    // else is held — a command sent into the dark is lost — so nothing else is offered.
    if (away) return [tv.locked ? "unlock" : "lock"];
    if (!tv.locked) {
      return (limited ? ["add15", "add30", "lock", "unlimited"] : ["lock"]);
    }
    switch (tv.lock_reason) {
      case "daily_limit":
        return ["unlock", "add15", "add30"].concat(limited ? ["unlimited"] : []);
      case "manual":
      case "sleep_timer":
        return ["unlock", "add15", "add30"];
      case "app_limit":
      case "app_not_allowed":
        return [];
      // The hours, and a reason this page has no words for: lifting the lock is the
      // one thing the set does with either.
      default:
        return ["unlock"];
    }
  }

  function paintActions(drawn, away) {
    const wanted = quick(drawn.tv, away);
    const order = wanted.map((name) => drawn.buttons[name]);
    // Moved only when the order really changes: moving a button takes the focus off it.
    const showing = Array.from(drawn.row.children).filter((one) => !one.hidden);
    if (showing.length !== order.length || showing.some((one, at) => one !== order[at])) {
      const rest = Object.keys(drawn.buttons).filter((name) => wanted.indexOf(name) < 0)
        .map((name) => drawn.buttons[name]);
      drawn.row.replaceChildren(...order, ...rest);
    }
    Object.keys(drawn.buttons).forEach((name) => {
      const button = drawn.buttons[name];
      const at = wanted.indexOf(name);
      button.hidden = at < 0;
      // No primary while none of them can be used: a faded mint still reads as "this one".
      button.className = "pill" + (at === 0 && !away ? " pill--accent" :
        (name === "lock" || name === "unlimited" || away ? " pill--outline" : ""));
      button.disabled = sending;
    });
    Object.keys(drawn.answers).forEach((name) => {
      drawn.answers[name].disabled = sending || away;
    });
    drawn.why.textContent = held(drawn.tv);
    drawn.why.hidden = !away;
    drawn.row.hidden = !wanted.length;
  }

  /** What a set that is not listening will be told when it is back, in one sentence. */
  function held(tv) {
    if (tv.lock_pending === "lock") return phrase("It will lock as soon as it is back.");
    if (tv.lock_pending === "unlock") {
      return phrase("It will unlock if it is back within 15 minutes.");
    }
    return phrase("A lock waits until it is back; the rest needs it on.");
  }

  function paintToday(drawn, away) {
    const watched = (drawn.tv.apps || [])
      .map((app) => ({name: app.name || app.package, minutes: TS.number(app.minutes)}))
      // Under half a minute reads as "0 min": a second charged between apps, not viewing.
      .filter((app) => app.minutes !== null && Math.round(app.minutes) > 0)
      .sort((one, other) => other.minutes - one.minutes);
    const parts = [element("h2", "heading", phrase("Today"))];
    const used = TS.number(drawn.tv.used_today);
    // A set that is not answering cannot say what is playing, so the day's total is
    // the one figure worth putting where the screen's large number would be.
    const rows = away && used !== null ?
      [{name: phrase("Watched"), minutes: used}].concat(watched) : watched;
    if (!rows.length) parts.push(element("p", "empty", phrase("Nothing watched yet today.")));
    rows.forEach((app) => {
      const row = element("div", "row");
      row.append(element("span", "row__name", String(app.name)),
        element("span", "row__value", TS.length(app.minutes)));
      parts.push(row);
    });
    drawn.today.replaceChildren(...parts);
  }

  function paint(drawn) {
    if (!drawn.root.contains(drawn.hero)) return;
    const tv = drawn.tv;
    const away = !tv.reporting;
    paintRequest(drawn);
    drawn.hero.replaceChildren(...(away ? heroAway(tv) :
      tv.locked ? heroLocked(tv) : heroWatching(tv)));
    drawn.hero.classList.toggle("hero--locked", !away && Boolean(tv.locked));
    paintActions(drawn, away);
    paintToday(drawn, away);
  }

  TS.screens.now = {
    reason: reason,

    render(root, tv) {
      if (!view || view.root !== root || !root.contains(view.hero)) view = build(root);
      view.tv = tv;
      paint(view);
    },
  };
})();
