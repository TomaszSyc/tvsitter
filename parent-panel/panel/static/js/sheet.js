// The bottom sheet: the one raised surface, and the one place the panel edits in.
//
// `open(build)` hands `build` the sheet's body to fill and shows it over a dimmed page;
// `close()` puts it away and gives the focus back to whatever had it. One sheet at a
// time, because two layers of editing on a phone is a parent who no longer knows which
// one Save belongs to.
//
// It lives outside the screen, on the body, so the poll that redraws the screen every
// five seconds cannot reach it: what a parent is halfway through choosing in here stays
// exactly as they left it until they save, cancel or tap outside.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const FOCUSABLE = "button:not([disabled]), select:not([disabled]), " +
    "input:not([disabled]), [tabindex]:not([tabindex='-1'])";

  let layer = null;
  let cameFrom = null;
  let made = 0;

  function element(tag, name) {
    const one = document.createElement(tag);
    if (name) one.className = name;
    return one;
  }

  /** The first node under `node` that passes, in document order. */
  function first(node, test) {
    for (const one of Array.from(node.children || [])) {
      if (test(one)) return one;
      const found = first(one, test);
      if (found) return found;
    }
    return null;
  }

  function focusable(sheet) {
    return sheet.querySelectorAll ? Array.from(sheet.querySelectorAll(FOCUSABLE)) : [];
  }

  /**
   * Keep the keyboard inside while the sheet is up: everything behind it is under a
   * backdrop that says it cannot be used, and a Tab that wandered back there would be
   * a focus nobody can see.
   */
  function trap(event, sheet) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const stops = focusable(sheet);
    if (!stops.length) return;
    const at = stops.indexOf(document.activeElement);
    if (event.shiftKey && at <= 0) {
      event.preventDefault();
      stops[stops.length - 1].focus();
    } else if (!event.shiftKey && at === stops.length - 1) {
      event.preventDefault();
      stops[0].focus();
    }
  }

  function close() {
    if (!layer) return;
    layer.remove();
    layer = null;
    const back = cameFrom;
    cameFrom = null;
    // Only to something still on the page: a sheet that saved may have redrawn the
    // very button that opened it.
    if (back && back.focus && document.contains(back)) back.focus();
  }

  function open(build) {
    close();
    cameFrom = document.activeElement;
    made += 1;

    layer = element("div", "sheet__layer");
    const backdrop = element("div", "sheet__backdrop");
    backdrop.setAttribute("aria-hidden", "true");
    backdrop.addEventListener("click", close);
    const sheet = element("div", "sheet");
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.tabIndex = -1;
    const grab = element("div", "sheet__grab");
    grab.setAttribute("aria-hidden", "true");
    const body = element("div", "sheet__body");
    sheet.append(grab, body);
    layer.append(backdrop, sheet);
    sheet.addEventListener("keydown", (event) => trap(event, sheet));

    build(body);

    // Named by its own title, which `build` gives the class `sheet__title`.
    const title = first(body, (one) => one.classList && one.classList.contains("sheet__title"));
    if (title) {
      title.id = title.id || "ts-sheet-title-" + made;
      sheet.setAttribute("aria-labelledby", title.id);
    }
    document.body.appendChild(layer);
    // Into the sheet, so a screen reader is where the thumb is. The first control
    // rather than Save: whatever the sheet is for, it starts at the top.
    const start = focusable(sheet)[0] || sheet;
    start.focus();
  }

  TS.sheet = {
    open: open,
    close: close,
    /** Whether a sheet is up, for a screen that should not act behind one. */
    isOpen: () => layer !== null,
  };
})();
