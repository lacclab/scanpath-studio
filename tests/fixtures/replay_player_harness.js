// BUG-93: drive `plots.animation_player_post_script` against a fake Plotly on a
// simulated 60 Hz display, so tests/test_replay_player.py can check *when* each
// replay frame reaches the screen without a browser.
//
//   node replay_player_harness.js config.json
//
// config = {script, meta, frames, steps}: `script` is the post_script with its
// `{plot_id}` placeholder still in, `meta` is the figure's `layout.meta`, `frames`
// its frame count, and `steps` a list of [op, arg] run in order:
//   ["run_until", ms]   advance the clock, firing display ticks and timers
//   ["click", name]     press the play / pause / restart button
//   ["slider", k]       drag the time slider to frame k
//   ["hide"] ["show"]   the tab goes to the background / comes back
//   ["detach"]          the plot leaves the page (the docs' instant navigation)
// Prints {shown, relayouts, native, listeners} as JSON: every frame put on
// screen with the time it happened, every Plotly.relayout, every button whose
// own Plotly command ran, and how many visibilitychange listeners remain.
"use strict";

const fs = require("fs");

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const TICK_MS = 1000 / 60;

let now = 0;
let rafSeq = 0;
let rafs = new Map();
let timers = [];
const listeners = {};
const visibilityListeners = [];
const log = { shown: [], relayouts: [], native: [] };

// Named like the figure's own buttons (`plots._animation_play_buttons`).
const buttons = ["play", "pause", "restart"].map((name) => ({ name, execute: true }));
const gd = {
  isConnected: true,
  layout: { meta: config.meta, updatemenus: [{ buttons }] },
  _transitionData: {
    _frames: Array.from({ length: config.frames }, (_, k) => ({ name: String(k) })),
  },
  on(event, fn) {
    (listeners[event] = listeners[event] || []).push(fn);
  },
};

function emit(event, data) {
  (listeners[event] || []).forEach((fn) => fn(data));
}

global.performance = { now: () => now };
global.requestAnimationFrame = (cb) => {
  rafs.set(++rafSeq, cb);
  return rafSeq;
};
global.cancelAnimationFrame = (id) => {
  rafs.delete(id);
};
global.setTimeout = (cb, ms) => {
  timers.push({ at: now + (ms || 0), cb });
};
global.document = {
  hidden: false,
  getElementById: (id) => (id === "gd" ? gd : null),
  addEventListener: (event, fn) => {
    if (event === "visibilitychange") visibilityListeners.push(fn);
  },
  removeEventListener: (event, fn) => {
    const at = visibilityListeners.indexOf(fn);
    if (event === "visibilitychange" && at >= 0) visibilityListeners.splice(at, 1);
  },
};
global.Plotly = {
  // Real Plotly draws the frame and then emits `plotly_animatingframe`.
  animate(target, names) {
    const name = String(names[0]);
    log.shown.push([name, now]);
    emit("plotly_animatingframe", { name });
    return Promise.resolve();
  },
  relayout(target, edit) {
    log.relayouts.push(edit);
    for (const [path, value] of Object.entries(edit)) {
      const m = /^updatemenus\[(\d+)\]\.buttons\[(\d+)\]\.(\w+)$/.exec(path);
      if (m) target.layout.updatemenus[+m[1]].buttons[+m[2]][m[3]] = value;
    }
    return Promise.resolve();
  },
};

const flush = () => new Promise((resolve) => setImmediate(resolve));

async function runUntil(until) {
  for (;;) {
    const nextTick = (Math.floor(now / TICK_MS + 1e-9) + 1) * TICK_MS;
    const nextTimer = timers.reduce((t, x) => Math.min(t, x.at), Infinity);
    const next = Math.min(nextTick, nextTimer);
    if (next > until) {
      now = until;
      return;
    }
    now = next;
    if (next === nextTimer) {
      const due = timers.filter((x) => x.at <= now);
      timers = timers.filter((x) => x.at > now);
      due.forEach((x) => x.cb());
    } else {
      // A display tick runs every callback queued before it, like a browser.
      const due = rafs;
      rafs = new Map();
      due.forEach((cb) => cb(now));
    }
    await flush();
  }
}

function click(name) {
  const button = buttons.find((b) => b.name === name);
  // Plotly runs the button's own command unless `execute` is false, then emits.
  if (button.execute !== false) {
    log.native.push(name);
    if (name === "restart") Plotly.animate(gd, ["0"]);
  }
  emit("plotly_buttonclicked", { button, menu: { buttons } });
}

function slider(k) {
  emit("plotly_sliderstart", {});
  emit("plotly_sliderchange", { interaction: true });
  Plotly.animate(gd, [String(k)]); // the slider step's own command
}

function setHidden(hidden) {
  document.hidden = hidden;
  visibilityListeners.slice().forEach((fn) => fn());
}

(async () => {
  // plotly.py wraps a post_script in `.then(function(){ ... })`.
  new Function(config.script.split("{plot_id}").join("gd"))();
  await flush();
  for (const [op, arg] of config.steps) {
    if (op === "run_until") await runUntil(arg);
    else if (op === "click") click(arg);
    else if (op === "slider") slider(arg);
    else if (op === "hide") setHidden(true);
    else if (op === "show") setHidden(false);
    else if (op === "detach") gd.isConnected = false;
    else throw new Error(`unknown step ${op}`);
    await flush();
  }
  log.listeners = visibilityListeners.length;
  process.stdout.write(JSON.stringify(log));
})();
