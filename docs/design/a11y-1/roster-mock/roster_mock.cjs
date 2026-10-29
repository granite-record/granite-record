// Mock-ups of the House roster under the seating chart, on the preview's real
// rows, for the owner's question (29 Oct 2026). Nothing here is committed.
//   now: fix/a11y-1 as it stands (no "Rep." to the eye, the letter held to the surname)
//   A:   the seat number without its division ("001"), smaller and muted, in the gutter
//   B:   no gutter; the seat number inside the card, right-aligned, small and muted; "Rep." shown
// The accessible name of each member's link is the same in all three; the
// division prefix stays for a screen reader (clipped, not removed).
//   NODE_USE_ENV_PROXY=1 NODE_PATH=$(npm root -g) node roster_mock.cjs <worktree> <outdir>
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT, OUT] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const baseCss = fs.readFileSync(WT + '/src/pages/app.css', 'utf8');
const SR = `position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0`;
const CSS = {
  now: '',
  A: `
:where(body.pg) #seatlist .sr{${SR}}
:where(body.pg) .seatrow .sseat{flex:0 0 1.9em;font-size:.78em;color:var(--ink-2);opacity:.85}
@media (min-width:73.75em){ :where(body.pg) .seatdivs .seatrow .sseat{flex:0 0 1.9em} }`,
  B: `
:where(body.pg) #seatlist .sr{${SR}}
:where(body.pg) #seatlist .seatrow > .sseat{display:none}
:where(body.pg) #seatlist .seatrow .mchip{display:flex;align-items:baseline;width:100%;box-sizing:border-box}
:where(body.pg) #seatlist .seatrow .mchip .mseat{margin-left:auto;padding-left:.6em;font-size:.78em;
  color:var(--ink-2);font-variant-numeric:tabular-nums;white-space:nowrap}`,
};
function rows(html, mode) {
  const s0 = html.indexOf('id="seatlist"'), s1 = html.indexOf('<ol class="seatlist senate">', s0);
  if (s0 < 0 || s1 < 0) throw new Error('no #seatlist block');
  let mid = html.slice(s0, s1);
  if (mode !== 'B') mid = mid.replace(/(<span class="mchip[^"]*"[^>]*>(?:<a [^>]*>)?)(Rep\.) /g, '$1<span class="mhon">$2 </span>');
  mid = mid.replace(/ (<span class="mtag">)/g, '&#160;$1')
    .replace(/(<span class="mtag">)\(([^()\s<]+)( - [^()<]+)\)(<\/span>)/g, '$1($2<span class="mdist">$3</span>)$4');
  if (mode === 'A') mid = mid.replace(/<span class="sseat">(\d+)-(\d+)<\/span>/g, '<span class="sseat"><span class="sr">$1-</span>$2</span>');
  if (mode === 'B') mid = mid.replace(/<span class="sseat">(\d+)-(\d+)<\/span>(<span class="mchip[^"]*"[^>]*>[\s\S]*?<\/a>)(<\/span>)/g,
    '<span class="sseat"><span class="sr">$1-</span>$2</span>$3<span class="mseat" aria-hidden="true">$2</span>$4');
  return html.slice(0, s0) + mid + html.slice(s1);
}
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const report = [];
  for (const mode of ['now', 'A', 'B']) for (const width of [1280, 390]) {
    const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: 'light' });
    await ctx.route('**/*', async route => {
      const u = route.request().url();
      if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
      const url = new URL(u);
      if (url.pathname === '/app.css') return route.fulfill({ status: 200, headers: { 'content-type': 'text/css; charset=utf-8' }, body: baseCss + CSS[mode] });
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400) return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      let body = Buffer.from(await r.arrayBuffer());
      if (/^\/officials(\.html)?$/.test(url.pathname)) body = Buffer.from(rows(body.toString('utf8'), mode));
      return route.fulfill({ status: r.status, headers: { 'content-type': r.headers.get('content-type') || '' }, body });
    });
    const p = await ctx.newPage();
    await p.goto(B + '/officials', { waitUntil: 'load', timeout: 90000 });
    await p.waitForTimeout(1200);
    await p.evaluate(() => { const t = document.getElementById('tab-legislators'); if (t) t.click(); });
    await p.click('#tab-seat'); await p.waitForTimeout(800);
    const info = await p.evaluate(() => {
      const list = document.getElementById('seatlist');
      const links = [...list.querySelectorAll('.seatrow .mchip a')];
      const lh = parseFloat(getComputedStyle(links[0]).lineHeight) || 20;
      const wrapped = links.filter(a => a.getBoundingClientRect().height > lh * 1.5).length;
      const name = links[1] ? (links[1].textContent || '').replace(/\s+/g, ' ').trim() : '';
      list.scrollIntoView();
      return { rows: links.length, wrapped, height: Math.round(list.getBoundingClientRect().height), accessibleName: name };
    });
    const full = `${OUT}/roster-${mode}-${width}-light.png`;
    const el = await p.$('#seatlist');
    await el.screenshot({ path: full });
    report.push({ mode, width, ...info, shot: full });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(report, null, 1));
})();
