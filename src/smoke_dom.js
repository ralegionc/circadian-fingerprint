/*
 * Headless smoke test for the page's rendering code.
 *
 * The preview pane could not serve the page (its assigned port was taken), so
 * instead of shipping unverified chart code this shims just enough DOM for the
 * engine to actually run against the real payload. It catches the errors that
 * matter here: missing data keys, bad indexing, undefined helpers. It does not
 * check layout, which is what the look at the published page is for.
 */
const fs = require("fs");
const path = require("path");

const INDEX = path.join(__dirname, "..", "site", "index.html");
const html = fs.readFileSync(INDEX, "utf8");

const VARS = {
  "--accent": "#256abf", "--surface": "#ffffff", "--surface-sunk": "#eaecf0",
  "--rule": "#d6d9e0", "--rule-soft": "#e4e6ec", "--ink": "#14161a",
  "--ink-2": "#4d545f", "--ink-3": "#79818e", "--paper": "#f4f5f7",
  "--night": "#eda100",
  "--s0": "#eef4fd", "--s1": "#cde2fb", "--s2": "#9ec5f4", "--s3": "#6da7ec",
  "--s4": "#3987e5", "--s5": "#256abf", "--s6": "#184f95", "--s7": "#0d366b",
  "--d-lo3": "#184f95", "--d-lo2": "#2a78d6", "--d-lo1": "#9ec5f4",
  "--d-mid": "#e6e6e2", "--d-hi1": "#f3b0ae", "--d-hi2": "#e34948",
  "--d-hi3": "#9e2726"
};

let created = 0;

function makeEl(tag) {
  created++;
  const el = {
    tagName: String(tag).toLowerCase(),
    children: [],
    attrs: {},
    dataset: {},
    style: {
      setProperty(k, v) { this[k] = v; },
      getPropertyValue(k) { return this[k] || ""; }
    },
    className: "",
    textContent: "",
    title: "",
    clientWidth: 900,
    _html: "",
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; this.children = []; },
    appendChild(c) { this.children.push(c); return c; },
    setAttribute(k, v) {
      this.attrs[k] = String(v);
      if (String(v) === "undefined" || String(v) === "NaN") {
        throw new Error(`<${this.tagName}> attribute ${k} set to ${v}`);
      }
    },
    getAttribute(k) { return this.attrs[k]; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener() {},
    removeEventListener() {},
    closest(sel) { return sel === ".tile" && this.className === "tile" ? this : null; },
    querySelectorAll() { return []; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 20 }; },
    getContext() { return ctx2d; },
    get firstChild() { return this.children[0]; }
  };
  return el;
}

const ctx2d = new Proxy({}, {
  get(_t, prop) {
    if (prop === "canvas") return makeEl("canvas");
    return function () { return undefined; };
  },
  set() { return true; }
});

const registry = {};
const IDS = ["lang-tiles", "tiles-toggle", "phase-strip", "amp-bars",
  "lang-detail", "wiki-weekday", "gh-tiles", "cross-hours", "gh-bot-lines", "gh-weekday", "gh-review-large",
  "topic-scatter", "lang-table", "rank-en-quiet", "rank-en-busy", "rank-en-weekend",
  "rank-en-weekday", "rank-ja-night", "rank-ja-day"];
IDS.forEach(function (id) { registry[id] = makeEl("div"); });

const documentElement = makeEl("html");

global.window = {
  devicePixelRatio: 1,
  matchMedia() { return { matches: false, addEventListener() {}, addListener() {} }; },
  addEventListener() {},
  getComputedStyle() {
    return { getPropertyValue(k) { return VARS[k] !== undefined ? VARS[k] : "#256abf"; } };
  }
};
global.document = {
  documentElement: documentElement,
  body: makeEl("body"),
  createElement: makeEl,
  createElementNS(_ns, tag) { return makeEl(tag); },
  getElementById(id) { return registry[id] || null; },
  querySelectorAll() { return []; },
  addEventListener() {}
};
global.getComputedStyle = global.window.getComputedStyle;
global.MutationObserver = function () { return { observe() {} }; };
global.setTimeout = function () { return 0; };
global.clearTimeout = function () {};

const blocks = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)]
  .map(function (m) { return m[1]; });

console.log(`running ${blocks.length} script blocks`);
blocks.forEach(function (src, i) {
  try {
    // eslint-disable-next-line no-new-func
    new Function("window", "document", "getComputedStyle", "MutationObserver",
                 "setTimeout", "clearTimeout", src)
      .call(global.window, global.window, global.document, global.getComputedStyle,
            global.MutationObserver, global.setTimeout, global.clearTimeout);
    console.log(`  block ${i + 1}: ok`);
  } catch (e) {
    console.error(`  block ${i + 1}: FAILED\n    ${e.stack.split("\n").slice(0, 4).join("\n    ")}`);
    process.exitCode = 1;
  }
});

const filled = IDS.filter(function (id) {
  return registry[id].children.length > 0 || registry[id]._html;
});
console.log(`\nelements created: ${created}`);
console.log(`hosts populated: ${filled.length}/${IDS.length}`);
IDS.forEach(function (id) {
  const n = registry[id].children.length;
  console.log(`  ${n > 0 ? "+" : "-"} ${id}: ${n} children`);
});
