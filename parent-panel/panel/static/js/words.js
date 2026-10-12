// What to say, in whatever language Home Assistant is set to.
//
// The first of the page's scripts, and the one every other one leans on: it opens the
// namespace the rest add their parts to, and it is how every sentence reaches the
// screen.
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
})();
