// The owner's roster choice (29 Oct 2026), a blend of mock-ups A and B, on the
// preview's real rows, beside A as it was mocked. Rows rewritten as
// build_pages.seat_row_tag writes them; app.css from <worktree> plus, in
// "blend" mode with no CSS argument, blend.css.
//   NODE_USE_ENV_PROXY=1 NODE_PATH=$(npm root -g) node roster_blend.cjs <worktree> <outdir> [modes] [extra.css|-]
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT, OUT, MODES = 'A,blend', EXTRA] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const baseCss = fs.readFileSync(WT + '/src/pages/app.css', 'utf8');
const blendCss = EXTRA === '-' ? '' : fs.readFileSync(EXTRA || (__dirname + '/blend.css'), 'utf8');
const SR = `position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0`;
const CSS = {
  A: `
:where(body.pg) #seatlist .sr{${SR}}
:where(body.pg) .seatrow .sseat{flex:0 0 1.9em;font-size:.78em;color:var(--ink-2);opacity:.85}
@media (min-width:73.75em){ :where(body.pg) .seatdivs .seatrow .sseat{flex:0 0 1.9em} }`,
  blend: blendCss,
  built: '',
  real: '',
};
const REAL = __dirname + '/officials_real.html';
function rows(html, mode) {
  if (mode === 'built' || mode === 'real') return html;
  const s0 = html.indexOf('id="seatlist"'), s1 = html.indexOf('<ol class="seatlist senate">', s0);
  if (s0 < 0 || s1 < 0) throw new Error('no #seatlist block');
  let mid = html.slice(s0, s1)
    .replace(/(<span class="mchip[^"]*"[^>]*>(?:<a [^>]*>)?)(Rep\.) /g, '$1<span class="mhon">$2 </span>')
    .replace(/ (<span class="mtag">)/g, '&#160;$1')
    .replace(/(<span class="mtag">)\(([^()\s<]+)( - [^()<]+)\)(<\/span>)/g, '$1($2<span class="mdist">$3</span>)$4');
  if (mode === 'A') mid = mid.replace(/<span class="sseat">(\d+)-(\d+)<\/span>/g, '<span class="sseat"><span class="sr">$1-</span>$2</span>');
  if (mode === 'blend') mid = mid.replace(/(<li class="seatrow"[^>]*><span class="sseat">(\d+)-(\d+)<\/span>[\s\S]*?)<\/span><\/li>/g,
    (all, head, d, n) => d === '6' ? all : `${head}<span class="mseat" aria-hidden="true">${n}</span></span></li>`);
  return html.slice(0, s0) + mid + html.slice(s1);
}
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const report = [];
  for (const mode of MODES.split(',')) for (const width of (process.env.WIDTHS ? process.env.WIDTHS.split(',').map(Number) : [1280, 390])) for (const scheme of (process.env.SCHEMES ? process.env.SCHEMES.split(',') : ['light', 'dark'])) {
    if (mode === 'A' && scheme === 'dark') continue;
    const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: scheme });
    await ctx.route('**/*', async route => {
      const u = route.request().url();
      if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
      const url = new URL(u);
      if (url.pathname === '/app.css') return route.fulfill({ status: 200, headers: { 'content-type': 'text/css; charset=utf-8' }, body: baseCss + CSS[mode] });
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400) return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      let body = Buffer.from(await r.arrayBuffer());
      if (/^\/officials(\.html)?$/.test(url.pathname)) body = mode === 'real' ? fs.readFileSync(REAL) : Buffer.from(rows(body.toString('utf8'), mode));
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
      const nums = [...list.querySelectorAll('.mseat')];
      let collide = [], notFirst = [], outside = [];
      for (const n of nums) {
        const chip = n.closest('.mchip'), a = chip.querySelector('a');
        const nr = n.getBoundingClientRect(), cr = chip.getBoundingClientRect();
        // The name's drawn text alone: its text nodes, less any inside a part
        // clipped for a screen reader (.mhon, .mdist).
        const lines = [];
        const tw = document.createTreeWalker(a, NodeFilter.SHOW_TEXT);
        for (let t; (t = tw.nextNode());) {
          let e = t.parentElement, hid = false;
          for (; e && e !== a; e = e.parentElement) if (getComputedStyle(e).clip.startsWith('rect(0')) hid = true;
          if (hid || !t.textContent.trim()) continue;
          const rg = document.createRange(); rg.selectNodeContents(t);
          lines.push(...[...rg.getClientRects()].filter(r => r.width > 0));
        }
        const who = a.textContent.replace(/\s+/g, ' ').trim();
        if (lines.some(r => r.right > nr.left - 2 && r.bottom > nr.top && r.top < nr.bottom)) collide.push(who);
        const first = lines.reduce((m, r) => Math.min(m, r.top), Infinity);
        if (Math.abs(nr.top - first) > lh * 0.6) notFirst.push(who);
        if (nr.right > cr.right + .5 || nr.left < cr.left) outside.push(who);
      }
      const rost = list.querySelector('.srost .mchip'), div1 = list.querySelector('.seatdivs .sdiv .mchip');
      const sseat = list.querySelector('.seatdivs .seatrow > .sseat');
      const cs = sseat && getComputedStyle(sseat);
      const name = links[1] ? (links[1].textContent || '').replace(/\s+/g, ' ').trim() : '';
      const rowText = list.querySelector('.seatdivs .seatrow').textContent.replace(/\s+/g, ' ').trim();
      list.scrollIntoView();
      return { rows: links.length, wrapped, numbers: nums.length, hidden: nums.filter(n => n.getAttribute('aria-hidden') === 'true').length,
               collide: collide.length, collideSample: collide.slice(0, 4), notFirstLine: notFirst.length, notFirstSample: notFirst.slice(0, 4),
               outsideCard: outside.length, rostrumW: rost && Math.round(rost.getBoundingClientRect().width),
               rostrumNumber: !!(rost && rost.querySelector('.mseat')), div1W: div1 && Math.round(div1.getBoundingClientRect().width),
               sseatClipped: cs ? (cs.position === 'absolute' && cs.clip.startsWith('rect(0') ? 'clipped' : `${cs.position} ${cs.clip}`) : 'none',
               height: Math.round(list.getBoundingClientRect().height), accessibleName: name, rowText };
    });
    const full = `${OUT}/roster-${mode}-${width}-${scheme}.png`;
    const top = `${OUT}/roster-${mode}-${width}-${scheme}-top.png`;
    const el = await p.$('#seatlist');
    await el.screenshot({ path: full });
    const box = await p.evaluate(() => { const r = document.getElementById('seatlist').getBoundingClientRect();
      return { x: r.left + scrollX, y: r.top + scrollY, width: r.width, height: r.height }; });
    await p.screenshot({ path: top, fullPage: true, clip: { x: Math.max(0, box.x - 8), y: box.y - 8, width: Math.min(width - Math.max(0, box.x - 8), box.width + 16), height: Math.min(620, box.height + 16) } });
    report.push({ mode, width, scheme, ...info, shot: full, top });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(report, null, 1));
})();
