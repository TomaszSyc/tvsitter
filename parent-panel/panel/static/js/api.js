// The page's one connection: the state it reads and the changes it sends.
//
// Both addresses are relative, because an Ingress App is served under a path the
// Supervisor invents per session. Neither request ever throws at its caller: a phone
// that has just woken is offline for a second, and a screen that has to catch that
// itself is a screen that one day forgets to.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;

  // `loaded` stays false until the first answer with televisions in it, so the page
  // does not say "no televisions yet" in the second before Home Assistant has answered.
  TS.state = {televisions: [], current: null, error: null, loaded: false};

  // Requests are numbered, so an answer that took longer than a later one cannot land
  // on top of it: a poll can still be in flight when a change is sent and read back.
  let asked = 0;
  let landed = 0;

  TS.api = {
    POLL_MS: 5000,

    /**
     * Read the state, and say whether anything new was read.
     *
     * What was last read is kept when nothing better arrives — a failed request, or an
     * answer that carries a reason and no televisions, which is what the add-on sends
     * when Home Assistant itself is not answering. Blanking the page for either would
     * be the panel's own fault; the reason goes in `error` and the shell says it.
     */
    async state() {
      const ticket = (asked += 1);
      let read = null;
      try {
        const back = await fetch("api/state", {headers: {"Accept": "application/json"}});
        read = (await back.json()) || {};
      } catch (failure) {
        if (ticket < landed) return false;
        landed = ticket;
        TS.state.error = phrase("No connection to Home Assistant");
        return false;
      }
      if (ticket < landed) return false;
      landed = ticket;
      const list = Array.isArray(read.televisions) ? read.televisions : [];
      // The add-on's own sentences are in the catalogue, so they are said in the page's
      // language; one that is not falls back to itself.
      TS.state.error = read.error ? phrase(String(read.error)) : null;
      if (read.error && !list.length) return false;
      TS.state.televisions = list;
      TS.state.loaded = true;
      if (!list.some((tv) => tv.id === TS.state.current)) {
        TS.state.current = list.length ? list[0].id : null;
      }
      return true;
    },

    /**
     * Ask for a change, then read the state back before answering.
     *
     * Whether a change is in force or waiting for a sleeping television is the state's
     * answer and not this one's, so the caller hears back only once the screen has
     * been redrawn from it. The answer is `{ok, error}` either way.
     */
    async act(body) {
      let answer = null;
      try {
        const back = await fetch("api/do", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        });
        answer = await back.json();
      } catch (failure) {
        answer = {ok: false, error: phrase("The panel could not reach the add-on.")};
      }
      if (TS.refresh) await TS.refresh();
      else await TS.api.state();
      if (!answer || typeof answer !== "object") answer = {ok: false};
      if (!answer.ok && !answer.error) answer.error = phrase("Home Assistant refused it.");
      return answer;
    },
  };

  /** The television being looked at, or null when there is none. */
  TS.tv = function tv() {
    return TS.state.televisions.find((one) => one.id === TS.state.current) || null;
  };
})();
