"use strict";
// A DOM small enough to read and large enough to run the panel's page.
//
// The page is sixty kilobytes of JavaScript that nothing but a browser could run, so
// until this existed the only thing that ever exercised it was a parent, on a phone,
// finding out that a poll had wiped what they had just drawn. It is not a browser and
// is not trying to be one: no layout, no cascade, no painting. Just enough of a tree,
// enough events and enough geometry that the page's own code runs and can be asked
// what it did.
//
// TV Sitter — parental control for Android TV / Google TV.
// Copyright (C) 2026 Tomasz Syc
// SPDX-License-Identifier: AGPL-3.0-only

class Ev {
  constructor(type, props) {
    this.type = type;
    this.defaultPrevented = false;
    this.target = null;
    Object.assign(this, props || {});
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() {}
}

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.hidden = false;
    this.style = {};
    this.tabIndex = 0;
    this.disabled = false;
    this._text = "";
    this._classes = new Set();
    this._attrs = new Map();
    this._on = new Map();
    const own = this;
    this.classList = {
      add(name) { own._classes.add(name); },
      remove(name) { own._classes.delete(name); },
      contains(name) { return own._classes.has(name); },
      toggle(name, force) {
        const on = force === undefined ? !own._classes.has(name) : Boolean(force);
        if (on) own._classes.add(name); else own._classes.delete(name);
        return on;
      },
    };
  }
  get className() { return [...this._classes].join(" "); }
  set className(words) {
    this._classes = new Set(String(words).split(" ").filter(Boolean));
  }
  get textContent() {
    return this._text + this.children.map((one) => one.textContent).join("");
  }
  set textContent(words) {
    this.children.forEach((one) => { one.parentNode = null; });
    this.children = [];
    this._text = words === null || words === undefined ? "" : String(words);
  }
  appendChild(node) {
    if (node.parentNode) node.remove();
    node.parentNode = this;
    this.children.push(node);
    return node;
  }
  append(...nodes) { nodes.forEach((node) => this.appendChild(node)); }
  insertBefore(node, before) {
    if (!before) return this.appendChild(node);
    if (node.parentNode) node.remove();
    node.parentNode = this;
    this.children.splice(this.children.indexOf(before), 0, node);
    return node;
  }
  replaceChildren(...nodes) {
    this.children.forEach((one) => { one.parentNode = null; });
    this.children = [];
    nodes.forEach((node) => this.appendChild(node));
  }
  remove() {
    if (!this.parentNode) return;
    const where = this.parentNode.children.indexOf(this);
    if (where >= 0) this.parentNode.children.splice(where, 1);
    this.parentNode = null;
  }
  contains(node) {
    for (let at = node; at; at = at.parentNode) if (at === this) return true;
    return false;
  }
  matches(selector) {
    if (selector.startsWith(".")) return this._classes.has(selector.slice(1));
    return this.tagName === selector.toUpperCase();
  }
  closest(selector) {
    for (let at = this; at; at = at.parentNode) {
      if (at.matches && at.matches(selector)) return at;
    }
    return null;
  }
  setAttribute(name, value) { this._attrs.set(name, String(value)); }
  getAttribute(name) {
    return this._attrs.has(name) ? this._attrs.get(name) : null;
  }
  addEventListener(type, listener) {
    if (!this._on.has(type)) this._on.set(type, []);
    this._on.get(type).push(listener);
  }
  dispatchEvent(event) {
    if (!event.target) event.target = this;
    for (let at = this; at; at = at.parentNode) {
      (at._on.get(event.type) || []).forEach((listener) => {
        event.currentTarget = at;
        listener.call(at, event);
      });
    }
    return !event.defaultPrevented;
  }
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = null; }
  // Enough geometry for the code that places things over the grid. Boxes are laid out
  // as though the week were a real one: each cell fifteen wide and thirty tall, rows
  // stacked down the page. Nothing here is a layout engine — it exists so that code
  // asking where a box is gets an answer rather than an exception.
  getBoundingClientRect() {
    const left = (this.atSlot === undefined ? 0 : this.atSlot * 16) + 100;
    const top = (this.atDay === undefined ? 0 : this.atDay * 31) + 200;
    return {left: left, top: top, width: 15, height: 30,
      right: left + 15, bottom: top + 30, x: left, y: top};
  }
  get offsetWidth() { return this.hidden ? 0 : 140; }
  setPointerCapture() {}
  releasePointerCapture() {}
  scrollIntoView() {}
}

const document = new El("#document");
document.activeElement = null;
document.hidden = false;
document.createElement = (tag) => new El(tag);
const known = new Map();
["banner", "nothing", "chooser", "tabs", "rail", "panels", "lead", "which",
  "go-now", "go-today", "go-rules", "go-apps"].forEach((id) => {
  const node = new El("div");
  node.id = id;
  // A destination in the rail is a mark and then its name, in that order, which is
  // what the page reaches into when it puts the name into the reader's language. An
  // empty box here would let that go untested and still pass.
  if (id.startsWith("go-")) {
    node.appendChild(new El("svg"));
    node.appendChild(new El("span"));
  }
  known.set(id, node);
  document.appendChild(node);
});
document.getElementById = (id) => known.get(id) || null;
document.elementFromPoint = () => null;

/** Fire an event at one node and let it bubble the way a browser would. */
function fire(node, type, props) {
  const event = new Ev(type, props);
  event.target = node;
  node.dispatchEvent(event);
  return event;
}

/** Every element under one node with a class, in document order. */
function all(node, name, into) {
  const found = into || [];
  node.children.forEach((one) => {
    if (one.classList.contains(name)) found.push(one);
    all(one, name, found);
  });
  return found;
}

module.exports = {El, Ev, document, fire, all};
