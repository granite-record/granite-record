const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev'), SH = __dirname + '/../shots/';
const fi = p => p.evaluate(() => { const e = document.activeElement; return e === document.body ? 'body' : `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''} "${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 40)}" ti=${e.tabIndex}`; });
(async () => {
  const b = await chromium.launch();
  // Seat chart: focus a seat, arrows, Enter; and what Tab does after the seat.
  { const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
    await p.goto(B + '/officials', { waitUntil: 'networkidle' }); await p.click('#tab-legislators'); await p.click('#tab-seat'); await p.waitForTimeout(800);
    await p.evaluate(() => { window.__l = []; const n = document.getElementById('seatnote'); new MutationObserver(() => window.__l.push(n.textContent.trim().slice(0, 90))).observe(n, { childList: true, subtree: true, characterData: true }); });
    const c = await p.$('#pane-seat circle[tabindex="0"], #pane-seat [tabindex="0"]');
    await c.focus(); console.log('seat focused:', await fi(p));
    for (const k of ['ArrowRight', 'ArrowRight', 'ArrowDown', 'Enter', 'Escape']) { await p.keyboard.press(k); await p.waitForTimeout(300); console.log(' ', k, '->', await fi(p)); }
    console.log(' seatnote said:', JSON.stringify(await p.evaluate(() => window.__l)));
    await p.keyboard.press('Tab'); await p.waitForTimeout(200); console.log(' Tab after seat ->', await fi(p));
    await p.keyboard.press('Tab'); console.log(' Tab again ->', await fi(p));
    const ring = await p.evaluate(() => { const e = document.querySelector('#pane-seat circle[tabindex="0"]'); e.focus(); const c = getComputedStyle(e); return `outline ${c.outlineStyle} ${c.outlineWidth} stroke ${c.stroke} ${c.strokeWidth}`; });
    console.log(' seat focus style:', ring);
    const el = await p.$('#pane-seat svg'); await el.screenshot({ path: SH + 'seat-focused.png' });
    await p.close(); }
  // Map: does the group respond to arrows / plus?
  { const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
    await p.goto(B + '/officials', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
    const g = await p.$('[role=group][aria-label*="map" i]');
    const snap = () => p.evaluate(() => { const g = document.querySelector('[role=group][aria-label*="map" i]'); return [...g.querySelectorAll('svg, svg > g, [transform]')].slice(0, 4).map(e => (e.getAttribute('viewBox') || '') + (e.getAttribute('transform') || '') + (e.style.transform || '')).join('|'); });
    const s0 = await snap(); await g.focus(); console.log('map focus:', await fi(p));
    await p.keyboard.press('ArrowRight'); await p.keyboard.press('ArrowRight'); await p.keyboard.press('Equal'); await p.keyboard.press('Shift+Equal'); await p.waitForTimeout(500);
    const s1 = await snap(); console.log(' map moved by keys:', s0 !== s1, '\n ', s0.slice(0, 120), '\n ', s1.slice(0, 120));
    const style = await g.evaluate(e => { const c = getComputedStyle(e); return `outline ${c.outlineStyle} ${c.outlineWidth}; shadow ${c.boxShadow}`; }); console.log(' map focus style:', style);
    await g.screenshot({ path: SH + 'map-focused.png' });
    // Can a district be reached and chosen by keyboard?
    const d = await p.$('[role=group][aria-label*="map" i] [role=button], [role=group][aria-label*="map" i] button');
    console.log(' district buttons:', await p.evaluate(() => document.querySelectorAll('[role=group][aria-label*="map" i] button, [role=group][aria-label*="map" i] [role=button]').length), 'first tabIndex', d ? await d.evaluate(e => e.tabIndex) : '-');
    await p.close(); }
  // Forced colours: the search box, focused and not.
  { const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, forcedColors: 'active' }); const p = await ctx.newPage();
    await p.goto(B + '/', { waitUntil: 'networkidle' });
    const hq = await p.$('#hq'); const st = () => p.$eval('#hq', e => { const c = getComputedStyle(e); return `outline ${c.outlineStyle} ${c.outlineWidth} ${c.outlineColor}; border ${c.borderWidth} ${c.borderColor}`; });
    const a = await st(); await hq.screenshot({ path: SH + 'forced-hq-plain.png' });
    await p.keyboard.press('Tab'); await hq.focus(); await p.waitForTimeout(200); const b2 = await st(); await hq.screenshot({ path: SH + 'forced-hq-focus.png' });
    console.log('forced #hq plain:', a, '\n        focused:', b2);
    await ctx.close(); }
  // The search page: are results drawn as you type, and is there any count?
  { const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
    await p.goto(B + '/search', { waitUntil: 'networkidle' }); await p.type('#resq', 'goffstown', { delay: 60 }); await p.waitForTimeout(1500);
    console.log('search page after typing:', (await p.evaluate(() => document.querySelector('main').innerText)).slice(0, 300).replace(/\n/g, ' / '));
    await p.screenshot({ path: SH + 'search-typed.png' }); await p.close(); }
  await b.close();
})();
