const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev'), SH = __dirname + '/../shots/';
const L = c => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(v => { v = v / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const x = L(a), y = L(b); return ((Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)).toFixed(2); };
(async () => { const b = await chromium.launch();
  for (const sch of ['light', 'dark']) {
    const p = await b.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: sch });
    await p.goto(B + '/', { waitUntil: 'networkidle' });
    const get = () => p.$eval('#hq', e => { const c = getComputedStyle(e); let bg; for (let a = e.parentElement; a; a = a.parentElement) { const k = getComputedStyle(a).backgroundColor; if (k !== 'rgba(0, 0, 0, 0)') { bg = k; break; } } return { border: c.borderColor, bw: c.borderWidth, shadow: c.boxShadow, bg, fill: c.backgroundColor }; });
    const a = await get(); await (await p.$('#hq')).screenshot({ path: SH + `hq-${sch}-plain.png` });
    await p.focus('#hq'); await p.keyboard.press('Shift+Tab'); await p.keyboard.press('Tab'); await p.waitForTimeout(200);
    const f = await get(); const el = await p.$('#hq'); const bb = await el.boundingBox();
    await p.screenshot({ path: SH + `hq-${sch}-focus.png`, clip: { x: bb.x - 8, y: bb.y - 8, width: bb.width + 16, height: bb.height + 16 } });
    const ring = f.shadow.match(/rgba?\([^)]*\)/)[0];
    console.log(sch, 'plain', JSON.stringify(a), '\n  focus', JSON.stringify(f), '\n  ring vs page', ratio(ring, f.bg), '| border focused vs page', ratio(f.border, f.bg), '| border plain vs page', ratio(a.border, a.bg));
    await p.close(); }
  await b.close(); })();
