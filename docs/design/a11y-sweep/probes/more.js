const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const fi = p => p.evaluate(() => { const e = document.activeElement; return e === document.body ? 'body' : `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''} "${(e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30)}"`; });
(async () => { const b = await chromium.launch();
  // Menu: Escape from inside it, on a phone.
  { const p = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true }); await p.goto(B + '/', { waitUntil: 'networkidle' });
    await p.focus('#navmenu'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
    const items = await p.$$eval('#navdrop a', a => a.length); await p.keyboard.press('Tab'); const inside = await fi(p);
    await p.keyboard.press('Escape'); await p.waitForTimeout(300);
    console.log('menu: items', items, '| Tab from button ->', inside, '| Escape ->', await fi(p), 'expanded', await p.getAttribute('#navmenu', 'aria-expanded'));
    // Escape straight from the button
    await p.focus('#navmenu'); await p.keyboard.press('Enter'); await p.waitForTimeout(300); await p.keyboard.press('Escape'); await p.waitForTimeout(300);
    console.log('menu: Escape from the button ->', await fi(p), 'expanded', await p.getAttribute('#navmenu', 'aria-expanded'));
    await p.close(); }
  // Bill tabs and the vote party buttons.
  { const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); await p.goto(B + '/bill/2026/hb1681', { waitUntil: 'networkidle' });
    await p.focus('#tab_HB1681_0'); const r = [];
    for (const k of ['ArrowRight', 'ArrowRight', 'End', 'Home']) { await p.keyboard.press(k); await p.waitForTimeout(250); r.push(k + '->' + await fi(p) + ' sel=' + await p.evaluate(() => document.querySelector('[role=tab][aria-selected=true]')?.id)); }
    console.log('bill tabs:', r.join(' | '));
    await p.click('#tab_HB1681_1'); await p.waitForTimeout(500);
    const vb = await p.$$eval('#pane_HB1681_1 button', bs => bs.slice(0, 8).map(e => `"${e.textContent.trim().replace(/\s+/g, ' ').slice(0, 25)}" pressed=${e.getAttribute('aria-pressed')} expanded=${e.getAttribute('aria-expanded')} label=${e.getAttribute('aria-label')}`));
    console.log('vote buttons:', vb.join(' ; '));
    const btn = await p.$('#pane_HB1681_1 button'); if (btn) { await btn.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(500);
      console.log(' after Enter on first vote button:', await btn.evaluate(e => `pressed=${e.getAttribute('aria-pressed')} expanded=${e.getAttribute('aria-expanded')}`), '| focus', await fi(p)); }
    await p.close(); }
  // Seat chart: what does the lost Tab land on?
  { const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); await p.goto(B + '/officials', { waitUntil: 'networkidle' });
    await p.click('#tab-legislators'); await p.click('#tab-seat'); await p.waitForTimeout(800);
    await p.evaluate(() => { window.__f = []; document.addEventListener('focusin', e => window.__f.push((e.target.tagName || '') + '#' + (e.target.id || '') + '.' + (e.target.getAttribute && (e.target.getAttribute('class') || ''))), true); document.addEventListener('focusout', e => window.__f.push('out:' + e.target.tagName), true); });
    await (await p.$('#pane-seat circle[tabindex="0"]')).focus(); await p.keyboard.press('Tab'); await p.waitForTimeout(200);
    console.log('seat Tab: focus events', JSON.stringify(await p.evaluate(() => window.__f)), '->', await fi(p));
    await p.close(); }
  await b.close(); })();
