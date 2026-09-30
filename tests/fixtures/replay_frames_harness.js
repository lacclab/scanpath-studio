// PERF-17: run the script `plots.replay_page` hands a replay's page against a
// fake Plotly, and print the frames it gives `Plotly.addFrames` as JSON.
//
//   node replay_frames_harness.js config.json
//
// config: {"script": "<the post_script>"}. The fake graph div carries an empty
// `layout.meta` and gets its frames on `addFrames`, so the player that follows
// the decoder finds no clock and stands down without scheduling anything.
"use strict";

const fs = require("fs");

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const gd = { layout: { meta: {} }, on() {} };
let added = null;
let calls = 0;

global.document = {
  getElementById: (id) => (id === "plot" ? gd : null),
  addEventListener() {},
  removeEventListener() {},
};
global.Plotly = {
  addFrames(target, frames) {
    if (target !== gd) throw new Error("addFrames on the wrong div");
    calls += 1;
    added = frames;
    gd._transitionData = { _frames: frames };
    return Promise.resolve();
  },
};

new Function(config.script.split("{plot_id}").join("plot"))();
process.stdout.write(JSON.stringify({ calls, frames: added }));
