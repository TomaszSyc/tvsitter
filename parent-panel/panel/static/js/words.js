// What to say, in whatever language Home Assistant is set to.
//
// The first of the page's scripts, and the one every other one leans on: it opens the
// namespace the rest add their parts to, and it is how every sentence reaches the
// screen. The few ways of writing a number down — a length, a time of day — live here
// too, because the header and every screen say them the same way.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = (window.TS = window.TS || {});
  TS.screens = TS.screens || {};

  /**
   * One sentence, in the catalogue's language or in the English it is written in.
   *
   * The English is the key as well as the fallback, so the scripts still read as the
   * sentences they put on the screen, and a language that has no word for one of them
   * says it in English rather than saying nothing at all. `SAID` is the catalogue the
   * shell writes into the document ahead of every script.
   *
   * Values go in afterwards, never by adding strings end to end: the order the pieces
   * of a sentence go in is not the same in every language.
   */
  TS.phrase = function phrase(words, values) {
    let said = (typeof SAID === "object" && SAID && SAID[words]) || words;
    if (values) {
      Object.keys(values).forEach((name) => {
        said = said.split("{" + name + "}").join(String(values[name]));
      });
    }
    return said;
  };

  const MINUTES_PER_HOUR = 60;

  /**
   * A number from the television, or null when it did not send one.
   *
   * The sensors hand numbers over as whatever Home Assistant made of them — a string, a
   * null, "unavailable" — and `Number(null)` is a nought that would read as "nothing
   * left" on a set that simply has no limit.
   */
  TS.number = function number(value) {
    if (value === null || value === undefined || value === "" || value === false) {
      return null;
    }
    const read = Number(value);
    return Number.isFinite(read) ? read : null;
  };

  /**
   * A length somebody reads rather than parses: "45 min", "1 h 15 min", "2 h".
   *
   * Hard spaces all through, so a narrow phone never puts a number on one line and
   * what it counts — or the rest of the length — on the next.
   */
  TS.length = function length(minutes) {
    const total = Math.round(Math.max(0, minutes));
    if (total < MINUTES_PER_HOUR) return total + "\u00a0min";
    const rest = total % MINUTES_PER_HOUR;
    const hours = (total - rest) / MINUTES_PER_HOUR;
    return rest ? hours + "\u00a0h\u00a0" + rest + "\u00a0min" : hours + "\u00a0h";
  };

  /** A time of day on the 24-hour clock the television itself shows. */
  TS.clock = function clock(at) {
    const two = (value) => String(value).padStart(2, "0");
    return two(at.getHours()) + ":" + two(at.getMinutes());
  };

  /**
   * When the television last reported, as briefly as is still true: the time alone
   * when it was today, the date as well when it was not. Null when nothing readable
   * was sent.
   */
  TS.seen = function seen(when) {
    if (!when) return null;
    const at = new Date(when);
    if (Number.isNaN(at.getTime())) return null;
    if (at.toDateString() === new Date().toDateString()) return TS.clock(at);
    return at.toLocaleDateString([], {day: "numeric", month: "short"}) + " " +
      TS.clock(at);
  };
})();
