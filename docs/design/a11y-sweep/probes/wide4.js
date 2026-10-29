const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
  await p.goto((process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev') + '/laws/659', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  const r = await p.evaluate(() => { const t = document.querySelector('#s27-a .rs-text');
    const words = t.textContent.split(/\s+/).filter(w => w.length > 25).slice(0, 5);
    const kids = [...t.children].map(c => `${c.tagName.toLowerCase()}.${c.className} sw=${c.scrollWidth} w=${Math.round(c.getBoundingClientRect().width)} ws=${getComputedStyle(c).whiteSpace}`).filter(s => !/sw=(\d+) w=\1/.test(s)).slice(0, 6);
    return { words, kids, html: t.innerHTML.match(/_{10,}|[^\s<>]{40,}/g)?.slice(0, 3) }; });
  console.log(JSON.stringify(r, null, 1));
  // Other chapters: is this a pattern? Check every section's text for width.
  const all = await p.evaluate(() => [...document.querySelectorAll('.rs-text')].filter(t => t.scrollWidth > t.clientWidth + 2).map(t => t.closest('section').id));
  console.log('sections too wide on 659:', all.join(' '));
  await b.close(); })();
