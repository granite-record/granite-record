/*
 * The pages a reader sees from following: confirm, manage, unsubscribe.
 * Served by the Functions as HTML, so no front-end file is involved.
 *
 * A private link carries its token after "#", which the browser keeps to
 * itself. Each page's first answer is therefore a shell with a few lines of
 * script that read the token from there and put it into the page's form,
 * which posts it in the body; the token is never in a request address. The
 * script then takes the "#" part out of the address bar (history.replaceState),
 * so a shared computer's history does not keep a working link. It runs under
 * a per-answer nonce, and no other script can.
 *
 * Every value written into a page goes through esc() (common.js).
 */

import { b64urlEncode } from "./address.js";
import { esc, htmlResponse } from "./common.js";

// THE SITE'S OWN LOOK (the person's manage-page redesign, 14 October 2026):
// the site's palette and spacing, its serif for headings and its sans for the
// rest -- by name, where the reader has them, since the page's policy loads no
// font from anywhere (common.js, default-src 'none'), and the system's own
// otherwise. Each part of the page is a card; a choice of two is a segmented
// switch; following is a switch beside each record; Save stays in reach.
const STYLE = `
:root{--paper:#E9EAEC;--surface:#FBFBFC;--wash:#DFE1E4;--ink:#1C2126;--ink-2:#4A5259;--rule:#D3D6DA;
--edge:#767E86;--pine:#14514C;--pine-soft:#DFEBEA;--on-pine:#fff;--brick:#9E2B25;--brick-soft:#FAE7E5;
--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--serif:"Source Serif 4",Georgia,"Times New Roman",serif}
@media (prefers-color-scheme: dark){:root{--paper:#171B1C;--surface:#21282A;--wash:#2C3436;--ink:#E6E9E8;
--ink-2:#A7B0B0;--rule:#3D4547;--edge:#7C8687;--pine:#7FB9B1;--pine-soft:#1B302E;--on-pine:#0F1414;
--brick:#F0938C;--brick-soft:#43211F}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--sans)}
main{max-width:720px;margin:0 auto;padding:20px 16px 72px}
.brand{font:600 20px/1 var(--serif);margin:4px 0 24px}
.brand a{color:var(--ink);text-decoration:none}
h1{font:600 30px/1.2 var(--serif);margin:0 0 6px}
.lede{color:var(--ink-2);margin:0 0 20px}
h2{font:600 20px/1.3 var(--serif);margin:0 0 4px}
h3{font:600 12px/1 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--ink-2);margin:22px 0 8px}
p{margin:0 0 12px}
a{color:var(--pine)}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:18px 20px;margin:0 0 16px}
.card > h2 + .quiet{margin-top:2px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 16px}
.pair .card{margin:0}
.note{padding:10px 14px;border-left:4px solid var(--pine);background:var(--pine-soft);border-radius:4px;margin:0 0 16px}
.quiet{color:var(--ink-2);font-size:14px}
fieldset{border:0;padding:0;margin:10px 0 0;min-width:0}
legend{padding:0}
label{display:flex;gap:10px;align-items:baseline;margin:0 0 8px}
label small{display:block;color:var(--ink-2);font-size:13.5px;line-height:1.4;margin-top:2px}
input[type=radio],input[type=checkbox]{accent-color:var(--pine)}
/* A CHOICE OF TWO, as a segmented switch: the radios stay radios. */
.seg{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid var(--edge);border-radius:8px;overflow:hidden}
.seg label{margin:0;padding:10px 12px;display:block;cursor:pointer;border-left:1px solid var(--rule)}
.seg label:first-child{border-left:0}
.seg input{position:absolute;opacity:0;width:1px;height:1px}
.seg label span{font-weight:600}
.seg label small{font-weight:400}
.seg label:has(input:checked){background:var(--pine-soft);box-shadow:inset 0 -3px 0 var(--pine)}
.seg label:has(input:checked) span{color:var(--pine)}
.seg label:has(input:focus-visible){outline:2px solid var(--pine);outline-offset:-2px}
.pauses label{padding:6px 0;margin:0}
/* WHAT YOU FOLLOW: one row a record, its switch at the end. */
ul.follows{list-style:none;padding:0;margin:0 0 10px;border-top:1px solid var(--rule)}
ul.follows li{border-bottom:1px solid var(--rule)}
ul.follows label{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:0;padding:12px 0;cursor:pointer}
ul.follows .what{min-width:0;overflow-wrap:anywhere;font-weight:600}
ul.follows .title{display:block;color:var(--ink-2);font-size:14px;font-weight:400}
input.sw{appearance:none;-webkit-appearance:none;flex:none;order:2;width:42px;height:24px;border-radius:999px;
background:var(--wash);border:1px solid var(--edge);position:relative;cursor:pointer;margin:0}
input.sw::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;
background:var(--surface);box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
input.sw:checked{background:var(--pine);border-color:var(--pine)}
input.sw:checked::after{transform:translateX(18px)}
ul.chips{list-style:none;padding:0;margin:6px 0 10px;display:flex;flex-wrap:wrap;gap:8px}
ul.chips label{border:1px solid var(--edge);border-radius:999px;padding:5px 12px;margin:0;align-items:center;
background:var(--surface);font-size:14.5px;cursor:pointer}
ul.chips label:has(input:checked){background:var(--pine-soft);border-color:var(--pine);color:var(--pine);font-weight:600}
ul.chips input{accent-color:var(--pine)}
.add{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:10px 0 4px}
.add label{margin:0;font-size:14px;font-weight:600;color:var(--ink-2)}
input[type=text],input:not([type]),input[type=date],select{font:inherit;font-size:16px;padding:8px 10px;min-height:42px;
border:1px solid var(--edge);border-radius:6px;background:var(--surface);color:var(--ink);max-width:100%;min-width:0}
.add select,.add input:not([type]){flex:1 1 220px}
button{font:inherit;font-size:15px;font-weight:600;padding:10px 18px;min-height:44px;border-radius:6px;cursor:pointer;
border:1px solid var(--pine);background:var(--pine);color:var(--on-pine)}
button.plain{background:var(--surface);color:var(--pine)}
button.danger{background:var(--surface);color:var(--brick);border-color:var(--brick)}
button:disabled{opacity:.5;cursor:default}
.save{position:sticky;bottom:0;z-index:2;display:flex;justify-content:flex-end;gap:12px;align-items:center;
background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:16px 0;
box-shadow:0 -2px 10px rgba(0,0,0,.08)}
.save .quiet{margin:0 auto 0 0}
.save button{white-space:nowrap}
.card.danger{border-color:var(--brick);background:linear-gradient(var(--brick-soft),var(--brick-soft)) top/100% 4px no-repeat,var(--surface)}
:focus-visible{outline:2px solid var(--pine);outline-offset:2px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:600px){.pair{grid-template-columns:1fr}.card{padding:16px}h1{font-size:26px}}
`;

export function nonce() {
  return b64urlEncode(crypto.getRandomValues(new Uint8Array(16)));
}

const NOSCRIPT = `<noscript><p class="note">This page needs JavaScript. Your private link
keeps its key after the &ldquo;#&rdquo; in its address, which your browser does not send
to any server, and a few lines of script on this page read it from there.</p></noscript>`;

const MISSING = `<p id="missing" class="note" hidden>This link is missing its private part.
Open the link from your most recent email from Granite Record, whole.</p>`;

// status, title (plain text), body (HTML already escaped by the caller), and
// fill: the name of the form field the token from "#" goes into, if any, and
// submit: the id of a form to post as soon as it is filled.
export function page(status, { title, body, fill = "", submit = "" }) {
  const n = fill ? nonce() : "";
  const script = fill ? `(function(){
var h=new URLSearchParams(location.hash.slice(1)),v=h.get(${JSON.stringify(fill)})||"";
if(location.hash){try{history.replaceState(null,"",location.pathname);}catch(e){}}
var fs=document.querySelectorAll('input[name=${JSON.stringify(fill)}]');
for(var i=0;i<fs.length;i++)fs[i].value=v;
if(!v||!/^[A-Za-z0-9_-]{43}$/.test(v)){document.getElementById("missing").hidden=false;
var b=document.querySelectorAll("form button");for(var j=0;j<b.length;j++)b[j].disabled=true;return;}
${submit ? `var f=document.getElementById(${JSON.stringify(submit)}),k=h.get("n")||"";
if(f.notice)f.notice.value=k;f.submit();` : ""}
})();` : "";
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${esc(title)} — Granite Record</title>
<style>${STYLE}</style></head>
<body><main>
<p class="brand"><a href="/">Granite Record</a></p>
${fill ? NOSCRIPT + MISSING : ""}
${body}
</main>${fill ? `<script nonce="${n}">${script}</script>` : ""}</body></html>`;
  return htmlResponse(status, html, n);
}

// A page that only says something: a link that has expired, an address
// deleted, a record that can no longer be followed.
export function message(status, title, ...paragraphs) {
  return page(status, { title,
    body: `<h1>${esc(title)}</h1>` + paragraphs.map(p => `<p>${esc(p)}</p>`).join("\n") });
}

// WHAT DELETING MEANS, said one way everywhere. The rows go from the database
// at once. Two copies do not, and the reader is told so rather than told
// "for good": D1 keeps point-in-time backups (Time Travel) that cannot be
// turned off and age out by themselves, and the mail service keeps a copy of
// each email it has sent for its own retention period. README.md has the
// figures to check on the day.
export const DELETES = "Deletes your address and everything you follow from our " +
  "database, at once, and nothing more is sent.";
export const AFTERWARDS = "Two copies age out on their own rather than at once: the " +
  "database's automatic backups, kept for at most 30 days, and the copy of each email " +
  "already sent that our mail service keeps for a limited time.";

export function deleted() {
  return message(200, "Your address has been deleted",
    "Your address and everything you followed have been deleted from our database, " +
    "and nothing more will be sent. To follow something again, use Follow on its page.",
    AFTERWARDS);
}
