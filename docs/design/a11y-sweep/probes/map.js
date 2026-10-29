const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev'), SH = __dirname + '/../shots/';
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto(B + '/officials', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  const g = await p.$('[role=group][aria-label*="map" i]');
  await g.focus(); const a = await g.screenshot({ path: SH + 'map-0.png' });
  for (let i = 0; i < 6; i++) await p.keyboard.press('ArrowRight');
  await p.keyboard.press('+'); await p.waitForTimeout(700); const c = await g.screenshot({ path: SH + 'map-1.png' });
  console.log('map image changed after arrows and +:', !a.equals(c));
  console.log(await g.evaluate(e => e.outerHTML.slice(0, 400)));
  await b.close();
})();
