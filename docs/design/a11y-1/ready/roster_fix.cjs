// After the review's fixes: on the preview's 382 rows (officials_real.html,
// passed through the branch's seat_row_tag) with the worktree's app.css, is
// every card's number and empty space the link; is a lit card lit; does the
// focus ring go round the card.
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'https://dry-run.graniterecord.pages.dev';
const [WT, OUT] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const css = fs.readFileSync(WT + '/src/pages/app.css');
const real = fs.readFileSync(__dirname + '/officials_real.html');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const out = [];
  for (const [width, scheme, forced] of [[390, 'light', 'none'], [1280, 'light', 'none'], [1280, 'dark', 'none'], [768, 'light', 'none'], [1280, 'light', 'active']]) {
    const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, forcedColors: forced });
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
    await p.click('#tab-seat'); await p.waitForTimeout(700);
    const hit = await p.evaluate(() => {
      const chips = [...document.querySelectorAll('#seatlist .seatrow .mchip')];
      let numOut = 0, deadPx = 0, linePx = 0, height = 0;
      for (const c of chips) {
        c.scrollIntoView({ block: 'center' });
        const r = c.getBoundingClientRect(), n = c.querySelector('.mseat');
        if (n) { const nr = n.getBoundingClientRect(); const e = document.elementFromPoint(nr.left + nr.width / 2, nr.top + nr.height / 2);
          if (!e || !e.closest('a') || !c.contains(e.closest('a'))) numOut++; }
        const y = r.top + Math.min(14, r.height / 2);
        for (let x = Math.ceil(r.left); x < r.right; x += 2) { linePx++; const e = document.elementFromPoint(x, y);
          if (!e || !e.closest('a') || !c.contains(e.closest('a'))) deadPx++; }
      }
      height = Math.round(document.getElementById('seatlist').getBoundingClientRect().height);
      return { cards: chips.length, numbersOutsideLink: numOut, deadShare: Math.round(deadPx / linePx * 1000) / 10 + '%', height };
    });
    await p.selectOption('#sgo', '1002'); await p.waitForTimeout(500);
    const lit = await p.evaluate(() => { const row = document.querySelector('#seatlist .seatrow[data-seat="1002"]'); const c = row.querySelector('.mchip');
      row.scrollIntoView({ block: 'center' }); const cs = getComputedStyle(c);
      const ring = getComputedStyle(c.querySelector('a'), '::before'); return { on: row.classList.contains('on'), bg: cs.backgroundColor, outline: `${ring.outlineStyle} ${ring.outlineWidth} ${ring.outlineColor}` }; });
    const row = await p.$('#seatlist .seatrow[data-seat="1002"]');
    const tag = `${width}-${scheme}${forced === 'active' ? '-forced' : ''}`;
    await row.screenshot({ path: `${OUT}/lit-${tag}.png` });
    await p.focus('#seatlist .seatrow[data-seat="1003"] .mchip > a'); await p.keyboard.press('Shift+Tab'); await p.keyboard.press('Tab'); await p.waitForTimeout(200);
    const foc = await p.evaluate(() => { const a = document.activeElement; const after = getComputedStyle(a, '::before');
      return { active: a.textContent.replace(/\s+/g, ' ').trim().slice(0, 30), linkOutline: getComputedStyle(a).outlineStyle, ring: `${after.outlineStyle} ${after.outlineWidth}` }; });
    const r3 = await p.$('#seatlist .seatrow[data-seat="1003"]');
    await r3.screenshot({ path: `${OUT}/focus-${tag}.png` });
    out.push({ width, scheme, forced, ...hit, lit, focus: foc });
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out, null, 1));
})();
