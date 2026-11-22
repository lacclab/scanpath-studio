// Exercise the replay frame reader independently of the player and its clock.
"use strict";

const fs = require("fs");
const assert = require("node:assert/strict");
const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const gd = { layout: config.layout || { meta: {} }, on() {} };
gd.layout.meta.scanpath_playback_speed = 0;
let calls = 0;
global.document = { getElementById: () => gd };
global.Plotly = { addFrames() { calls += 1; } };

new Function(config.script.split("{plot_id}").join("plot"))();
assert.equal(calls, 0, "a replay registered frames before playback");
const frames = Array.from({length: config.count}, (_, i) => gd._spsFrameAt(i));
for (const i of [0, config.count - 1, Math.floor(config.count / 2), 0]) {
  assert.deepEqual(gd._spsFrameAt(i), frames[i]);
}
process.stdout.write(JSON.stringify({ calls, frames }));
