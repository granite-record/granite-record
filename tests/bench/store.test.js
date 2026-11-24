// workers/bench/store.js and schema.sql on the fake D1: what is kept about a
// person, an item served once, holds, answers in the ledger's words, the
// limits, undo, calibration and the owner's Links page.

import test from "node:test";
import assert from "node:assert/strict";
import { CALIB_EVERY, DAILY_CAP, HELD_MOST, answersOf, claimCalib, farAlong, hold, linkFor, linkList,
         makeLink, next, progress, queueLabels, setState, takeBack, toLedger, touch, undo, judge }
  from "../../workers/bench/store.js";
import { TOPICS, addLink, at, loadPack, makeBench, momentCard, tagCard, topicCard } from "./world.js";

async function bench(opts) {
  const d1 = makeBench();
  await loadPack(d1, opts);
  const owner = await addLink(d1, { id: "owner2", name: "You", role: "owner" });
  const sam = await addLink(d1, { id: "sam234", name: "Sam" });
  const ann = await addLink(d1, { id: "ann234", name: "Ann" });
  const L = async x => linkFor(d1, x.token);
  return { d1, owner: await L(owner), sam: await L(sam), ann: await L(ann), tokens: { owner, sam, ann } };
}

const yes = { answer: "yes" };
const stepsYes = n => ({ steps: Array.from({ length: n }, () => ({ answer: "yes" })) });

test("the schema keeps no column about a person but the link's name and two days", () => {
  const d1 = makeBench();
  const cols = Object.fromEntries(d1.tables().map(t => [t, d1.columns(t)]));
  assert.deepEqual(cols.links, ["id", "name", "token_hash", "role", "queues", "state", "made_on", "last_on",
                                "daily_cap"]);
  assert.deepEqual(Object.keys(cols).sort(),
                   ["ask_answers", "asks", "calib", "calib_holds", "groups", "items", "judgments", "link_days", "links",
                    "queues"]);
  const all = Object.values(cols).flat().join(" ");
  assert.doesNotMatch(all, /\b(ip|email|mail|address|cookie|agent|device|browser|referr?er|session|token)\b/i,
    "no column for an address, a cookie, a device or a referrer, and none for a token but its hash");
  assert.equal(all.match(/\bname\b/g).length, 1, "one name, the link's");
});

test("a token finds its link in one read; a wrong or malformed one finds nothing", async () => {
  const { d1, tokens } = await bench();
  const before = d1.prepared.length;
  assert.equal((await linkFor(d1, tokens.sam.token)).name, "Sam");
  assert.equal(d1.prepared.length - before, 1, "one statement");
  assert.equal(await linkFor(d1, "x".repeat(43)), null);
  const n = d1.prepared.length;
  assert.equal(await linkFor(d1, "short"), null);
  assert.equal(await linkFor(d1, tokens.sam.token + "x"), null);
  assert.equal(d1.prepared.length, n, "a malformed token asks the database nothing");
  assert.ok(d1.everyCell().every(c => !c.includes(tokens.sam.token)), "no token is kept, only its hash");
});

test("an item is served once: two links never hold one item, and each holds two at most", async () => {
  const { d1, sam, ann } = await bench();
  const a = await next(d1, sam, ["timing"], at(0));
  const b = await next(d1, ann, ["timing"], at(0));
  assert.equal(a.length, HELD_MOST);
  assert.equal(b.length, HELD_MOST);
  const keys = [...a, ...b].map(x => x.key);
  assert.equal(new Set(keys).size, keys.length, "no item given twice");
  const again = await next(d1, sam, ["timing"], at(30));
  assert.deepEqual(again.map(x => x.key), a.map(x => x.key), "asking again gives what it holds, nothing more");
  const held = d1.rows("items").filter(r => r.held_by === "sam234");
  assert.equal(held.length, HELD_MOST);
  // ONE STATEMENT: the claim is the UPDATE that RETURNs what it took.
  assert.ok(d1.prepared.some(s => /^UPDATE items SET held_by = \?1, held_until = \?2 WHERE rowid = \(SELECT/.test(s)
    && /RETURNING/.test(s)));
});

test("a hold lapses after ten minutes unless the open page renews it", async () => {
  const { d1, sam, ann } = await bench({ timings: 2 });
  const mine = await next(d1, sam, ["timing"], at(0));
  assert.equal(mine.length, 2);
  assert.deepEqual(await next(d1, ann, ["timing"], at(9 * 60)), [], "held, so nothing for another");
  assert.equal(await hold(d1, sam, at(9 * 60)), 2, "renewed at nine minutes");
  assert.deepEqual(await next(d1, ann, ["timing"], at(15 * 60)), [], "still held at fifteen");
  const theirs = await next(d1, ann, ["timing"], at(19 * 60 + 1));
  assert.equal(theirs.length, 2, "a page closed for ten minutes lets its items go");
  assert.equal(await hold(d1, sam, at(19 * 60 + 2)), 0, "a lapsed hold is not renewed");
  // ... and not even one nobody has taken since: the page that lost it asks again.
  const b = await bench({ timings: 2 });
  await next(b.d1, b.sam, ["timing"], at(0));
  assert.equal(await hold(b.d1, b.sam, at(10 * 60 + 1)), 0, "a hold lapsed a second ago is not renewed");
});

test("an answer is kept in the ledger's words, and its item judged in the same batch", async () => {
  const { d1, sam } = await bench();
  const [first] = await next(d1, sam, ["timing"], at(0));
  const steps = first.card.steps.length;
  const r = await judge(d1, sam, { ref: first.ref, note: { text: "after a recess", hidden: 0 },
    answer: { steps: [{ answer: "no", mark: 754 }, ...Array(steps - 1).fill({ answer: "yes" })] } }, at(1));
  assert.deepEqual(r, { ok: true, verdict: "wrong", side: "no", calib: false });
  const j = d1.rows("judgments").at(-1);
  assert.equal(j.verdict, "wrong");
  assert.deepEqual(JSON.parse(j.fields), steps === 2 ? { start: "no", observed_start: "0:12:34", end: "yes" }
                                                    : { start: "no", observed_start: "0:12:34" });
  assert.equal(j.note, "after a recess");
  const it = d1.rows("items").find(x => x.key === first.key);
  assert.equal(it.state, "judged");
  assert.equal(it.held_by, null);
  assert.deepEqual(await judge(d1, sam, { ref: first.ref, answer: stepsYes(steps) }, at(5)),
                   { ok: false, why: "gone" }, "an item answered is not answered twice");
  // The batch is one: a judgment that does not go in takes no item with it.
  const [second] = await next(d1, sam, ["timing"], at(6));
  d1.failWhen = sql => /^UPDATE items SET state = 'judged'/.test(sql) ? new Error("disk") : null;
  await assert.rejects(judge(d1, sam, { ref: second.ref, answer: stepsYes(second.card.steps.length) }, at(7)));
  d1.failWhen = null;
  assert.equal(d1.rows("judgments").length, 1, "the answer rolled back with its item");
  // A reference that is no item's, or not a reference at all.
  assert.deepEqual(await judge(d1, sam, { ref: "i99999", answer: yes }, at(9)), { ok: false, why: "gone" });
  assert.deepEqual(await judge(d1, sam, { ref: "x'; DROP TABLE items", answer: yes }, at(9)),
                   { ok: false, why: "bad" });
  assert.match(first.ref, /^i\d+$/);
});

test("an item not held, a second answer within a second, and the day's cap are refused", async () => {
  const { d1, sam, ann } = await bench({ timings: 8, topics: 4 });
  const [a1, a2] = await next(d1, sam, ["topic"], at(0));
  const [b1] = await next(d1, ann, ["topic"], at(0));
  assert.deepEqual(await judge(d1, sam, { ref: b1.ref, answer: yes }, at(1)),
                   { ok: false, why: "gone" }, "another's item");
  assert.ok((await judge(d1, sam, { ref: a1.ref, answer: yes }, at(1))).ok);
  assert.deepEqual(await judge(d1, sam, { ref: a2.ref, answer: yes }, at(1.5)),
                   { ok: false, why: "fast" }, "one answer a second");
  assert.ok((await judge(d1, sam, { ref: a2.ref, answer: yes }, at(2.2))).ok);
  d1.sql.prepare("UPDATE links SET daily_cap = 3 WHERE id = 'sam234'").run();
  const capped = { ...sam, daily_cap: 3 };
  const [c1, c2] = await next(d1, capped, ["timing"], at(3));
  assert.ok((await judge(d1, capped, { ref: c1.ref, answer: stepsYes(c1.card.steps.length) },
                         at(4))).ok, "the third of three");
  assert.deepEqual(await judge(d1, capped, { ref: c2.ref, answer: stepsYes(c2.card.steps.length) },
                               at(6)), { ok: false, why: "full" }, "a fourth, past the cap of three");
  assert.equal(d1.rows("link_days").find(r => r.link === "sam234").n, 3);
  assert.equal(DAILY_CAP, 500);
});

test("only an answer the card takes is kept", () => {
  const m = momentCard("HB 1", 100, 200), m1 = momentCard("HB 1", 100, null);
  const t = topicCard("HB 2", "Police"), g = tagCard("SB 3", "Medicaid");
  assert.deepEqual(toLedger(m, null, stepsYes(2)), { verdict: "correct", side: "yes", fields: { start: "yes", end: "yes" } });
  assert.deepEqual(toLedger(m1, null, { steps: [{ answer: "unsure" }] }),
                   { verdict: "unsure", side: "unsure", fields: { start: "unsure" } });
  assert.deepEqual(toLedger(m, null, { steps: [{ answer: "yes" }, { answer: "no", mark: 3725.4 }] }),
                   { verdict: "wrong", side: "no", fields: { start: "yes", end: "no", observed_end: "1:02:05" } });
  assert.deepEqual(toLedger(m, null, { steps: [{ answer: "no" }, { answer: "unsure" }] }).verdict, "wrong",
                   "a No outweighs a Not sure");
  assert.equal(toLedger(m, null, stepsYes(1)), null, "a step missing");
  assert.equal(toLedger(m, null, { steps: [{ answer: "yes", mark: 5 }, { answer: "yes" }] }), null,
               "a moment marked with a Yes");
  assert.equal(toLedger(m, null, { steps: [{ answer: "no", mark: -1 }, { answer: "yes" }] }), null);
  assert.equal(toLedger(m, null, { steps: [{ answer: "maybe" }, { answer: "yes" }] }), null);
  assert.deepEqual(toLedger(t, TOPICS, { answer: "no", better: "Employment" }),
                   { verdict: "wrong", side: "no", fields: { better_topic: "Employment" } });
  assert.equal(toLedger(t, TOPICS, { answer: "yes", better: "Employment" }), null, "a better topic with a Yes");
  assert.equal(toLedger(t, TOPICS, { answer: "no", better: "Not a topic" }), null, "a topic not the site's");
  assert.deepEqual(toLedger(g, null, { answer: "no" }), { verdict: "no", side: "no", fields: {} });
  assert.equal(toLedger(g, null, { answer: "partly" }), null, "no partly on the hosted bench");
  assert.equal(toLedger(g, null, { answer: "no", better: "x" }), null, "a tag has no better answer");
});

test("undo takes back the latest answer alone, and gives its item back to the same person", async () => {
  const { d1, sam, ann } = await bench({ topics: 4 });
  const [a1, a2] = await next(d1, sam, ["topic"], at(0));
  await judge(d1, sam, { ref: a1.ref, answer: yes }, at(1));
  await judge(d1, sam, { ref: a2.ref, answer: { answer: "no" } }, at(3));
  const back = await undo(d1, sam, at(4));
  assert.equal(back.key, a2.key, "the latest");
  assert.equal(await undo(d1, sam, at(5)), null, "a second undo takes nothing more");
  assert.equal(d1.rows("judgments").filter(j => j.state === "undone").length, 1);
  assert.equal(d1.rows("items").find(x => x.key === a2.key).held_by, "sam234");
  const theirs = await next(d1, ann, ["topic"], at(6));
  assert.ok(!theirs.some(x => x.key === a2.key), "the item taken back is not given to another");
  const mine = await next(d1, sam, ["topic"], at(7));
  assert.equal(mine[0].key, a2.key, "it is the next shown");
  assert.ok((await judge(d1, sam, { ref: a2.ref, answer: yes }, at(8))).ok, "answered again");
  d1.sql.prepare("UPDATE judgments SET state = 'merged'").run();
  assert.equal(await undo(d1, sam, at(9)), null, "a merged answer cannot be taken back");
});

test("one item in twenty-five a contributor is given is one the owner judged, never one it answered", async () => {
  const { d1, sam, owner } = await bench({ topics: 40, calib: 2 });
  let given = [], n = 0;
  for (let i = 0; i < 30; i++) {
    const held = await next(d1, sam, ["topic"], at(n));
    const it = held[0];
    given.push(it);
    n += 2;
    const r = await judge(d1, sam, { ref: it.ref, answer: yes }, at(n));
    assert.ok(r.ok, JSON.stringify(r));
  }
  const cal = given.map((x, i) => [i + 1, x]).filter(([, x]) => x.calib);
  assert.deepEqual(cal.map(([i]) => i), [25], "the 25th");
  assert.ok(cal[0][1].key.startsWith("topic|2021-2022|HB90"), cal[0][1].key);
  assert.equal(d1.rows("judgments").filter(j => j.calib === 1).length, 1);
  assert.equal(d1.rows("items").filter(x => x.state === "judged").length, 29, "a calibration answer judges no item");
  const ownerGiven = await next(d1, owner, ["topic"], at(n + 2));
  assert.ok(ownerGiven.every(x => !x.calib), "the owner is never given her own again");
  const [s] = (await linkList(d1)).filter(l => l.id === "sam234");
  assert.equal(s.asked, 1);
  assert.equal(s.agree, 1, "hers was Yes on the first, and so was Sam's");
  assert.equal(CALIB_EVERY, 25);
  // Never one this link has answered: the next is the other, and then none.
  const c2 = await claimCalib(d1, sam, ["topic"], at(n + 4));
  assert.equal(c2.key, "topic|2021-2022|HB901");
  assert.ok((await judge(d1, sam, { ref: c2.ref, answer: { answer: "yes" } }, at(n + 6))).ok);
  assert.equal(await claimCalib(d1, sam, ["topic"], at(n + 8)), null, "both answered: none left for Sam");
  // Taking back a link's answers leaves its calibration answers: the evidence.
  assert.equal(await takeBack(d1, "sam234"), 29);
  assert.equal(d1.rows("judgments").filter(j => j.calib === 1 && j.state === "kept").length, 2);
  const [s2] = (await linkList(d1)).filter(l => l.id === "sam234");
  assert.deepEqual([s2.asked, s2.agree], [2, 1], "hers was No on the second, Sam's Yes");
});

test("a link judges only its queues, and a queue no longer chosen lets its holds go", async () => {
  const { d1, tokens } = await bench();
  const tagOnly = await linkFor(d1, (await addLink(d1, { id: "tag234", queues: ["tag"] })).token);
  assert.deepEqual(await next(d1, tagOnly, ["timing", "topic"], at(0)), []);
  assert.ok((await next(d1, tagOnly, ["timing", "topic", "tag"], at(0))).every(x => x.queue === "tag"));
  const sam = await linkFor(d1, tokens.sam.token);
  await next(d1, sam, ["timing"], at(0));
  await next(d1, sam, ["topic"], at(1));
  assert.ok(d1.rows("items").filter(x => x.held_by === "sam234").every(x => x.queue === "topic"));
  assert.deepEqual((await queueLabels(d1, tagOnly)).map(q => q.queue), ["tag"]);
});

test("the owner's Links page: a new link shown once, pause, take back and turn off", async () => {
  const { d1, sam, owner } = await bench({ topics: 6 });
  const made = await makeLink(d1, { name: "  Civics\nclass ", queues: ["tag", "nonsense"] }, at(0));
  assert.match(made.id, /^[a-z2-9]{6}$/);
  assert.match(made.token, /^[A-Za-z0-9_-]{43}$/);
  const row = d1.rows("links").find(l => l.id === made.id);
  assert.equal(row.name, "Civics class");
  assert.deepEqual(JSON.parse(row.queues), ["tag"]);
  assert.equal(await makeLink(d1, { name: "", queues: ["tag"] }, at(0)), null);
  assert.equal(await makeLink(d1, { name: "x", queues: [] }, at(0)), null);
  const [a1, a2] = await next(d1, sam, ["topic"], at(0));
  await judge(d1, sam, { ref: a1.ref, answer: yes }, at(1));
  await judge(d1, sam, { ref: a2.ref, answer: yes }, at(3));
  await touch(d1, sam, at(3));
  let s = (await linkList(d1)).find(l => l.id === "sam234");
  assert.deepEqual([s.answers, s.unmerged, s.last_on], [2, 2, "2026-11-20"]);
  const seen = await answersOf(d1, "sam234");
  assert.equal(seen.length, 2);
  assert.equal(seen[0].head, "HB 201 · 2023-2024");
  assert.equal(await takeBack(d1, "sam234", seen[0].id), 1, "one taken back");
  assert.equal(d1.rows("items").find(x => x.key === a2.key).state, "open");
  assert.equal(await takeBack(d1, "sam234"), 1, "the rest");
  s = (await linkList(d1)).find(l => l.id === "sam234");
  assert.deepEqual([s.answers, s.unmerged], [0, 0]);
  await next(d1, sam, ["topic"], at(10));
  assert.equal(await setState(d1, "sam234", "paused"), 1);
  assert.equal(d1.rows("items").filter(x => x.held_by === "sam234").length, 0, "paused lets go");
  assert.equal(await setState(d1, owner.id, "off"), 0, "the owner's own link is not turned off here");
  assert.equal(await setState(d1, "sam234", "off"), 1);
  assert.equal(await setState(d1, "sam234", "active"), 0, "a link turned off stays off");
  const list = await linkList(d1);
  assert.equal(list.at(-1).role, "owner", "the owner's last, as the mockup has it");
});

test("how far along: a group's judged of its goal, and each queue's share of its pool", async () => {
  const { d1, sam } = await bench({ timings: 6, topics: 4 });
  const [a1] = await next(d1, sam, ["topic"], at(0));
  await judge(d1, sam, { ref: a1.ref, answer: yes }, at(1));
  assert.deepEqual(await progress(d1, "topic|2023-2024"),
                   { grp: "topic|2023-2024", label: "Bills of 2023-2024", goal: 4, done: 1 });
  d1.sql.prepare("UPDATE items SET state = 'elsewhere' WHERE key = 'topic|2023-2024|HB203'").run();
  assert.equal((await progress(d1, "topic|2023-2024")).goal, 3, "one judged on the laptop leaves the group");
  const far = await farAlong(d1);
  assert.deepEqual(far.map(q => [q.queue, q.judged, q.pool]),
                   [["timing", 34, 12545], ["topic", 45, 31449], ["tag", 18, 1994]]);
});
