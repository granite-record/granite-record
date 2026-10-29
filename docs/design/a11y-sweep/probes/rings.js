const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
(async () => { const b = await chromium.launch();
  for (const sch of ['light', 'dark']) for (const path of ['/', '/bill/2026/hb1681', '/town/goffstown', '/guides/how-to-vote']) {
    const p = await b.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: sch });
    await p.goto(B + path, { waitUntil: 'networkidle' });
    const st = {};
    for (let i = 0; i < 45; i++) { await p.keyboard.press('Tab');
      const s = await p.evaluate(() => { const e = document.activeElement; if (!e || e === document.body) return null; const c = getComputedStyle(e);
        let bg = null; for (let a = e; a; a = a.parentElement) { const k = getComputedStyle(a).backgroundColor; if (k !== 'rgba(0, 0, 0, 0)') { bg = k; break; } }
        return { k: `outline ${c.outlineStyle} ${c.outlineWidth} ${c.outlineColor} off ${c.outlineOffset} | shadow ${c.boxShadow}`, bg, tag: e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') }; });
      if (s) { const key = s.k + ' on ' + s.bg; st[key] = st[key] || new Set(); st[key].add(s.tag); } }
    console.log('==', sch, path); for (const [k, v] of Object.entries(st)) console.log('  ', k, '::', [...v].slice(0, 6).join(' '));
    await p.close(); }
  await b.close(); })();
