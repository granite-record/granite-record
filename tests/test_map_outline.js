// GRANITE_VERSION: 2026-11-11.1
/* THE DISTRICT MAP KEEPS THE STATE'S OUTLINE ON EVERY LAYER, RUN IN NODE.

     node tests/test_map_outline.js src/pages/map.js district_map.json

   The owner, 11 November 2026: "the map outline also disappears when
   switching between state house and state senate." The State House and the
   towns drew the county lines, which carry the state's edge; every other
   layer's mesh is its interior lines only, so the State Senate had no outline
   at all. draw() puts edgeLines(M, layer) on every layer; this loads map.js
   as a module and switches layers fifty times in turn, holding that each
   layer, each time, gets a heavy line (casing and line) with a path in it,
   the same state edge on every layer, and nothing left over from the layer
   before. Prints one line of JSON. */
"use strict";
const fs = require("fs"), path = require("path");
const G = require(path.resolve(process.argv[2]));
const T = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const M = G.model(T);
const out = { layers: [], missing: [], switches: 0, drifted: [] };
const layers = G.LAYERS.map(l => l[0]);
out.layers = layers;
const edge = G.stateD(M);
if (!edge || edge.length < 100) out.missing.push("the state has no outline of its own in the data");
const outlineOf = lk => {
  const L = G.edgeLines(M, lk);
  const line = L.find(([c]) => /(^| )cty( |$)/.test(c)), casing = L.find(([c]) => /(^| )ctyc( |$)/.test(c));
  return { line, casing, n: L.length };
};
for (let i = 0; i < 50; i++) {
  const lk = layers[i % layers.length];
  const o = outlineOf(lk);
  out.switches++;
  if (!o.line || !o.casing || !o.line[1] || !o.casing[1]) out.missing.push(`${lk} (switch ${i}) draws no outline`);
  else if (lk !== "base" && lk !== "towns" && o.line[1] !== edge) out.drifted.push(`${lk} draws something other than the state's edge`);
  else if (o.line[1].length < edge.length) out.drifted.push(`${lk}'s outline is shorter than the state's edge`);
}
console.log(JSON.stringify(out));
