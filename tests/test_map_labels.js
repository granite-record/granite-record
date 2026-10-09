// GRANITE_VERSION: 2026-10-09.1
/* THE DISTRICT MAP'S LABEL RULE, RUN IN NODE.

     node tests/test_map_labels.js src/pages/map.js district_map.json

   preflight runs this ("the district map's labels never overlap, in any of
   its three modes") on the real geometry, with the map's data built from the
   tracked files. It loads map.js as a module, as a page loads it as a script,
   and lays out the labels of every layer in every mode over a set of views a
   reader reaches: the whole state, and each of twelve places at four zooms,
   in the map's box at 1366, 768 and 375 pixels wide; in Town names, with and
   without a chosen town and district. It prints one line of JSON: how many
   layouts it ran, every pair of labels that overlap, every name outside the
   view or under the zoom buttons, every label of the wrong kind for its
   mode, and what each mode shows where the design says something about it.

   THE WIDTHS ARE A STAND-IN for the browser's measure of Public Sans:
   a width per kind of character, in em. The rule is held to never overlapping
   by its OWN measure, which is the property that matters: in a browser it
   measures with the real face and the same rule applies. */
"use strict";
const fs = require("fs"), path = require("path");
const G = require(path.resolve(process.argv[2]));
const T = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const M = G.model(T);

function measure(txt, weight, px) {
  let em = 0;
  for (const c of String(txt)) {
    if (/[il.,'’:;|!I]/.test(c)) em += 0.28;
    else if (/[fjrt()\-–]/.test(c)) em += 0.37;
    else if (c === " ") em += 0.26;
    else if (/[mwMW]/.test(c)) em += 0.86;
    else if (/[A-Z&]/.test(c)) em += 0.68;
    else if (/[0-9]/.test(c)) em += 0.6;
    else em += 0.56;
  }
  return em * px * (weight >= 600 ? 1.04 : weight <= 400 ? 0.98 : 1);
}

// the map's box at each width (map.css: min(76vh, 700px) tall on a desktop,
// 64vh on a phone; the panel beside it above 860px)
const BOXES = { 1366: [660, 684], 768: [734, 684], 375: [341, 520] };
const ZOOMS = [1, 1.4 ** 2, 1.4 ** 4, 1.4 ** 6, 1.4 ** 7];
const PLACES = ["Manchester", "Nashua", "Concord", "Portsmouth", "Dover", "Rochester",
  "Keene", "Lebanon", "Laconia", "Pittsburg", "Conway", "Salem"];
const LAYERS = G.LAYERS.map(l => l[0]);

function view(W, H, z, town) {
  const vb = [0, 0, T.w, T.h], s = Math.min(W * z / vb[2], H * z / vb[3]), sw = W * z, sh = H * z;
  const ox0 = (sw - vb[2] * s) / 2, oy0 = (sh - vb[3] * s) / 2;
  let sl = 0, st = 0;
  if (town) {
    const b = G.fbox(M, "towns", town);
    sl = ox0 + ((b[0] + b[2]) / 2 - vb[0]) * s - W / 2;
    st = oy0 + ((b[1] + b[3]) / 2 - vb[1]) * s - H / 2;
  }
  sl = Math.max(0, Math.min(sw - W, sl));
  st = Math.max(0, Math.min(sh - H, st));
  // the zoom buttons: three of 2.75rem, .25rem apart, .5rem from the corner
  return { vb, s, ox: ox0 - sl, oy: oy0 - st, vw: W, vh: H, obstacles: [[W - 8 - 140, 8, W - 8, 52]] };
}

const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
const out = { layouts: 0, overlaps: [], outside: [], wrongKind: [], full: {}, manchester: {}, modes: {} };
out.modes = { labels: G.LABELS, default: G.DEFAULT_LABELS };
const t0 = Date.now();

function run(where, V, S) {
  const L = G.layout(M, V, S);
  out.layouts++;
  const boxes = L.shown.map(l => [l, l.box]).concat(L.tag ? [[L.tag, L.tag.box]] : []);
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++)
      if (hit(boxes[i][1], boxes[j][1]) && out.overlaps.length < 20)
        out.overlaps.push(`${where}: "${boxes[i][0].text}" over "${boxes[j][0].text}"`);
  for (const [l, b] of boxes) {
    const under = V.obstacles.some(o => hit(b, o));
    const off = S.mode === "names" && (b[0] < 0 || b[1] < 0 || b[2] > V.vw || b[3] > V.vh);
    if ((under || off) && out.outside.length < 20)
      out.outside.push(`${where}: "${l.text}" ${under ? "under the zoom buttons" : "outside the view"}`);
  }
  const want = S.mode === "names" ? /^nm( |$)/ : S.mode === "numbers" ? /^lab$/ : null;
  for (const l of L.shown)
    if ((!want || !want.test(l.cls)) && out.wrongKind.length < 20)
      out.wrongKind.push(`${where}: "${l.text}" drawn as ${l.cls} in ${S.mode}`);
  return L;
}

for (const [W, H] of Object.values(BOXES)) {
  for (const z of ZOOMS) {
    for (const town of z === 1 ? [null] : PLACES) {
      const V = view(W, H, z, town);
      for (const layer of LAYERS) {
        for (const mode of ["names", "numbers", "none"]) {
          const S = { mode, layer, here: null, ward: null, frame: null, dim: false, picked: null,
                      rootPx: 16, measure, zoom: z };
          const where = `${W}px ${layer} ${mode} x${z.toFixed(2)} ${town || "state"}`;
          const L = run(where, V, S);
          if (z === 1) out.full[`${W} ${layer} ${mode}`] = L.shown.length;
          // a chosen town, and the district holding it chosen with it
          if (town && mode === "names" && (layer === "base" || layer === "senate")) {
            const w0 = Object.values(T.places[town].w)[0];
            run(where + " chosen", V, Object.assign({}, S, { here: town,
              picked: [layer, layer === "base" ? w0[0] : w0[2]] }));
          }
        }
      }
    }
  }
  // the first press of + (x1.4 each) at which Manchester's wards are
  // numbered, and named, with the city in the middle of the box
  for (const mode of ["numbers", "names"]) {
    let k = 0;
    for (; k <= 8; k++) {
      const z = Math.min(12, 1.4 ** k), V = view(W, H, z, "Manchester");
      const L = G.layout(M, V, { mode, layer: "base", rootPx: 16, measure, zoom: z });
      const ward = mode === "numbers"
        ? L.shown.some(l => M.group.base[l.id.slice(2)] === "Manchester")
        : L.shown.some(l => l.id.startsWith("w:Manchester|"));
      if (ward) break;
    }
    out.manchester[`${W} ${mode}`] = k <= 8 ? k : null;
  }
}
out.ms = Date.now() - t0;
console.log(JSON.stringify(out));
