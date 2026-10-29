const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const PAGES = [['/', []], ['/bill/2026/hb1681', []], ['/bill/2026/hb1681', ['#tab_HB1681_1']], ['/legislator/joe-alexander-hills-29', []], ['/officials', []], ['/officials', ['#tab-legislators', '#tab-seat']], ['/town/goffstown', ['#tab-map']], ['/calendar', []], ['/bills', ['#ftoggle']], ['/guides/how-to-vote', []], ['/learn/general-court', []], ['/laws', []]];
(async () => { const b = await chromium.launch();
  for (const [path, steps] of PAGES) {
    const p = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    await p.goto(B + path, { waitUntil: 'networkidle', timeout: 60000 }); for (const s of steps) { await p.click(s); await p.waitForTimeout(600); }
    const small = await p.evaluate(() => {
      const out = {}; const sel = 'a[href],button,input:not([type=hidden]),select,summary,[role=button],[role=tab],[tabindex="0"]';
      const els = [...document.querySelectorAll(sel)];
      const rects = els.map(e => e.getBoundingClientRect());
      els.forEach((e, i) => { const r = rects[i]; const c = getComputedStyle(e);
        if (r.width === 0 || r.height === 0 || c.visibility === 'hidden') return;
        if (e.closest('.sr,[hidden]') || (r.width <= 1 && r.height <= 1)) return;
        // Inline links inside a sentence are excepted by 2.5.8.
        if (c.display === 'inline' && e.tagName === 'A' && e.parentElement && /^(P|LI|TD|DD|SPAN|DIV)$/.test(e.parentElement.tagName) && e.parentElement.textContent.trim().length > e.textContent.trim().length + 15) return;
        if (r.width >= 24 && r.height >= 24) return;
        // Spacing exception: a 24px circle centred on it must not meet another target.
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const crowded = rects.some((q, j) => j !== i && q.width > 0 && (Math.max(q.left - cx, 0, cx - q.right) ** 2 + Math.max(q.top - cy, 0, cy - q.bottom) ** 2) < 144);
        if (!crowded) return;
        const k = `${e.tagName.toLowerCase()}.${(typeof e.className === 'string' ? e.className : e.getAttribute('class') || '').split(' ')[0]} ${Math.round(r.width)}x${Math.round(r.height)}`;
        out[k] = out[k] || { n: 0, eg: (e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30) }; out[k].n++; });
      return out; });
    console.log('==', path, steps.join(' '), '\n', Object.entries(small).slice(0, 8).map(([k, v]) => `${k} x${v.n} "${v.eg}"`).join('\n '));
    await p.close(); }
  await b.close(); })();
