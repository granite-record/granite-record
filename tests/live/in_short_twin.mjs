// In short's twin, the browser's half (preflight's _in_short_twin): reads
// {wordbook, words, cases: [{r, body}]} on stdin, loads components.js,
// motions.js and live.js as a page does, and writes, for each case,
// [motions.classify's key, GRLive.voteSaid's sentence], as JSON. preflight
// holds them equal to motions.py and build_session_pages.vote_said.
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = rel => readFileSync(new URL(`../../${rel}`, import.meta.url), "utf8");
let s = "";
process.stdin.on("data", d => { s += d; });
process.stdin.on("end", () => {
  const { wordbook, words, cases } = JSON.parse(s);
  const ctx = vm.createContext({ console, Intl, Date, Math, JSON, WORDBOOK: wordbook });
  ctx.window = ctx;
  for (const f of ["src/pages/components.js", "src/pages/motions.js", "src/pages/live.js"]) {
    vm.runInContext(read(f), ctx, { filename: f });
  }
  const L = ctx.GRLive;
  const W = { closing: wordbook.closing, recommendation: words.recommendation, roll_call: words.roll_call };
  const out = cases.map(c => [L.motionOf(c.r, c.body).mk, L.voteSaid(c.r, c.body, W)]);
  process.stdout.write(JSON.stringify(out));
});
