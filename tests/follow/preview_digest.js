/*
 * A digest, rendered and not sent: what a reader following these records
 * would be emailed, from a site's real changes files, through the sender's
 * own collect() and digestEmail() -- so the preview cannot drift from what is
 * sent. Nothing here touches the database, Resend or an address.
 * It lives here, not in workers/follow/, because it prints to the console
 * and privacy.test.js holds that nothing in the Worker does.
 *
 *   node tests/follow/preview_digest.js                      the preview site, a sample of follows
 *   node tests/follow/preview_digest.js --follow bill:2026/HB1442 member:1234 committee:H-ED
 *   node tests/follow/preview_digest.js --weekly --nights 7 --out preview-mail
 *   node tests/follow/preview_digest.js --site https://graniterecord.org
 *   node tests/follow/preview_digest.js --dir site           a built site on this disk
 *
 * With no --follow, it takes the records with the most news in the nights
 * read -- three bills, a legislator, a committee, a law and a topic, where
 * there is one -- so the preview always has something in it.
 *
 * Writes <out>/digest-<frequency>.html (the email's HTML under a strip giving
 * its subject and follows, as a mail client would show it), .txt (the plain
 * part) and .json (the subject and the sections, for a test to read). The
 * manage and unsubscribe links point nowhere: they are a reader's own and a
 * preview has no reader.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { readCurrent, readNight } from "../../workers/follow/changes.js";
import { addDays, keyOf, parseKey } from "../../workers/follow/common.js";
import { digestEmail } from "../../workers/follow/mail.js";
import { collect } from "../../workers/follow/sender.js";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(name);
  return i < 0 ? dflt : args[i + 1];
};
const list = name => {
  const i = args.indexOf(name);
  if (i < 0) return [];
  const out = [];
  for (let j = i + 1; j < args.length && !args[j].startsWith("--"); j++) out.push(args[j]);
  return out;
};
const site = opt("--site", "https://dry-run.graniterecord.pages.dev").replace(/\/$/, "");
const dir = opt("--dir", "");
const frequency = args.includes("--weekly") ? "weekly" : "daily";
const nightsRead = Number(opt("--nights", frequency === "weekly" ? "7" : "1"));
const out = opt("--out", "preview-mail");
const detail = args.includes("--milestones") ? "milestones" : "all";

// The sender's own fetch, or the same answers from a folder.
const get = dir
  ? async path => {
      try {
        return new Response(readFileSync(join(dir, path.split("?")[0])), { status: 200 });
      } catch { return new Response("", { status: 404 }); }
    }
  : path => fetch(`${site}${path}`, { headers: { Accept: "application/json" } });

const cur = await readCurrent(get);
if (!cur.value) {
  console.error(`preview: no readable /changes/current.json at ${dir || site}`);
  process.exit(1);
}
const today = cur.value.date;
const nights = [];
for (let d = addDays(today, -(nightsRead - 1)); d <= today; d = addDays(d, 1)) {
  const r = await readNight(get, d);
  if (r.value) nights.push(r.value);
  else console.error(`preview: no night file for ${d}`);
}
if (!nights.length) {
  console.error("preview: no night read, so nothing to show");
  process.exit(1);
}

// The busiest records of each kind, where --follow names none.
function sample() {
  const count = new Map();
  for (const n of nights)
    for (const [k, r] of n.refs) count.set(k, (count.get(k) || 0) + r.items.length);
  const busiest = (kind, n) => [...count].filter(([k]) => k.startsWith(kind + ":"))
    .sort((a, b) => b[1] - a[1]).slice(0, n).map(([k]) => k);
  return [...busiest("bill", 3), ...busiest("member", 1), ...busiest("committee", 1),
          ...busiest("law", 1), ...busiest("topic", 1)];
}
const keys = list("--follow").length ? list("--follow") : sample();
const follows = [];
for (const k of keys) {
  const p = parseKey(k);
  if (p) follows.push({ ...p, fh: "preview" });
  else console.error(`preview: ${k} is not a record key (kind:ref, as in current.json)`);
}
follows.sort((a, b) => keyOf(a.kind, a.ref).localeCompare(keyOf(b.kind, b.ref)));

const sections = collect({ follows, nights, cursor: {}, current: cur.value, frequency,
  today, detail });
const origin = dir ? "https://graniterecord.org" : site;
const mail = digestEmail({ origin, frequency, date: today, sections,
  manage: "#preview-manage", unsub: "#preview-unsubscribe",
  feedbackUrl: "https://forms.gle/PYw9c3xgpDDwvX7E9" });

mkdirSync(out, { recursive: true });
const base = join(out, `digest-${frequency}`);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const strip = `<div style="font:13px/1.5 system-ui,sans-serif;background:#eef0f2;border-bottom:1px solid #d3d6da;padding:10px 16px">
<b>Preview, not sent.</b> ${esc(frequency)} digest of ${esc(today)} from ${esc(dir || site)}, ${nights.length} night${nights.length === 1 ? "" : "s"} read<br>
<b>Subject:</b> ${esc(mail.subject)}<br>
<b>Following:</b> ${esc(follows.map(f => keyOf(f.kind, f.ref)).join(", ") || "nothing")}</div>`;
writeFileSync(`${base}.html`, mail.html.replace(/<body([^>]*)>/i, m => m + strip));
writeFileSync(`${base}.txt`, `Subject: ${mail.subject}\n\n${mail.text}`);
writeFileSync(`${base}.json`, JSON.stringify({ subject: mail.subject, follows: keys, sections }, null, 1));
console.log(`preview: ${sections.length} of ${follows.length} follows have news; ` +
  `"${mail.subject}"\n  ${base}.html\n  ${base}.txt`);
