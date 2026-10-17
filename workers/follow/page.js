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
/* IN FORCED COLOURS the wash and the rule under the chosen one are painted
   away and the radios are out of sight, so the two were the same (the review
   of 16 October 2026): the chosen one takes the system's selection colours,
   and its focus ring the selection's text colour, as the sign-up box's does
   (app.css .followfreq). */
@media (forced-colors:active){
.seg label:has(input:checked){forced-color-adjust:none;background:Highlight;color:HighlightText;box-shadow:none}
.seg label:has(input:checked) span,.seg label:has(input:checked) small{color:HighlightText}
.seg label:has(input:checked:focus-visible){outline-color:HighlightText;outline-offset:-4px}}
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
/* ADDING LEGISLATORS AND COMMITTEES (the person's test of 16 October 2026: not
   searchable, ordered by first name, one at a time). A closed details a kind,
   so the page stays short on a phone until it is wanted; inside it a box that
   narrows the list as the reader types, shown only where the script runs, and
   a list of boxes to tick, the House and the Senate apart, that scrolls within
   a height a phone shows whole -- every ticked one is added on Save. */
[hidden]{display:none!important}
details.pick{margin:10px 0 4px;border:1px solid var(--edge);border-radius:8px;background:var(--surface)}
details.pick > summary{cursor:pointer;padding:10px 14px;font-weight:600;color:var(--pine);min-height:44px;
display:flex;align-items:center;gap:10px;list-style:none}
/* The summary is a flex row, which takes away the browser's own triangle in
   Chromium and Firefox and not always in Safari; so each is put away, and one
   chevron of the page's own says it opens: pointing on while closed, down
   while open. Drawn in currentColor, so forced colours keep it. */
details.pick > summary::-webkit-details-marker{display:none}
details.pick > summary::marker{content:""}
details.pick > summary::before{content:"";flex:none;width:7px;height:7px;margin:0 2px 0 1px;
border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg)}
details.pick[open] > summary::before{transform:rotate(45deg)}
details.pick > summary .picked{font-weight:400;font-size:14px;color:var(--ink-2)}
details.pick[open] > summary{border-bottom:1px solid var(--rule)}
.pickfind{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:0;padding:10px 14px 4px}
.pickfind label{margin:0;font-size:14px;font-weight:600;color:var(--ink-2)}
.pickfind input{flex:1 1 200px}
input[type=search]{font:inherit;font-size:16px;padding:8px 10px;min-height:42px;border:1px solid var(--edge);
border-radius:6px;background:var(--surface);color:var(--ink);max-width:100%;min-width:0}
.picklist{max-height:min(22rem,60vh);overflow-y:auto;overscroll-behavior:contain;padding:0 14px 8px}
.picklist fieldset{margin:8px 0 0}
.picklist legend{font:600 12px/1 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--ink-2);
padding:8px 0 6px}
.picklist ul{list-style:none;margin:0;padding:0}
.picklist li{border-top:1px solid var(--rule)}
.picklist label{display:flex;align-items:center;gap:12px;margin:0;padding:9px 2px;min-height:44px;cursor:pointer;
overflow-wrap:anywhere}
.picklist input[type=checkbox]{flex:none;width:20px;height:20px;margin:0}
.picklist .tag{white-space:nowrap}
.picklist .none{margin:10px 0 2px}
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

// THE FIND BOX OF EACH LIST TO ADD FROM (manage.js picker). A few lines that
// narrow the list as the reader types: case and accents ignored, and every
// word typed found somewhere in a row's name -- "aldrich glen", "belk 6",
// "sd22". A ticked row stays in sight whatever is typed, so what is about to
// be added is never hidden, and the summary counts them while the list is
// closed. The box itself is hidden in the markup and shown here: without
// script the whole list shows, and no box is offered that does nothing.
// Enter in the box does nothing: it is the one form of the page, and a
// phone's Search or Go key would otherwise save it halfway through ticking
// (the review of 16 October 2026). Save is the page's own button.
// String.raw, so the page receives the backslashes as written, and the
// accents and curly quotes are written as escapes rather than as the
// characters, which an editor or a copy can silently turn into others.
export const PICK_SCRIPT = String.raw`(function(){
function fold(s){return String(s).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase()
.replace(/['\u2018\u2019\x60]/g,"").replace(/[^a-z0-9]+/g," ").trim();}
var picks=document.querySelectorAll("[data-pick]");
for(var i=0;i<picks.length;i++)(function(d){
var box=d.querySelector("[data-find]"),rows=d.querySelectorAll("li"),sets=d.querySelectorAll("fieldset"),
none=d.querySelector("[data-none]"),count=d.querySelector("[data-picked]"),names=[];
for(var j=0;j<rows.length;j++)names.push(fold(rows[j].textContent));
function show(){
var q=fold(box.value).split(" ").filter(Boolean),any=false,ticked=0;
for(var j=0;j<rows.length;j++){var on=rows[j].querySelector("input").checked,hit=on;
if(on)ticked++;
if(!hit){hit=true;for(var w=0;w<q.length;w++)if(names[j].indexOf(q[w])<0){hit=false;break;}}
rows[j].hidden=!hit;if(hit)any=true;}
for(var k=0;k<sets.length;k++)sets[k].hidden=!sets[k].querySelector("li:not([hidden])");
none.hidden=any;count.textContent=ticked?ticked+" ticked":"";}
box.parentNode.hidden=false;box.addEventListener("input",show);d.addEventListener("change",show);
box.addEventListener("keydown",function(e){if(e.key==="Enter"||e.keyCode===13)e.preventDefault();});show();
})(picks[i]);
})();`;

// status, title (plain text), body (HTML already escaped by the caller), and
// fill: the name of the form field the token from "#" goes into, if any, and
// submit: the id of a form to post as soon as it is filled; script: one more
// script of this file's own (PICK_SCRIPT), never a caller's text, run under
// the same per-answer nonce.
export function page(status, { title, body, fill = "", submit = "", script: more = "" }) {
  const n = fill || more ? nonce() : "";
  const script = (fill ? `(function(){
var h=new URLSearchParams(location.hash.slice(1)),v=h.get(${JSON.stringify(fill)})||"";
if(location.hash){try{history.replaceState(null,"",location.pathname);}catch(e){}}
var fs=document.querySelectorAll('input[name=${JSON.stringify(fill)}]');
for(var i=0;i<fs.length;i++)fs[i].value=v;
if(!v||!/^[A-Za-z0-9_-]{43}$/.test(v)){document.getElementById("missing").hidden=false;
var b=document.querySelectorAll("form button");for(var j=0;j<b.length;j++)b[j].disabled=true;return;}
${submit ? `var f=document.getElementById(${JSON.stringify(submit)}),k=h.get("n")||"";
if(f.notice)f.notice.value=k;f.submit();` : ""}
})();` : "") + more;
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
</main>${script ? `<script nonce="${n}">${script}</script>` : ""}</body></html>`;
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
