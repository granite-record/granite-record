// workers/bench/page.js: the page as the design draws it, read as source.
// What a browser does with it was looked at in one (phone and desktop widths,
// light and dark, the answers, the two-step timing, swipes, undo and the
// toast); these hold what that look found, so a change that undoes it fails.

import test from "node:test";
import assert from "node:assert/strict";
import { SCRIPT, benchPage } from "../../workers/bench/page.js";

const page = async () => (await benchPage().text());

test("the page's script is one function that parses, and nothing in the page chooses an answer", async () => {
  assert.doesNotThrow(() => new Function(SCRIPT), "the script parses");
  const html = await page();
  const markup = html.slice(0, html.indexOf("<script nonce"));
  assert.doesNotMatch(markup, /\b(checked|selected)\b/, "no answer checked or selected in the markup");
  assert.match(markup, /<footer class="answers" id="answers"><\/footer>/, "the answers are drawn by the script, empty first");
  // An answer is sent from answer() alone, which only a press, a key or a swipe calls.
  const sends = [...SCRIPT.matchAll(/\bsend\(/g)].length;
  const inAnswer = SCRIPT.slice(SCRIPT.indexOf("function answer(what)"), SCRIPT.indexOf("function openNote")).match(/\bsend\(/g).length;
  assert.equal(sends, inAnswer + 1, "send() is called from answer() and defined once, nowhere else");
  // ... and answer() from a press, a key or a swipe alone: its definition, the click
  // handler's one, the keys' five (Escape in a field among them) and the swipe's one.
  const calls = [...SCRIPT.matchAll(/\banswer\(/g)].length;
  assert.equal(calls, 8, `answer( is written ${calls} times: a call from somewhere new answers without a person`);
  assert.match(SCRIPT, /\nstart\(\);\}\)\(\);$/, "the script ends by asking the bench, and nothing after");
});

test("the token leaves the address before anything else runs, so YouTube's player is never told it", () => {
  // The player API sends the page's whole address to YouTube (its forigin): seen on
  // 17 November 2026 carrying the token after "#".
  const strip = SCRIPT.indexOf('history.replaceState(null,"",location.pathname+location.search)');
  assert.ok(strip > 0, "the address keeps the token");
  for (const later of ["function api(", "function ytLoad(", "YT.Player(", "\nstart();"])
    assert.ok(SCRIPT.indexOf(later) > strip, `${later} comes before the token leaves the address`);
  assert.match(SCRIPT, /sessionStorage\.setItem\("bench",T\);else T=sessionStorage\.getItem\("bench"\)/,
               "the token is kept for the tab alone, so a reload still works");
  assert.doesNotMatch(SCRIPT, /localStorage|document\.cookie/, "kept nowhere longer than the tab");
});

test("the keys: left No, down Not sure, right Yes, Z undo, N note, Space play, J and L ten seconds", () => {
  const keys = SCRIPT.slice(SCRIPT.indexOf('document.addEventListener("keydown"'));
  assert.match(keys, /k==="ArrowRight"\)answer\(S\.mode==="mark"\?"mark":S\.mode==="better"\?"saveno":"yes"\)/);
  assert.match(keys, /k==="ArrowLeft"\)answer\(S\.mode==="mark"\?"lost":S\.mode==="better"\?"back":"no"\)/);
  assert.match(keys, /k==="ArrowDown"&&S\.mode==="ask"\)answer\("unsure"\)/);
  assert.match(keys, /k==="z"\|\|k==="Z"\)undo\(\)/);
  assert.match(keys, /k==="n"\|\|k==="N"/);
  assert.match(keys, /st&&k===" "\)play\(st\.at\)/);
  assert.match(keys, /nudge\(-10\)/);
  assert.match(keys, /e\.target\.matches\("input,select,textarea"\)/, "typing a note answers nothing");
});

test("a swipe answers only across the card, far enough and more across than down, never on the player", () => {
  assert.match(SCRIPT, /SWIPE=80/);
  assert.match(SCRIPT, /Math\.abs\(dx\)>SWIPE&&Math\.abs\(dx\)>2\*Math\.abs\(dy\)\)answer\(dx>0\?"yes":"no"\)/);
  assert.match(SCRIPT, /closest\("#player,input,select,button"\)\)+\{sx=null;return;\}/);
  assert.match(SCRIPT, /\$\("card"\)\.addEventListener\("touchstart"/, "on the card alone");
});

test("undo for six seconds; holds renewed every two minutes; the recording cued, never played unasked", () => {
  assert.match(SCRIPT, /TOAST_MS=6000/);
  assert.match(SCRIPT, /toast\("Saved: "\+SAID\[side\],true\)/);
  assert.match(SCRIPT, /HOLD_EVERY=120000/);
  assert.match(SCRIPT, /api\("\/api\/bench\/hold",\{\}\)/);
  assert.match(SCRIPT, /LEAD=8/);
  assert.match(SCRIPT, /cueVideoById\(\{videoId:id,startSeconds:start\}\)/);
  assert.doesNotMatch(SCRIPT, /autoplay|loadVideoById/, "nothing plays until asked");
  assert.match(SCRIPT, /host:"https:\/\/www\.youtube-nocookie\.com"/, "the bill pages' player");
});

test("progress without rewards: a bar for the group and this sitting, how far along, and no score anywhere", async () => {
  const html = await page();
  for (const id of ['id="pdone"', 'id="pmine"', 'id="pgroup"', 'id="pyou"', 'id="farlist"'])
    assert.ok(html.includes(id), id);
  assert.match(SCRIPT, /"you "\+you/);
  const words = html.replace(/<script[\s\S]*?<\/script>/, "") + SCRIPT;
  assert.doesNotMatch(words, /\b(score|streak|points?|badge|level up|well done|great job|congratulations|round complete)\b/i,
                      "no score, no streak, no screen between groups");
  assert.match(html, /nothing else about you is\. Answers and notes become part of Granite Record’s open data, with no name on them\./);
  assert.match(html, /@media \(prefers-color-scheme:dark\)\{:root\{--paper:#171B1C;/, "dark, in the site's palette");
  assert.match(html, /--paper:#E9EAEC;/, "light, in the site's palette");
  assert.match(html, /<meta name="robots" content="noindex">/);
  assert.doesNotMatch(html, /New Hampshire|\bN\.?H\.?\b/, "the page names no state: a card carries its own words");
});

test("every value from the bench reaches the page through esc()", () => {
  // The fields a card or a link carries, joined into markup only inside esc(): never
  // beside a "+" of their own. A confirm() is text the browser shows, not markup.
  const src = SCRIPT.replace(/confirm\(.*?\)\)return;/g, "");
  // Where an expression around the field is joined with "+": the field itself, or the
  // parenthesis that holds it when that parenthesis is not esc()'s.
  const opening = (s, close) => {
    for (let i = close - 1, depth = 0; i >= 0; i--) {
      if (s[i] === ")") depth++;
      else if (s[i] === "(") { if (!depth) return i; depth--; }
    }
    return -1;
  };
  const joined = (s, at, len) => {
    let i = at + len;
    while (s[i] === " ") i++;
    if (s[i] === "+" || /\+\s*$/.test(s.slice(Math.max(0, at - 3), at))) return true;
    while (s[i] === ")") {
      const o = opening(s, i);
      if (o < 0 || s.slice(Math.max(0, o - 3), o) === "esc") return false;
      i++;
      while (s[i] === " ") i++;
      if (s[i] === "+") return true;
    }
    return false;
  };
  for (const f of ["c.head", "c.meta", "c.title", "c.body", "c.label", "c.claim", "c.def", "c.q", "st.label", "st.q",
                   "st.find", "st.mark", "st.lost", "l.name", "l.id", "a.head", "a.what", "a.note", "a.side", "q.label",
                   "f.better_topic", "p.label"]) {
    for (const m of src.matchAll(new RegExp(`\\b${f.replace(".", "\\.")}\\b(?!\\s*[?=!&|])`, "g")))
      assert.ok(!joined(src, m.index, f.length), `${f} is joined into the page unescaped: ` +
                JSON.stringify(src.slice(m.index - 40, m.index + 30)));
  }
  assert.match(SCRIPT, /esc\(c\.head\)/);
  assert.match(SCRIPT, /esc\(a\.note\)/);
});
