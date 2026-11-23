// Packs bench_pack.py wrote with the owner's list (--asks, --only-asks), loaded one after
// another as the owner loads them, into a bench whose database was made before the list's two
// tables, as production's and the preview's were; and after each, the answers of hers that a
// file names, given through the store. Prints one line of JSON: the tables before; after each
// pack, the list her link is given, how many wait and what each answer was told; the two
// tables' columns; and every answer kept. preflight's _bench_asks_pack runs it, so the Python
// that writes the list and the JavaScript that serves it are held to each other.
//   node tests/bench/apply_asks.js <answers.json> <pack.sql> [<pack.sql> ...]
// answers.json: [[the pack it follows (0 for the first), key, answer, note], ...]
// And with --rule <cases.json>: whether the page's LINK_RULE takes each address, one line.

import { readFileSync } from "node:fs";
import { askAnswer, askList, askWaiting, linkFor } from "../../workers/bench/store.js";
import { LINK_RULE } from "../../workers/bench/page.js";
import { addLink, benchBeforeAsks } from "./world.js";

const args = process.argv.slice(2);
if (args[0] === "--rule") {
  const rule = new RegExp(LINK_RULE);
  console.log(JSON.stringify(JSON.parse(readFileSync(args[1], "utf8")).map(u => rule.test(u))));
  process.exit(0);
}
const [answersFile, ...packs] = args;
const answers = JSON.parse(readFileSync(answersFile, "utf8"));
const d1 = benchBeforeAsks();
const before = d1.tables();
const owner = await linkFor(d1, (await addLink(d1, { id: "owner2", name: "You", role: "owner" })).token);
let t = Date.parse("2026-11-23T18:00:00.000Z");
const steps = [];
for (const [i, f] of packs.entries()) {
  d1.sql.exec(readFileSync(f, "utf8"));
  const said = [];
  for (const [, key, answer, note] of answers.filter(a => a[0] === i))
    said.push(await askAnswer(d1, owner, { key, answer, note: { text: note || "", hidden: 0 } }, new Date((t += 2000))));
  steps.push({ list: (await askList(d1)).map(x => ({ key: x.key, section: x.card.section, title: x.card.title,
                                                      answer: x.answer ? x.answer.answer : null,
                                                      note: x.answer ? x.answer.note : null })),
               waiting: await askWaiting(d1), said });
}
console.log(JSON.stringify({ before, steps, columns: { asks: d1.columns("asks"), ask_answers: d1.columns("ask_answers") },
                             answers: d1.rows("ask_answers").map(r => [r.key, r.answer, r.note]),
                             items: d1.rows("items").length }));
