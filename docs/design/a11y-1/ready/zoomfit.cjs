// The branch's built /officials (the fixture's, every place of the floor drawn)
// served on the preview's origin with the branch's app.css: the chart's
// opening zoom and the zoom buttons' boxes, light, dark and forced colours.
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT, OUT] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const css = fs.readFileSync(WT + '/src/pages/app.css');
const pages = { '/officials': fs.readFileSync(__dirname + '/fx/officials.html'), '/es/officials': fs.readFileSync(__dirname + '/fx/es/officials.html') };
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const out = [];
  const runs = [[390, 'light', 'none', '/officials'], [390, 'dark', 'none', '/officials'], [1280, 'light', 'none', '/officials'],
                [1024, 'light', 'none', '/officials'], [390, 'light', 'active', '/officials'], [1280, 'dark', 'active', '/officials'], [390, 'light', 'none', '/es/officials']];
  for (const [width, scheme, forced, path] of runs) {
    const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, forcedColors: forced });
    await ctx.route('**/*', async route => {
      const u = route.request().url();
      if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
      const url = new URL(u);
      if (url.pathname === '/app.css') return route.fulfill({ status: 200, headers: { 'content-type': 'text/css' }, body: css });
      const pth = url.pathname.replace(/\.html$/, '');
      if (pages[pth]) return route.fulfill({ status: 200, headers: { 'content-type': 'text/html; charset=utf-8' }, body: pages[pth] });
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400) return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      return route.fulfill({ status: r.status, headers: { 'content-type': r.headers.get('content-type') || '' }, body: Buffer.from(await r.arrayBuffer()) });
    });
    const p = await ctx.newPage();
    const errors = []; p.on('pageerror', e => errors.push(String(e)));
    await p.goto(B + path, { waitUntil: 'load', timeout: 90000 });
    await p.waitForTimeout(800);
    await p.evaluate(() => { const t = document.getElementById('tab-legislators'); if (t) t.click(); });
    const seat = await p.$('#tab-seat'); if (seat) await seat.click();
    await p.waitForTimeout(800);
    const info = await p.evaluate(() => {
      const wrap = document.querySelector('.seatwrap'), svg = document.querySelector('.seatmap');
      const btn = id => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect();
        const s = e.querySelector('svg'); const sr = s && s.getBoundingClientRect(); const cs = getComputedStyle(e);
        return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10, label: e.getAttribute('aria-label'), title: e.getAttribute('title'),
                 color: cs.color, border: cs.borderTopColor, icon: sr ? { dx: Math.round((sr.left + sr.width / 2 - (r.left + r.width / 2)) * 10) / 10,
                 dy: Math.round((sr.top + sr.height / 2 - (r.top + r.height / 2)) * 10) / 10, stroke: getComputedStyle(s.querySelector('path')).stroke } : null }; };
      const before = { svgW: Math.round(svg.getBoundingClientRect().width), wrapW: wrap.clientWidth, inline: svg.style.width || null };
      document.getElementById('szin').click();
      const zoomed = Math.round(svg.getBoundingClientRect().width);
      document.getElementById('szfit').click();
      const back = Math.round(svg.getBoundingClientRect().width);
      document.querySelector('.seatzoom').scrollIntoView({ block: 'center' });
      return { open: before, afterPlus: zoomed, afterFit: back, out: btn('szout'), inn: btn('szin'), fit: btn('szfit') };
    });
    const shot = `${OUT}/zoom-${path.replace(/\W+/g, '')}-${width}-${scheme}${forced === 'active' ? '-forced' : ''}.png`;
    const bar = await p.$('.seatbar');
    if (bar) await bar.screenshot({ path: shot });
    out.push({ width, scheme, forced, path, errors, ...info, shot });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out, null, 1));
})();
