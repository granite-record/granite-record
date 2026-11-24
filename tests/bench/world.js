// A bench to test on: the fake D1 of tests/follow/ with the bench's own schema
// (workers/bench/schema.sql), a small pack of each kind of card, links, and the
// owner's list for her Your input tab (and a database made before its tables).
// Every token is made at run time and lives only in memory.

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { FakeD1 } from "../follow/fake_d1.js";
import { hashToken } from "../../workers/follow/address.js";
import { newToken } from "../../workers/bench/store.js";

export const SCHEMA = fileURLToPath(new URL("../../workers/bench/schema.sql", import.meta.url));
export const SITE = "https://graniterecord.org";
export const T0 = "2026-11-20T15:00:00.000Z";

export const TOPICS = ["Education - General", "Employment", "Police", "Miscellaneous"];
const CLAIMS = { yes: "correct", no: "wrong", unsure: "unsure" };
const TAGS = { yes: "yes", no: "no", unsure: "unsure" };

export function momentCard(bill, at, end) {
  const step = (field, t) => ({ field, at: t, label: field === "end" ? "the end" : "the start",
    q: field === "end" ? `Does ${bill} end at {t}?` : `Does the chair open ${bill} at {t}?`,
    mark: field === "end" ? "Mark end" : "Mark start", lost: "Can’t find it",
    find: `Play or skip to where ${bill} really ${field === "end" ? "ends" : "starts"}, then mark it. The site said {t}.` });
  return { type: "moment", head: `${bill} · public hearing`, meta: "Election Law · 3 February 2026",
           title: "a title", what: "hearing", player: { host: "youtube", id: "VIDEO000001" },
           steps: end === null ? [step("start", at)] : [step("start", at), step("end", end)], words: CLAIMS };
}

export function topicCard(bill, claim) {
  return { type: "claim", head: `${bill} · 2023-2024`, title: "relative to a thing.", what: "topic",
           label: "The drafters’ analysis", body: "This bill does a thing.", q: "Is {claim} a fair topic for it?",
           claim, words: CLAIMS,
           better: { field: "better_topic", label: "A better topic? (if you know one)",
                     none: "Leave it — just say No", from: "The site’s own list of topics." } };
}

export function tagCard(bill, tag) {
  return { type: "claim", head: `${bill} · 2025-2026`, title: "relative to care.", what: "tag",
           label: "The drafters’ analysis", body: "This bill does a thing.", q: "Is this bill about {claim}?",
           claim: tag, def: "Bills about it.", words: TAGS };
}

// A pack: three queues; two groups of timings, one of topics, one of tags;
// and calibration items the owner judged.
export async function loadPack(d1, { timings = 6, topics = 4, tags = 3, calib = 3 } = {}) {
  const run = (sql, ...a) => d1.sql.prepare(sql).run(...a);
  run("INSERT INTO queues (queue, label, pool, judged, as_of, options, ord) VALUES (?, ?, ?, ?, ?, ?, ?)",
      "timing", "Hearing times", 12545, 34, T0, null, 0);
  run("INSERT INTO queues (queue, label, pool, judged, as_of, options, ord) VALUES (?, ?, ?, ?, ?, ?, ?)",
      "topic", "Topics", 31449, 44, T0, JSON.stringify(TOPICS), 1);
  run("INSERT INTO queues (queue, label, pool, judged, as_of, options, ord) VALUES (?, ?, ?, ?, ?, ?, ?)",
      "tag", "Tags", 1994, 18, T0, null, 2);
  for (const [grp, queue, label, ord] of [["timing|2026", "timing", "2026 recordings", 0],
                                          ["timing|2025", "timing", "2025 recordings", 1],
                                          ["topic|2023-2024", "topic", "Bills of 2023-2024", 0],
                                          ["tag|medicaid", "tag", "Medicaid and public assistance", 0]])
    run("INSERT INTO groups (grp, queue, label, ord) VALUES (?, ?, ?, ?)", grp, queue, label, ord);
  const add = (kind, key, queue, grp, ord, card, shown) =>
    run("INSERT INTO items (kind, key, queue, pack, grp, ord, card, shown) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        kind, key, queue, "2026-11-19", grp, ord, JSON.stringify(card), JSON.stringify(shown));
  for (let i = 0; i < timings; i++) {
    const grp = i < timings / 2 ? "timing|2026" : "timing|2025";
    add(i < timings / 2 ? "timestamp" : "timestamp", `VID${i}|HB${100 + i}|public hearing`, "timing", grp,
        i, momentCard(`HB ${100 + i}`, 600 + i, i % 2 ? null : 900 + i),
        { video_id: `VID${i}`, bill: `HB${100 + i}`, proceeding: "public hearing", start: 600 + i });
  }
  for (let i = 0; i < topics; i++)
    add("topic", `topic|2023-2024|HB${200 + i}`, "topic", "topic|2023-2024", i,
        topicCard(`HB ${200 + i}`, "Education - General"), { bill: `HB${200 + i}`, topic: "Education - General" });
  for (let i = 0; i < tags; i++)
    add("tag", `tag|medicaid|title|2025-2026/SB${300 + i}`, "tag", "tag|medicaid", i,
        tagCard(`SB ${300 + i}`, "Medicaid and public assistance"), { bill: `SB${300 + i}`, hard: false });
  for (let i = 0; i < calib; i++)
    run("INSERT INTO calib (kind, key, queue, card, hers, ord) VALUES (?, ?, ?, ?, ?, ?)",
        "topic", `topic|2021-2022|HB${900 + i}`, "topic", JSON.stringify(topicCard(`HB ${900 + i}`, "Police")),
        i % 2 ? "no" : "yes", i);
}

// A link straight into the table, as bench_pull.py --owner-link writes the
// owner's: { id, token, ...row }.
export async function addLink(d1, { id, name = "Sam", role = "contributor", queues = ["timing", "topic", "tag"],
                                    state = "active", cap = 500 } = {}) {
  const token = newToken();
  d1.sql.prepare("INSERT INTO links (id, name, token_hash, role, queues, state, made_on, daily_cap) " +
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
    .run(id, name, await hashToken(token), role, JSON.stringify(queues), state, "2026-11-19",
         role === "owner" ? null : cap);
  return { id, token, name, role, queues, state, daily_cap: role === "owner" ? null : cap };
}

export function makeBench() {
  return new FakeD1(SCHEMA);
}

// THE OWNER'S LIST, as a pack loads it (bench_pack.py --asks): a card is the entry as the
// page draws it, with its section's label.
export function askCard({ section = "In the update waiting for your word", title = "Navigation in two rows",
                          what = "Each section's pages now sit in a second row.\n\nOn a phone the row scrolls.",
                          where = [{ label: "The home page on the preview", url: "https://dry-run.graniterecord.pages.dev/" }],
                          question = "Does the new navigation read right on a computer and on a phone?",
                          answers = { yes: "Looks right", no: "Needs changes", unsure: "Let’s discuss" },
                          recommended = "yes", added = "2026-11-23" } = {}) {
  return { section, title, what, where, question, answers, recommended, added };
}

// Entries straight into the table: [{ key, section, ord, card, state }].
export function loadAsks(d1, entries) {
  entries.forEach((e, i) => d1.sql.prepare(
    "INSERT INTO asks (key, section, ord, card, pack, state, added_on) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .run(e.key, e.section || "release", e.ord ?? i, JSON.stringify(e.card || askCard()), "2026-11-23-asks",
         e.state || "open", "2026-11-23"));
}

// A bench whose database was made before the asks tables were: the schema without them, as
// the preview's and production's databases stood until a pack brought the list.
export function benchBeforeAsks() {
  const text = readFileSync(SCHEMA, "utf8");
  const cut = text.indexOf("-- THE OWNER'S LIST");
  if (cut < 0) throw new Error("schema.sql no longer marks where the owner's list begins");
  const dir = mkdtempSync(join(tmpdir(), "gr-bench-"));
  const path = join(dir, "schema-before-asks.sql");
  writeFileSync(path, text.slice(0, cut));
  try {
    return new FakeD1(path);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

export const at = (s, base = T0) => new Date(new Date(base).getTime() + s * 1000);
