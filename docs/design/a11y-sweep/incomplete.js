const { chromium } = require('playwright'); const fs = require('fs');
const AXE = fs.readFileSync(__dirname + '/node_modules/axe-core/axe.min.js', 'utf8');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const src = fs.readFileSync(__dirname + '/sweep.js', 'utf8');
const PAGES = eval(src.slice(src.indexOf('const PAGES = [') + 14, src.indexOf('];', src.indexOf('const PAGES = [')) + 1));
require('fs').mkdirSync(__dirname + '/results', { recursive: true });
(async () => { const b = await chromium.launch(); const out = [];
  for (const [name, path, steps] of PAGES) for (const w of [390, 1280]) for (const m of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, isMobile: w < 600, colorScheme: m }); const p = await ctx.newPage();
    try { await p.goto(B + path, { waitUntil: 'networkidle', timeout: 60000 }); for (const s of steps || []) { await p.click(s); await p.waitForTimeout(600); }
      await p.addScriptTag({ content: AXE });
      const r = await p.evaluate(async () => { const r = await axe.run(document, { runOnly: { type: 'rule', values: ['color-contrast', 'target-size', 'link-in-text-block'] } });
        return r.incomplete.flatMap(v => v.nodes.map(n => ({ rule: v.id, t: n.target.join(' '), why: (n.any[0] || {}).message, data: (n.any[0] || {}).data, text: n.html.replace(/<[^>]+>/g, '').trim().slice(0, 50) }))); });
      for (const x of r) out.push({ view: `${name}_${w}_${m}`, ...x });
      console.log(name, w, m, r.length);
    } catch (e) { console.log(name, w, m, 'ERR', e.message.split('\n')[0]); }
    await ctx.close(); }
  fs.writeFileSync(__dirname + '/results/incomplete.json', JSON.stringify(out, null, 1)); await b.close(); })();
