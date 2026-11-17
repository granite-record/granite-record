// A pack bench_pack.py wrote, loaded into the fake D1 with the bench's schema,
// as `wrangler d1 execute --file` loads it into the real one, and then used:
// a contributor's link and the owner's are each given what they hold, and one
// answer is kept. Prints one line of JSON. preflight's _bench_pack runs it on a
// pack drawn from a fixture, so the Python that writes a pack and the
// JavaScript that serves one are held to each other.
//   node tests/bench/apply_pack.js <pack.sql> [<pack.sql> ...]

import { readFileSync } from "node:fs";
import { judge, linkFor, next } from "../../workers/bench/store.js";
import { addLink, makeBench } from "./world.js";

const d1 = makeBench();
for (const f of process.argv.slice(2)) d1.sql.exec(readFileSync(f, "utf8"));
const count = (sql) => d1.sql.prepare(sql).get().n;
const sam = await linkFor(d1, (await addLink(d1, { id: "sam234", name: "Sam" })).token);
const owner = await linkFor(d1, (await addLink(d1, { id: "owner2", name: "You", role: "owner" })).token);
const now = new Date();
const given = {};
for (const q of ["timing", "topic", "tag"]) given[q] = (await next(d1, sam, [q], now)).map(x => x.queue);
const mine = await next(d1, owner, ["topic"], now);
let kept = null;
const first = (await next(d1, sam, ["topic"], now))[0];
if (first) kept = await judge(d1, sam, { ref: first.ref, answer: { answer: "no", better: undefined } }, now);
console.log(JSON.stringify({
  items: count("SELECT COUNT(*) AS n FROM items"),
  open: count("SELECT COUNT(*) AS n FROM items WHERE state = 'open'"),
  elsewhere: count("SELECT COUNT(*) AS n FROM items WHERE state = 'elsewhere'"),
  groups: count("SELECT COUNT(*) AS n FROM groups"),
  calib: count("SELECT COUNT(*) AS n FROM calib"),
  queues: d1.rows("queues").map(r => [r.queue, r.pool, r.judged, r.options ? JSON.parse(r.options).length : 0]),
  given, owner: mine.length, kept,
}));
