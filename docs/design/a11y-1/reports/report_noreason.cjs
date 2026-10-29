// HB 1547 of 2010's Reports tab on the dry-run preview with fix/a11y-1's app.js
// and app.css served in place of the preview's. Every other origin aborted.
//   NODE_USE_ENV_PROXY=1 NODE_PATH=$(npm root -g) node report_noreason.cjs <worktree> <outdir> [bill path...]
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT, OUT] = process.argv.slice(2);
const BILLS = ['/bill/2010/hb1547'];
// HB 1547 of 2010's one report, rewritten in the page's data: "recOnly" is the
// shape of an interim study statement (a recommendation, no vote, no text);
// "both" keeps the 17-1 vote and drops the text. The real statement arrives
// with feat/interim-study-statements and is not on the preview yet.
const MODES = { recOnly: h => h.replace(/"vote_yeas": 17, "vote_nays": 1, "text": "Discount[^"]*"/, '"vote_yeas": null, "vote_nays": null, "text": ""'),
                both:    h => h.replace(/("vote_yeas": 17, "vote_nays": 1, "text": )"Discount[^"]*"/, '$1""') };
fs.mkdirSync(OUT, { recursive: true });
const js = fs.readFileSync(WT + '/src/pages/app.js');
const css = fs.readFileSync(WT + '/src/pages/app.css');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const report = [];
  for (const path of BILLS) for (const mode of Object.keys(MODES)) for (const width of [390, 1280]) for (const scheme of ['light', 'dark']) {
    if (mode === 'both' && !(width === 1280 && scheme === 'light')) continue;
    const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: scheme });
    const served = [];
    await ctx.route('**/*', async route => {
      const u = route.request().url();
      if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
      const url = new URL(u);
      if (/\/app(\.[0-9a-f]+)?\.js$/.test(url.pathname)) { served.push(url.pathname); return route.fulfill({ status: 200, headers: { 'content-type': 'text/javascript; charset=utf-8' }, body: js }); }
      if (/\/app(\.[0-9a-f]+)?\.css$/.test(url.pathname)) { served.push(url.pathname); return route.fulfill({ status: 200, headers: { 'content-type': 'text/css; charset=utf-8' }, body: css }); }
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400) return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      let body = Buffer.from(await r.arrayBuffer());
      if (url.pathname === path) { const h = body.toString('utf8'), h2 = MODES[mode](h); if (h2 === h) throw new Error('no rewrite for ' + mode); body = Buffer.from(h2); }
      return route.fulfill({ status: r.status, headers: { 'content-type': r.headers.get('content-type') || '' }, body });
    });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', e => errors.push(String(e)));
    const resp = await p.goto(B + path, { waitUntil: 'load', timeout: 90000 });
    await p.waitForTimeout(1200);
    const t = p.getByRole('tab', { name: /^Reports/i }).first();
    const hasTab = await t.count();
    if (hasTab) { await t.click(); await p.waitForTimeout(900); }
    const info = await p.evaluate(() => {
      const notes = [...document.querySelectorAll('.repblock .note')].map(n => n.innerText.trim());
      const first = document.querySelector('.repblock');
      if (first) first.scrollIntoView({ block: 'center' });
      return { notes, blocks: document.querySelectorAll('.repblock').length };
    });
    const slug = path.split('/').filter(Boolean).slice(1).join('-');
    const shot = `${OUT}/reports-${slug}-${mode}-${width}-${scheme}.png`;
    const sec = await p.$('.repblock');
    const panel = sec ? await sec.evaluateHandle(n => n.closest('section,[role=tabpanel],.tabpanel') || n.parentElement) : null;
    if (panel) await panel.asElement().screenshot({ path: shot }); else await p.screenshot({ path: shot });
    report.push({ path, mode, width, scheme, status: resp && resp.status(), hasTab, served: [...new Set(served)], errors, ...info, shot });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(report, null, 1));
})();
