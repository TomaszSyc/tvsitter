// The bottom sheet, the one raised surface. A stand-in until the screens that edit
// something need it: `open(build)` hands `build` the sheet's body, `close()` puts it away.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  window.TS.sheet = {open() {}, close() {}};
})();
