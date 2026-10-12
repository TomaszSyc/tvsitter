// The History screen: what was watched today, and over the last seven days, by app.
//
// Two lists, each the longest first, and nothing to press. The figure that matters is
// the total at the head of each list, in mint; the rows under it say where it went.
// The apps the rules never reach (the launcher, the lock screen) are left out of both,
// the way Apps leaves them out, so the lists read the same side by side.
//
// There is nothing here to keep focus or an edit, so every poll draws the screen again
// from what was reported rather than patching it.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;

  function element(tag, name, words) {
    const made = document.createElement(tag);
    if (name) made.className = name;
    if (words !== undefined) made.textContent = words;
    return made;
  }

  /** Apps with time on them, without what no rule reaches, the longest first. */
  function rowsOf(list, exempt) {
    return list
      .filter((one) => one && one.package && !exempt.includes(one.package))
      .map((one) => ({
        name: String(one.name || one.package),
        minutes: TS.number(one.minutes) || 0,
      }))
      // What rounds to "0 min" is the set passing through an app, not anybody watching.
      .filter((one) => Math.round(one.minutes) > 0)
      .sort((one, other) => other.minutes - one.minutes ||
        (one.name < other.name ? -1 : one.name > other.name ? 1 : 0));
  }

  function total(rows) {
    return rows.reduce((sum, one) => sum + one.minutes, 0);
  }

  function row(one) {
    const made = element("div", "app");
    const text = element("span", "app__text");
    text.appendChild(element("span", "app__title ellipsis", one.name));
    made.append(TS.tile(one.name), text,
      element("span", "app__value", TS.length(one.minutes)));
    return made;
  }

  /** A heading with the figure that sums its list at the end of the line. */
  function head(words, minutes) {
    const made = element("div", "history__head");
    made.appendChild(element("h2", "heading", words));
    if (minutes > 0) made.appendChild(element("b", "history__total", TS.length(minutes)));
    return made;
  }

  function today(tv, exempt) {
    const apps = rowsOf(Array.isArray(tv.apps) ? tv.apps : [], exempt);
    // The television's own count includes what the list cannot name, so it wins.
    const used = TS.number(tv.used_today);
    const parts = [head(phrase("Today"), used !== null && used > 0 ? used : total(apps))];
    if (!apps.length) parts.push(element("p", "empty", phrase("Nothing watched yet today.")));
    return parts.concat(apps.map(row));
  }

  function week(tv, exempt) {
    const known = Array.isArray(tv.week_by_app);
    const apps = known ? rowsOf(tv.week_by_app, exempt) : [];
    const parts = [head(phrase("Last seven days"), total(apps))];
    const before = TS.number(tv.used_yesterday);
    if (before !== null) {
      parts.push(element("p", "history__line",
        phrase("Yesterday {time}", {time: TS.length(before)})));
    }
    if (!known) {
      parts.push(element("p", "empty",
        phrase("The last seven days are not available from this television yet.")));
    } else if (!apps.length) {
      parts.push(element("p", "empty", phrase("Nothing watched in the last seven days.")));
    }
    return parts.concat(apps.map(row));
  }

  window.TS.screens.history = {
    render(root, tv) {
      const exempt = Array.isArray(tv.exempt_apps) ? tv.exempt_apps : [];
      const parts = element("div", "history");
      parts.append(...today(tv, exempt), ...week(tv, exempt));
      root.replaceChildren(parts);
    },
  };
})();
