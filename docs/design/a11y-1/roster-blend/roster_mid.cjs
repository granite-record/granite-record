// The blend at the in-between widths, and what a screen reader is given for
// a row and for the rostrum.
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT] = process.argv.slice(2);
const css = fs.readFileSync(WT + '/src/pages/app.css');
const real = fs.readFileSync(__dirname + '/officials_real.html');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const out = [];
  for (const width of [768, 1024, 1180, 1440]) {
    const ctx = await b.newContext({ viewport: { width, height: 900 } });
    await ctx.route('**/*', async route => {
      const u = route.request().url();
      if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
      const url = new URL(u);
      if (url.pathname === '/app.css') return route.fulfill({ status: 200, headers: { 'content-type': 'text/css' }, body: css });
      if (/^\/officials(\.html)?$/.test(url.pathname)) return route.fulfill({ status: 200, headers: { 'content-type': 'text/html; charset=utf-8' }, body: real });
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400) return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      return route.fulfill({ status: r.status, headers: { 'content-type': r.headers.get('content-type') || '' }, body: Buffer.from(await r.arrayBuffer()) });
    });
    const p = await ctx.newPage();
    await p.goto(B + '/officials', { waitUntil: 'load', timeout: 90000 });
    await p.waitForTimeout(1000);
    await p.evaluate(() => { const t = document.getElementById('tab-legislators'); if (t) t.click(); });
    await p.click('#tab-seat'); await p.waitForTimeout(600);
    const info = await p.evaluate(() => {
      const list = document.getElementById('seatlist');
      const rost = list.querySelector('.srost .mchip').getBoundingClientRect();
      const cards = [...list.querySelectorAll('.seatdivs .mchip')].map(c => Math.round(c.getBoundingClientRect().width));
      const over = document.documentElement.scrollWidth > innerWidth;
      return { rostrumW: Math.round(rost.width), divCardW: [Math.min(...cards), Math.max(...cards)], hScroll: over,
               height: Math.round(list.getBoundingClientRect().height) };
    });
    if (width === 1024) {
      info.ariaRow = await p.locator('#seatlist .seatdivs .seatrow').first().ariaSnapshot();
      info.ariaRostrum = await p.locator('#seatlist .srost .seatrow').first().ariaSnapshot();
      await p.locator('#seatlist').screenshot({ path: __dirname + '/real/roster-real-1024-light.png' });
    }
    out.push({ width, ...info });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out, null, 1));
})();
