// Every value written into HTML is escaped -- from a reader, the database or
// the changes file alike -- and no page can be framed, run another's script,
// or point a link off the site.

import test from "node:test";
import assert from "node:assert/strict";
import { esc, siteUrl, oneLine } from "../../workers/follow/common.js";
import { confirmationEmail, digestEmail } from "../../workers/follow/mail.js";
import { run } from "../../workers/follow/sender.js";
import { get, lastMailTo, makeWorld } from "./fakes.js";
import { handlers, join, view } from "./flows.js";

const HOSTILE_LABEL = `<img src=x onerror=alert(1)>`;
const HOSTILE_TITLE = `"><script>alert(1)</script>`;
const HOSTILE_SUMMARY = `</li><script>alert('x')</script><a href="javascript:alert(1)">`;

// No markup made from these strings survives: only their escaped forms.
function clean(html) {
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /href="javascript:/i);
  assert.doesNotMatch(html, /<[^>]*\son[a-z]+=/i, "no inline handler in any tag");
}

test("esc() escapes the five characters that matter, and nothing is left raw", () => {
  assert.equal(esc(`<a href="x" title='y'>&</a>`),
    "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;");
  assert.equal(esc(null), "");
  assert.equal(esc(42), "42");
});

test("a link goes to the site or to its front page, never anywhere else", () => {
  const o = "https://graniterecord.org";
  assert.equal(siteUrl(o, "/bill/2026/hb9901"), `${o}/bill/2026/hb9901`);
  assert.equal(siteUrl(o, "/bills?topic=Banking%20and%20Finance"), `${o}/bills?topic=Banking%20and%20Finance`);
  for (const bad of ["javascript:alert(1)", "//evil.example.com/x", "https://evil.example.com",
                     "/x\"onmouseover=\"y", "/x y", "", null])
    assert.equal(siteUrl(o, bad), `${o}/`, String(bad));
  assert.equal(oneLine("a\r\nBcc: b\u0000c"), "a Bcc: b c");
});

test("the manage page escapes what the changes file calls a record", async () => {
  const w = makeWorld();
  try {
    const cur = w.net.site.get("/changes/current.json");
    cur.followable["bill:2026/HB9901"] = { label: HOSTILE_LABEL, title: HOSTILE_TITLE,
                                           url: "javascript:alert(1)" };
    const s = await join(w, "reads.hostile");
    const r = await view(w, s.manage);
    clean(r.body);
    assert.match(r.body, /&lt;img src=x onerror=alert\(1\)&gt;/);
    assert.match(r.body, /&quot;&gt;&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  } finally { w.close(); }
});

test("the emails escape it too, and a subject is one line", () => {
  const c = confirmationEmail({ origin: "https://graniterecord.org", label: `${HOSTILE_LABEL}\r\nBcc: x`,
                                title: HOSTILE_TITLE, token: "T".repeat(43) });
  clean(c.html);
  assert.doesNotMatch(c.subject, /[\r\n]/);
  const d = digestEmail({ origin: "https://graniterecord.org", frequency: "weekly", date: "2026-10-10",
    manage: "M".repeat(43), unsub: "U".repeat(43), feedbackUrl: "javascript:alert(1)",
    sections: [{ key: "bill:2026/HB9901", kind: "bill", ref: "2026/HB9901", label: HOSTILE_LABEL,
      title: HOSTILE_TITLE, url: "javascript:alert(1)", more: 0, week: { votes: 1, exec: 0 },
      items: [{ date: "2026-10-08", kind: "vote", summary: HOSTILE_SUMMARY }],
      study: { recommends: false, summary: HOSTILE_SUMMARY },
      ended: { how: "law", summary: HOSTILE_SUMMARY },
      upcoming: [{ date: "2026-10-14", time: "10:00", what: HOSTILE_TITLE, committee: HOSTILE_LABEL, venue: "" }] }] });
  clean(d.html);
  assert.doesNotMatch(d.text, /feedback form: javascript/, "a feedback address that is not https is left out");
});

test("a hostile summary in a night reaches the reader's email escaped", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reads.night");
    w.net.site.set("/changes/2026-10-07.json", { format: 1, date: "2026-10-07",
      built: "2026-10-07T09:00:00Z", sitting_term: "2025-2026", new_by: "first-seen",
      refs: { "bill:2026/HB9901": { items: [{ guid: "h", date: "2026-10-06", kind: "action",
        summary: HOSTILE_SUMMARY, term: "2025-2026", seen: "2026-10-07T09:00:00Z" }] } } });
    w.at("2026-10-07T12:00:00Z");
    await run(w.env, w.now);
    const m = lastMailTo(w, s.address);
    assert.match(m.text, /alert\('x'\)/, "the text part carries it as text");
    clean(m.html);
  } finally { w.close(); }
});

test("every page refuses framing, other scripts and other forms' targets", async () => {
  const w = makeWorld();
  try {
    const s = await join(w, "reads.headers");
    const pages = [
      await w.call(handlers.confirm, get("/api/follow/confirm")),
      await w.call(handlers.manage, get("/api/follow/manage")),
      await w.call(handlers.unsubscribe, get("/api/follow/unsubscribe")),
      await view(w, s.manage),
      await view(w, "X".repeat(43)),
    ];
    for (const p of pages) {
      const csp = p.headers["content-security-policy"];
      assert.match(csp, /default-src 'none'/);
      assert.match(csp, /frame-ancestors 'none'/);
      assert.match(csp, /form-action 'self'/);
      assert.match(csp, /script-src ('none'|'nonce-[A-Za-z0-9_-]{22}')/);
      assert.equal(p.headers["x-frame-options"], "DENY");
      assert.equal(p.headers["referrer-policy"], "no-referrer");
      clean(p.body);
      const scripts = p.body.match(/<script[^>]*>/g) || [];
      for (const tag of scripts) assert.match(tag, /^<script nonce="[A-Za-z0-9_-]{22}">$/);
    }
  } finally { w.close(); }
});
