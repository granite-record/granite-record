// Read-only keyboard and live-region checks on the dry-run preview.
const { chromium } = require('playwright');
const B = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const SH = __dirname + '/shots/';
const log = (...a) => console.log(...a);
const focusInfo = p => p.evaluate(() => {
  const e = document.activeElement; if (!e || e === document.body) return 'body';
  return `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''} "${(e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40)}"`;
});
async function page(b, path, w = 1280, opts = {}) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, isMobile: w < 600, hasTouch: w < 600, ...opts });
  const p = await ctx.newPage(); await p.goto(B + path, { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(500); return [ctx, p];
}
// Watch every live region's text, and report what changed.
const watchLive = p => p.evaluate(() => {
  window.__live = [];
  for (const e of document.querySelectorAll('[aria-live],[role=status],[role=alert]')) {
    new MutationObserver(() => window.__live.push(`${e.tagName.toLowerCase()}#${e.id || '?'}.${e.className}: "${e.textContent.trim().slice(0, 80)}"`))
      .observe(e, { childList: true, subtree: true, characterData: true });
  }
});
const liveSaid = p => p.evaluate(() => [...new Set(window.__live)]);

(async () => {
  const b = await chromium.launch();
  // A. The Sections menu on a phone: its tab order when open, and Escape from inside it.
  { const [ctx, p] = await page(b, '/', 390);
    await p.focus('#navmenu'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
    const exp = await p.getAttribute('#navmenu', 'aria-expanded');
    await p.keyboard.press('Tab'); const inside = await focusInfo(p);
    await p.keyboard.press('Escape'); await p.waitForTimeout(300);
    log('A menu: expanded after Enter =', exp, '| Tab ->', inside, '| Escape -> expanded', await p.getAttribute('#navmenu', 'aria-expanded'), ', focus', await focusInfo(p));
    await p.focus('#navmenu'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
    const seq = []; for (let i = 0; i < 14; i++) { await p.keyboard.press('Tab'); seq.push(await focusInfo(p)); }
    log('  tab order after opening:', seq.join(' > '));
    await p.focus('#navmenu'); await p.waitForTimeout(200);
    await p.screenshot({ path: SH + 'menu-390-open.png' });
    await ctx.close(); }
  // B. Town tabs: arrow keys and the tab order into the panel.
  { const [ctx, p] = await page(b, '/town/goffstown');
    await p.focus('#tab-representatives');
    const r = [];
    for (const k of ['ArrowRight', 'ArrowRight', 'End', 'Home', 'ArrowLeft']) {
      await p.keyboard.press(k); await p.waitForTimeout(250);
      r.push(`${k}: focus ${await focusInfo(p)} selected=${await p.evaluate(() => document.querySelector('[role=tab][aria-selected=true]')?.id)}`);
    }
    await p.focus('#tab-representatives'); await p.keyboard.press('Tab');
    log('B town tabs:', r.join(' | '), '| Tab from tab list ->', await focusInfo(p));
    // Each tab panel: its labelling and whether hidden ones are out of the tab order.
    log('  panels:', await p.evaluate(() => [...document.querySelectorAll('[role=tabpanel]')].map(e => `${e.id} labelledby=${e.getAttribute('aria-labelledby')} hidden=${e.hidden}`).join('; ')));
    await ctx.close(); }
  // C. The seating chart.
  { const [ctx, p] = await page(b, '/officials');
    await p.click('#tab-legislators'); await p.waitForTimeout(500);
    const seat = await p.$('#tab-seat');
    if (seat) { await seat.click(); await p.waitForTimeout(800); }
    await p.focus('#tab-seat').catch(() => {});
    const seq = []; for (let i = 0; i < 40; i++) { await p.keyboard.press('Tab'); seq.push(await focusInfo(p)); }
    log('C seat chart present:', !!seat, '| 40 tabs from its tab:', [...new Set(seq)].length, 'distinct;', seq.slice(0, 14).join(' > '));
    const seats = await p.evaluate(() => { const pane = document.getElementById('pane-seat'); if (!pane) return 'no pane';
      const f = pane.querySelectorAll('a,button,[tabindex]:not([tabindex="-1"])'); const s = pane.querySelectorAll('svg *[aria-label], svg a, svg [role]');
      return `${f.length} focusable in the pane, ${s.length} labelled svg parts; svg role=${pane.querySelector('svg')?.getAttribute('role')} label=${pane.querySelector('svg')?.getAttribute('aria-label')}`; });
    log('  ', seats);
    await watchLive(p);
    const firstSeat = await p.$('#pane-seat button, #pane-seat a, #pane-seat [tabindex="0"]');
    if (firstSeat) { await firstSeat.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(400); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(300); }
    log('   seat note said:', (await liveSaid(p)).join(' | ') || 'nothing', '| focus', await focusInfo(p));
    await p.screenshot({ path: SH + 'seat-1280-focus.png' });
    await ctx.close(); }
  // D. The district map on Officials: how many Tab stops to get past it, and do arrows move it.
  { const [ctx, p] = await page(b, '/officials');
    await p.focus('#lq');
    let n = 0, inMap = 0, first = '', after = '';
    for (; n < 400; n++) { await p.keyboard.press('Tab');
      const w = await p.evaluate(() => { const e = document.activeElement; const g = e.closest('[role=group]'); return { inMap: !!(g && /map/i.test(g.getAttribute('aria-label') || '')) || !!e.closest('svg'), d: e.tagName + ' ' + (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30) }; });
      if (w.inMap) { inMap++; if (!first) first = w.d; } else if (inMap) { after = w.d; break; } }
    log('D map: Tab stops inside the map =', inMap, '| first', first, '| first after the map:', after);
    // Whether the keys move it: compare the drawing before and after (its transform lives on an inner element).
    const grp = await p.$('[role=group][aria-label*="map" i]');
    if (grp) { await grp.focus(); const before = await grp.screenshot();
      for (let i = 0; i < 6; i++) await p.keyboard.press('ArrowRight');
      await p.keyboard.press('+'); await p.waitForTimeout(700);
      log('   group tabIndex:', await grp.evaluate(e => e.tabIndex), '| arrows and + moved it:', !before.equals(await grp.screenshot()), '| label:', await grp.getAttribute('aria-label')); }
    await ctx.close(); }
  // E. Follow on a legislator and a committee page; Testify on a bill that has one.
  for (const path of ['/legislator/joe-alexander-hills-29', '/committee/H64', '/bill/2026/hb1083', '/bill/2026/hb1681']) {
    const [ctx, p] = await page(b, path);
    const found = await p.evaluate(() => [...document.querySelectorAll('summary,button')].filter(e => /follow|testify/i.test(e.textContent)).map(e => `${e.tagName.toLowerCase()} "${e.textContent.trim().replace(/\s+/g, ' ').slice(0, 60)}"`));
    log('E', path, 'Follow/Testify:', found.join(' ; ') || 'none');
    for (const word of ['Follow', 'Testify']) {
      const s = await p.$(`summary:has-text("${word}")`); if (!s) continue;
      await s.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
      const open = await s.evaluate(e => e.parentElement.open);
      const fields = await s.evaluate(e => [...e.parentElement.querySelectorAll('input,select,textarea,button')].map(f => {
        const id = f.id; const lab = (id && document.querySelector(`label[for="${id}"]`)) || f.closest('label');
        return `${f.tagName.toLowerCase()}[${f.type || ''}] name="${(f.getAttribute('aria-label') || (lab && lab.textContent) || f.placeholder || f.textContent || '').trim().slice(0, 30)}"`; }));
      const seq = []; for (let i = 0; i < 6; i++) { await p.keyboard.press('Tab'); seq.push(await focusInfo(p)); }
      await s.focus(); await p.keyboard.press('Escape'); await p.waitForTimeout(200);
      log(`   ${word}: opens with Enter=${open}; fields: ${fields.join(', ')}; then Tab: ${seq.join(' > ')}; open after Escape=${await s.evaluate(e => e.parentElement.open)}`);
      await p.screenshot({ path: SH + `${word.toLowerCase()}-${path.split('/').pop()}.png` });
    }
    await ctx.close();
  }
  // F. Live regions: do they announce?
  const cases = [
    ['/', '#findq', 'goffs', 'header search'],
    ['/', '#hq', 'education', 'home search', 'Enter'],
    ['/search', '#resq', 'goffstown', 'search page'],
    ['/bills', '#q', 'education', 'bill search', 'Enter'],
    ['/officials', '#lq', 'Goffstown', 'officials finder'],
  ];
  for (const [path, sel, text, what, key] of cases) {
    const [ctx, p] = await page(b, path);
    await watchLive(p);
    const el = await p.$(sel);
    if (!el) { log('F', what, sel, 'missing'); await ctx.close(); continue; }
    if (!(await el.isVisible())) { await p.click('#findbtn').catch(() => {}); await p.waitForTimeout(300); }
    await p.fill(sel, ''); await p.type(sel, text, { delay: 60 }); if (key) await p.keyboard.press(key);
    await p.waitForTimeout(1800);
    const said = await liveSaid(p);
    const results = await p.evaluate(() => document.body.innerText.length);
    log(`F ${what} (${path} ${sel} "${text}"): live regions said -> ${said.length ? said.slice(-3).join(' | ') : 'NOTHING'}`);
    await ctx.close();
  }
  // G. Forced colours: what focus looks like on the inputs and tabs.
  { const [ctx, p] = await page(b, '/', 1280, { forcedColors: 'active' });
    await p.focus('#hq'); await p.waitForTimeout(200);
    await (await p.$('#hq')).screenshot({ path: SH + 'forced-hq-focus.png' });
    const st = await p.$eval('#hq', e => { const c = getComputedStyle(e); return `outline ${c.outlineStyle} ${c.outlineWidth} ${c.outlineColor}; shadow ${c.boxShadow}; border ${c.borderColor}`; });
    log('G forced, #hq focused:', st);
    await ctx.close(); }
  await b.close();
})();
