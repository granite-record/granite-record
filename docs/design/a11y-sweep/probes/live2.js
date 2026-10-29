const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const watch = p => p.evaluate(() => { window.__l = []; for (const e of document.querySelectorAll('[aria-live],[role=status],[role=alert]')) new MutationObserver(() => window.__l.push(`${e.id || e.className}: "${e.textContent.trim().slice(0, 70)}"`)).observe(e, { childList: true, subtree: true, characterData: true }); });
(async () => { const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  { const p = await ctx.newPage(); await p.goto(B + '/', { waitUntil: 'networkidle' }); await watch(p);
    await p.focus('#hq'); await p.keyboard.press('Enter'); await p.waitForTimeout(800);
    console.log('home search, empty Enter: said', JSON.stringify(await p.evaluate(() => window.__l || [])), '| url', p.url());
    await p.goto(B + '/', { waitUntil: 'networkidle' }); await watch(p);
    await p.fill('#hq', 'zzzzqqq'); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
    console.log('home search, no match: said', JSON.stringify(await p.evaluate(() => window.__l || [])), '| url', p.url()); await p.close(); }
  { const p = await ctx.newPage(); await p.goto(B + '/bill/2026/hb1681', { waitUntil: 'networkidle' }); await watch(p);
    await p.click('button:has-text("Cite")').catch(() => {}); await p.waitForTimeout(300);
    const c = await p.$('button[aria-label="Copy the MLA citation"], button:has-text("Copy the MLA")');
    if (c) { await c.click({ force: true }).catch(e => console.log('click', e.message.split('\n')[0])); await p.waitForTimeout(800); }
    await p.click('button:has-text("Share")').catch(() => {}); await p.waitForTimeout(800);
    console.log('bill cite/share: said', JSON.stringify(await p.evaluate(() => window.__l))); await p.close(); }
  { const p = await ctx.newPage(); await p.goto(B + '/search?q=goffstown', { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
    const live = await p.$$eval('[aria-live],[role=status]', es => es.map(e => `${e.id}:${e.textContent.trim().slice(0, 40)}`));
    const res = await p.evaluate(() => { const m = document.querySelector('main'); const h = [...m.querySelectorAll('[aria-live],[role=status],[role=region],h2')].map(e => e.tagName + ':' + e.textContent.trim().slice(0, 30)); return h; });
    console.log('search page: live regions', live, '| structure', res.slice(0, 6)); await p.close(); }
  await b.close(); })();
