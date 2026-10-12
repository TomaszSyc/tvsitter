// The Settings screen, behind the gear: the parent's PIN and where requests go, the
// television's own switches, and what it last said about itself.
//
// Three groups and no cards, rows with a hairline between them. Nothing here is on the
// five-second poll except the television's own fields; the phones the house has are a
// registry read of their own, so they are asked for when the screen opens and again
// after a change, never on the beat.
//
// The screen is built once per root and updated in place afterwards, so a PIN being
// typed, a choice being made or a question being asked survives every poll. A PIN
// leaves the field the moment it is read, whether or not it is sent: a field that
// keeps it is a PIN that whoever next picks up the phone can read.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

(() => {
  "use strict";

  const TS = window.TS;
  const phrase = TS.phrase;

  const PIN_LENGTH = 4;
  const MINUTE_MS = 60000;
  const MINUTES_PER_HOUR = 60;
  const DASH = "—";
  // The warnings a parent is offered, in minutes; nought is none. A warning the set
  // already has that is not among them is offered as well, so it is never hidden.
  const WARNINGS = [0, 1, 2, 3, 5, 10, 15, 20, 30];

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
  function say(note, words, bad) {
    note.textContent = words || "";
    note.hidden = !words;
    note.classList.toggle("note--quiet", !bad);
  }

  function note() {
    const made = element("p", "note note--quiet");
    made.setAttribute("role", "status");
    made.hidden = true;
    return made;
  }

  /** The mark on the back button: a chevron, static geometry only. */
  function chevron() {
    const space = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(space, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const line = document.createElementNS(space, "path");
    line.setAttribute("d", "M15 5l-7 7 7 7");
    svg.appendChild(line);
    return svg;
  }

  /** A group's name, and what follows it. */
  function group(name, ...parts) {
    const made = element("section", "settings__group");
    made.append(element("h2", "heading group", name), ...parts);
    return made;
  }

  /** A row: its title on the left, and what it holds on the right. */
  function row(title, control) {
    const made = element("div", "set");
    made.append(element("p", "set__title", title), control);
    return made;
  }

  function value() {
    return element("p", "set__value");
  }

  /** How long ago the television last reported, as briefly as is still true. */
  function reported(when) {
    if (!when) return DASH;
    const at = new Date(when).getTime();
    if (!Number.isFinite(at)) return DASH;
    const minutes = Math.floor((Date.now() - at) / MINUTE_MS);
    if (minutes < 1) return phrase("just now");
    if (minutes < MINUTES_PER_HOUR) return phrase("{count} min ago", {count: minutes});
    return phrase("at {clock}", {clock: TS.seen(when)});
  }

  /** A notify service, as the phone somebody would call it. */
  function called(service) {
    const bare = service.replace("notify.mobile_app_", "").split("_").join(" ");
    return bare ? bare[0].toUpperCase() + bare.slice(1) : service;
  }

  /** Fill one picker with the phones, leaving whatever is chosen chosen. */
  function offer(into, phones, chosen, none) {
    into.replaceChildren();
    const blank = element("option", null, none);
    blank.value = "";
    into.appendChild(blank);
    phones.forEach((phone) => {
      const one = element("option", null, called(phone));
      one.value = phone;
      into.appendChild(one);
    });
    into.value = chosen && phones.includes(chosen) ? chosen : "";
  }

  /** The warnings on offer, with the one the television holds among them. */
  function warnings(held) {
    const list = WARNINGS.slice();
    if (held !== null && !list.includes(held)) {
      list.push(held);
      list.sort((one, other) => one - other);
    }
    return list;
  }

  // ---- The parts of the screen. ----

  /** The parent's PIN: set or not, a field to set it, and a way to take it away. */
  function pinPart(view) {
    const state = value();
    const input = element("input", "field");
    input.setAttribute("type", "password");
    input.type = "password";
    input.inputMode = "numeric";
    input.setAttribute("inputmode", "numeric");
    input.autocomplete = "off";
    input.setAttribute("autocomplete", "off");
    input.maxLength = PIN_LENGTH;
    input.setAttribute("maxlength", String(PIN_LENGTH));
    input.placeholder = "••••";
    input.setAttribute("aria-label", phrase("New PIN"));
    const set = pill(phrase("Set the PIN"), "pill--accent");
    const entry = element("div", "entry");
    entry.append(input, set);

    // Two taps rather than one, because it is the tap that cannot be undone: the PIN
    // is not kept anywhere, so a stray tap is a PIN to think of again and type into
    // the television.
    const ask = pill(phrase("Remove the PIN"), "pill--outline");
    const yes = pill(phrase("Yes, remove it"), "pill--danger");
    const no = pill(phrase("Keep it"), "pill--outline");
    const why = element("p", "hint",
      phrase("Without a PIN, a lock can only be lifted from Home Assistant."));
    const drop = element("div", "actions actions--start");
    drop.append(ask, yes, no);
    const where = note();
    const arm = (on) => {
      ask.hidden = on;
      yes.hidden = !on;
      no.hidden = !on;
      why.hidden = !on;
    };
    arm(false);

    set.addEventListener("click", async () => {
      const typed = input.value.trim();
      input.value = "";
      if (typed.length !== PIN_LENGTH || !/^[0-9]+$/.test(typed)) {
        say(where, phrase("A PIN is four digits."), true);
        return;
      }
      await view.act({id: view.tv.id, action: "set_pin", pin: typed}, where,
        phrase("PIN set"));
    });
    ask.addEventListener("click", () => arm(true));
    no.addEventListener("click", () => arm(false));
    yes.addEventListener("click", async () => {
      arm(false);
      await view.act({id: view.tv.id, action: "clear_pin"}, where,
        phrase("PIN removed"));
    });

    view.pin = {state, drop, arm};
    return [row(phrase("Parent PIN"), state), entry, drop, why, where];
  }

  /** Where a request for more time is sent: a phone, and a second device. */
  function phonesPart(view) {
    const first = element("select", "setting__select");
    first.setAttribute("aria-label", phrase("Send time requests to"));
    const second = element("select", "setting__select");
    second.setAttribute("aria-label", phrase("Second device"));
    const save = pill(phrase("Save"), "pill--accent");
    const where = note();
    const nothing = element("p", "empty empty--start");
    nothing.hidden = true;
    const picks = element("div", "picks");
    picks.append(row(phrase("Send time requests to"), first),
      row(phrase("Second device"), second));
    const actions = element("div", "actions actions--start");
    actions.append(save);
    view.phones = {first, second, picks, actions, nothing, where, save};

    save.addEventListener("click", async () => {
      save.disabled = true;
      say(where, phrase("Saving…"), false);
      let answer = null;
      try {
        const back = await fetch("api/setup", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            id: view.tv.id,
            notify: first.value,
            also_notify: second.value,
          }),
        });
        answer = await back.json();
      } catch (failure) {
        answer = {ok: false, error: phrase("The panel could not reach the add-on.")};
      }
      // Read back before saying anything, the way every other change does: what was
      // made is Home Assistant's answer rather than this one's guess.
      await view.listen();
      save.disabled = false;
      if (answer && answer.ok) say(where, phrase("Saved"), false);
      else {
        say(where, phrase((answer && answer.error) || "Home Assistant refused it."),
          true);
      }
    });
    return [picks, actions, nothing, where];
  }

  /** The two things the television is told once and keeps: a warning, and a block. */
  function televisionPart(view) {
    const warn = element("select", "setting__select");
    warn.setAttribute("aria-label", phrase("Warning before the end"));
    const warned = note();
    warn.addEventListener("change", async () => {
      if (warn.value === "") return;
      view.holding = true;
      await view.act({id: view.tv.id, action: "number", key: "warn_before",
        value: Number(warn.value)}, warned);
      view.holding = false;
      view.update();
    });

    const block = element("button", "switch");
    block.setAttribute("type", "button");
    block.setAttribute("role", "switch");
    block.setAttribute("aria-label", phrase("Block Settings on the television"));
    block.appendChild(element("span", "switch__knob"));
    block.addEventListener("click", async () => {
      if (block.disabled) return;
      block.disabled = true;
      await view.act({id: view.tv.id, action: "block_settings",
        on: block.getAttribute("aria-checked") !== "true"}, warned);
      block.disabled = false;
      view.update();
    });

    const followed = value();
    const stop = pill(phrase("Stop following"), "pill--outline pill--small");
    const keeps = element("p", "hint",
      phrase("The hours stay as they are, and the helper is left alone."));
    const idle = element("p", "hint",
      phrase("To take the hours from a schedule, choose one in Home Assistant."));
    stop.addEventListener("click", async () => {
      stop.disabled = true;
      await view.act({id: view.tv.id, action: "stop_following"}, warned);
      stop.disabled = false;
      view.update();
    });

    // The two are rules, so a change to either waits for a sleeping set, and says so here
    // where it was made rather than only on Rules.
    const held = element("p", "held-line",
      phrase("The television is asleep. The change goes when it wakes."));
    held.hidden = true;

    view.television = {warn, block, followed, stop, keeps, idle, held};
    return [
      row(phrase("Warning before the end"), warn),
      row(phrase("Block Settings on the television"), block), held,
      row(phrase("Hours from a Home Assistant schedule"), followed),
      keeps, idle, stop, warned,
    ];
  }

  function statusPart(view) {
    const version = value();
    const last = value();
    view.status = {version, last};
    return [row(phrase("Version on the television"), version),
      row(phrase("Last report"), last)];
  }

  // ---- Putting the television's fields on the parts. ----

  function update(view) {
    const tv = view.tv;
    const set = Boolean(tv.pin_set);
    view.pin.state.textContent = phrase(set ? "Set" : "Not set");
    view.pin.drop.hidden = !set;
    if (!set) view.pin.arm(false);

    const warn = view.television.warn;
    // What a change waiting for a sleeping set says, over what the set reports: read
    // the other way, the choice snapped back once the shell stopped holding it.
    const heldWarn = TS.held(tv, "warn_before_s");
    const heldBlock = TS.held(tv, "block_settings");
    view.television.held.hidden = heldWarn === undefined && heldBlock === undefined;
    const warnSeconds = heldWarn === undefined ? null : TS.number(heldWarn);
    const held = heldWarn === undefined ? TS.number(tv.warn_before) :
      warnSeconds === null ? null : warnSeconds / 60;
    // What a parent is choosing is not written over while the choice travels.
    if (!view.holding && document.activeElement !== warn) {
      warn.replaceChildren();
      if (held === null) {
        const none = element("option", null, DASH);
        none.value = "";
        warn.appendChild(none);
      }
      warnings(held).forEach((minutes) => {
        const one = element("option", null,
          minutes ? TS.length(minutes) : phrase("Off"));
        one.value = String(minutes);
        warn.appendChild(one);
      });
      warn.value = held === null ? "" : String(held);
    }

    const on = heldBlock === undefined ? Boolean(tv.block_settings) : Boolean(heldBlock);
    view.television.block.setAttribute("aria-checked", String(on));
    view.television.block.classList.toggle("switch--on", on);

    const following = typeof tv.following_schedule === "string" &&
      tv.following_schedule ? tv.following_schedule : null;
    view.television.followed.textContent = following || phrase("Off");
    view.television.stop.hidden = !following;
    view.television.keeps.hidden = !following;
    view.television.idle.hidden = Boolean(following);

    view.status.version.textContent = tv.version ? String(tv.version) : DASH;
    view.status.last.textContent = reported(tv.last_reported);
  }

  /** What the setup says, put on the pickers; or why there is nothing to pick. */
  function listen(view, said) {
    const parts = view.phones;
    const mine = ((said && said.televisions) || [])
      .find((one) => one.id === view.tv.id);
    const phones = (said && said.notify) || [];
    const usable = Boolean(mine && mine.ready) && phones.length > 0;
    parts.picks.hidden = !usable;
    parts.actions.hidden = !usable;
    parts.nothing.hidden = usable;
    if (!usable) {
      parts.nothing.textContent = said && said.error ? phrase(said.error) :
        phrase(mine && !mine.ready ?
          "This television, added by an older integration, has no time request " +
          "to answer." :
          "No phone with the Home Assistant app was found.");
      return;
    }
    offer(parts.first, phones, mine.notify, phrase("Nobody"));
    offer(parts.second, phones, mine.also_notify, phrase("Nobody else"));
  }

  /** The setup, asked apart from the state. */
  async function ask(view) {
    let said = null;
    try {
      const back = await fetch("api/setup", {headers: {"Accept": "application/json"}});
      said = await back.json();
    } catch (failure) {
      said = {error: phrase("The panel could not reach the add-on.")};
    }
    // A screen that has been left is not drawn on, and a later one has asked again.
    if (view === current) listen(view, said);
  }

  // The one screen being drawn. Rebuilt when the shell has emptied its root.
  let current = null;

  function build(root, tv) {
    const view = {root, tv, holding: false};
    view.update = () => {
      view.tv = TS.tv() || view.tv;
      update(view);
    };
    view.listen = () => ask(view);
    /** Send one change, and say how it went; the screen follows what is read back. */
    view.act = async (body, where, saying) => {
      say(where, "", false);
      const answer = await TS.api.act(body);
      if (answer.ok) say(where, saying || "", false);
      else say(where, phrase(answer.error), true);
      view.update();
      return answer;
    };

    const back = element("button", "back");
    back.setAttribute("type", "button");
    back.appendChild(chevron());
    back.appendChild(element("span", null, phrase("Back")));
    back.addEventListener("click", () => TS.back());
    const head = element("header", "settings__head");
    head.append(back, element("h1", "settings__title", phrase("Settings")));

    // Parts first, then the groups: each part registers what the others update.
    const parent = pinPart(view).concat(phonesPart(view));
    const television = televisionPart(view);
    const status = statusPart(view);
    const top = element("div", "settings");
    top.append(head, group(phrase("Parent"), ...parent),
      group(phrase("Television"), ...television),
      group(phrase("Status"), ...status));
    view.top = top;
    root.replaceChildren(top);
    current = view;
    ask(view);
    return view;
  }

  TS.screens.settings = {
    render(root, tv) {
      if (!current || current.root !== root || !root.contains(current.top)) {
        current = build(root, tv);
      }
      current.tv = tv;
      update(current);
    },
  };
})();
