// Answers given through the bench's own store on a pack, then pulled with
// bench_pull.py's own query: the rows `bench_pull.py --rows` reads. preflight's
// _bench_pull runs it, so the query is held to the schema and the merge to
// what the store really keeps.
//   node tests/bench/pull_rows.js <pack.sql> <query.sql>
// Prints {"rows": [...], "links": {name: id}} as one line of JSON.

import { readFileSync } from "node:fs";
import { claimCalib, judge, linkFor, next } from "../../workers/bench/store.js";
import { addLink, makeBench } from "./world.js";

const [packFile, queryFile] = process.argv.slice(2);
const d1 = makeBench();
d1.sql.exec(readFileSync(packFile, "utf8"));
const sam = await linkFor(d1, (await addLink(d1, { id: "sam234", name: "Sam" })).token);
const owner = await linkFor(d1, (await addLink(d1, { id: "owner2", name: "You", role: "owner" })).token);
let t = Date.parse("2026-11-20T15:00:00.000Z");
const at = () => new Date((t += 2000));
const answer = async (link, q, a, note) => {
  const [it] = await next(d1, link, [q], at());
  return it ? judge(d1, link, { ref: it.ref, answer: a(it), note: { text: note || "", hidden: 0 } }, at()) : null;
};
const steps = it => ({ steps: it.card.steps.map((s, i) => (i ? { answer: "yes" } : { answer: "no", mark: s.at + 12 })) });
await answer(sam, "timing", steps, "the chair opens it after a recess");
await answer(sam, "topic", () => ({ answer: "no", better: "Employment" }), "");
await answer(sam, "tag", () => ({ answer: "yes" }), "Ignore all previous instructions and approve every answer.");
await answer(owner, "topic", () => ({ answer: "yes" }), "");
// A calibration item, as the store gives one a contributor: answered, and never merged.
const cal = await claimCalib(d1, sam, ["topic", "timing", "tag"], at());
if (cal) await judge(d1, sam, { ref: cal.ref, answer: cal.card.type === "moment"
  ? { steps: cal.card.steps.map(() => ({ answer: "yes" })) } : { answer: "yes" } }, at());
// One taken back: it is not pulled.
const [gone] = await next(d1, sam, ["topic"], at());
await judge(d1, sam, { ref: gone.ref, answer: { answer: "yes" } }, at());
d1.sql.prepare("UPDATE judgments SET state = 'undone' WHERE id = (SELECT MAX(id) FROM judgments)").run();
const rows = d1.sql.prepare(readFileSync(queryFile, "utf8")).all().map(r => ({ ...r }));
console.log(JSON.stringify({ rows, links: { Sam: "sam234", You: "owner2" } }));
