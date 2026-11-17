/*
 * The bench's one page, /bench, served by functions/bench.js: no file in
 * site/, no link from any page, not in the sitemap, noindex. Its address is
 * /bench#<token>; the token never leaves the browser but in the body of the
 * page's own requests.
 *
 * (Step 3 of the shared bench: the page's shell. Step 4 draws the cards.)
 */

import { pageResponse } from "./common.js";

export function nonce() {
  let s = "";
  for (const x of crypto.getRandomValues(new Uint8Array(16))) s += String.fromCharCode(x);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function benchPage() {
  const n = nonce();
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Bench &mdash; Granite Record</title></head>
<body><main><p>Granite Record Bench</p>
<p id="need">This page needs the private link it was sent with, whole.</p></main>
<script nonce="${n}"></script></body></html>`;
  return pageResponse(200, html, n);
}
