// Runs the repo's own measure() (src/checks/sweep_browser.js, read-only) on the preview.
const { chromium } = require('playwright'); const fs = require('fs');
const lines = fs.readFileSync(require('path').resolve(__dirname, '../../../src/checks/sweep_browser.js'), 'utf8').split('\n');
const MEASURE = lines.slice(177, 522).join('\n');
const src = fs.readFileSync(__dirname + '/sweep.js', 'utf8');
const PAGES = eval(src.slice(src.indexOf('const PAGES = [') + 14, src.indexOf('];', src.indexOf('const PAGES = [')) + 1));
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
require('fs').mkdirSync(__dirname + '/results', { recursive: true });
(async () => { const b = await chromium.launch(); const out = [];
  for (const [name, path, steps] of PAGES) for (const w of [390, 1280]) for (const m of ['light', 'dark', 'forced', 'text24']) {
    const ctx = await b.newContext({ viewport: { width: w, height: w < 600 ? 844 : 900 }, isMobile: w < 600, hasTouch: w < 600,
      colorScheme: m === 'dark' ? 'dark' : 'light', forcedColors: m === 'forced' ? 'active' : 'none' });
    const p = await ctx.newPage();
    try {
      if (m === 'text24') { const c = await ctx.newCDPSession(p); await c.send('Page.enable'); await c.send('Page.setFontSizes', { fontSizes: { standard: 24, fixed: 20 } }); }
      await p.goto(B + path, { waitUntil: 'load', timeout: 90000 }); await p.waitForTimeout(2500);
      for (const s of steps || []) { await p.click(s); await p.waitForTimeout(700); }
      const r = await p.evaluate(`(${MEASURE})(${JSON.stringify({ standard: m === 'text24' ? 24 : 16 })})`);
      out.push({ view: `${name}_${w}_${m}`, page: name, w, m, rootPx: r.rootPx, contrast: r.contrast, overflow: r.overflow, overlap: r.overlap, headings: r.headings, small: r.text.small.slice(0, 5), min: r.text.min, minAt: r.text.minAt });
      console.log(name, w, m, 'contrast fails', r.contrast.failures, 'sideways', r.overflow.sideways, 'poking', r.overflow.poking.length, 'clipped', r.overflow.clipped.length, 'overlap', r.overlap.count, 'edgeCut', (r.overlap.edgeCut || []).length);
    } catch (e) { console.log(name, w, m, 'ERR', e.message.split('\n')[0]); out.push({ view: `${name}_${w}_${m}`, error: e.message.split('\n')[0] }); }
    await ctx.close();
    fs.writeFileSync(__dirname + '/results/measure.json', JSON.stringify(out, null, 1));
  }
  await b.close(); })();
