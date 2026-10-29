const { chromium } = require('playwright'); const fs = require('fs');
const AXE = fs.readFileSync(__dirname + '/../node_modules/axe-core/axe.min.js', 'utf8');
(async () => { const b = await chromium.launch(); const p = await b.newPage();
  await p.goto((process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev') + '/bill/2026/hb1681', { waitUntil: 'networkidle' });
  await p.addScriptTag({ content: AXE });
  console.log('axe defined:', await p.evaluate(() => typeof window.axe));
  await p.evaluate(() => { const i = document.createElement('img'); i.src = '/icon-32.png'; document.querySelector('main').append(i); const s = document.createElement('p'); s.style.color = '#ccc'; s.textContent = 'low contrast test'; document.querySelector('main').append(s); });
  const r = await p.evaluate(async () => { const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }); return { v: r.violations.map(v => v.id + ':' + v.nodes.length), passes: r.passes.length, inc: r.incomplete.map(v => v.id + ':' + v.nodes.length) }; });
  console.log(JSON.stringify(r)); await b.close(); })();
