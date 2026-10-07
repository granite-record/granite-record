/*
 * The pages a reader sees from following: confirm, manage, unsubscribe.
 * Served by the Functions as HTML, so no front-end file is involved.
 *
 * A private link carries its token after "#", which the browser keeps to
 * itself. Each page's first answer is therefore a shell with a few lines of
 * script that read the token from there and put it into the page's form,
 * which posts it in the body; the token is never in a request address. The
 * script runs under a per-answer nonce, and no other script can.
 *
 * Every value written into a page goes through esc() (common.js).
 */

import { b64urlEncode } from "./address.js";
import { esc, htmlResponse } from "./common.js";

const STYLE = `
:root{--bg:#fbfaf7;--fg:#1a1a1a;--quiet:#555;--rule:#e3e0d8;--accent:#1d4e89;--on-accent:#fff;
--note:#eef3f9;--danger:#8a1c1c;--card:#fff}
@media (prefers-color-scheme: dark){:root{--bg:#16181b;--fg:#e9e6df;--quiet:#a9a59c;
--rule:#34373c;--accent:#8db4e6;--on-accent:#101215;--note:#1e2833;--danger:#e39a9a;--card:#1d2024}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.55 "Source Serif 4",Georgia,"Times New Roman",serif}
main{max-width:640px;margin:0 auto;padding:32px 16px 64px}
.brand{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--quiet);margin:0 0 24px}
.brand a{color:inherit;text-decoration:none}
h1{font-size:28px;line-height:1.2;margin:0 0 16px}
h2{font-size:20px;line-height:1.3;margin:36px 0 8px}
p{margin:0 0 14px}
a{color:var(--accent)}
.note{padding:10px 14px;border-left:4px solid var(--accent);background:var(--note);margin:0 0 20px}
.quiet{color:var(--quiet);font-size:15px}
ul.follows{list-style:none;padding:0;margin:0 0 10px;border-top:1px solid var(--rule)}
ul.follows li{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;
gap:8px 16px;padding:10px 0;border-bottom:1px solid var(--rule)}
ul.follows .what{min-width:0;overflow-wrap:anywhere}
ul.follows .title{display:block;color:var(--quiet);font-size:14px}
form{margin:0 0 12px}
fieldset{border:0;padding:0;margin:0 0 12px}
label{display:flex;gap:10px;align-items:baseline;margin:0 0 8px}
button{font:inherit;font-size:15px;padding:8px 16px;border-radius:4px;cursor:pointer;
border:1px solid var(--accent);background:var(--accent);color:var(--on-accent)}
button.plain{background:var(--card);color:var(--accent)}
button.danger{background:var(--card);color:var(--danger);border-color:var(--danger)}
button:disabled{opacity:.5;cursor:default}
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
