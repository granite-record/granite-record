const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
  await p.goto((process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev') + '/laws/659', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  // Find the element whose removal fixes the width, by bisecting the body's children, then descending.
  const r = await p.evaluate(() => {
    const de = document.documentElement, vw = de.clientWidth;
    const wide = () => de.scrollWidth > vw + 2;
    let node = document.body, path = [];
    for (let depth = 0; depth < 25; depth++) {
      let culprit = null;
      for (const c of [...node.children]) { const d = c.style.display; c.style.display = 'none'; const ok = !wide(); c.style.display = d; if (ok) { culprit = c; break; } }
      if (!culprit) break;
      const cs = getComputedStyle(culprit);
      path.push(`${culprit.tagName.toLowerCase()}${culprit.id ? '#' + culprit.id : ''}.${typeof culprit.className === 'string' ? culprit.className.split(' ').slice(0, 2).join('.') : ''} pos=${cs.position} w=${Math.round(culprit.getBoundingClientRect().width)} sw=${culprit.scrollWidth} "${(culprit.textContent || '').trim().slice(0, 50)}"`);
      node = culprit;
    }
    return path; });
  console.log(r.join('\n'));
  await p.evaluate(() => window.scrollTo(258, 0)); await p.waitForTimeout(200); await p.screenshot({ path: __dirname + '/../shots/laws659-390-scrolled.png' });
  await b.close(); })();
