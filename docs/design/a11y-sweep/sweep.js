// Read-only accessibility sweep of the dry-run preview (README.md). Writes results/sweep.json and shots/run/.
const { chromium } = require('playwright');
const fs = require('fs');
const AXE = fs.readFileSync(__dirname + '/node_modules/axe-core/axe.min.js', 'utf8');
const BASE = (process.env.A11Y_BASE || 'https://dry-run.graniterecord.pages.dev');
const OUT = __dirname;
fs.mkdirSync(OUT + '/shots/run', { recursive: true }); fs.mkdirSync(OUT + '/results', { recursive: true });

const PAGES = [
  ['home', '/'],
  ['bill', '/bill/2026/hb1681'],
  ['legislator', '/legislator/joe-alexander-hills-29'],
  ['committee', '/committee/H64'],
  ['session-day', '/session/H/2026-02-19'],
  ['town-representatives', '/town/goffstown'],
  ['town-map', '/town/goffstown', ['#tab-map']],
  ['town-officials', '/town/goffstown', ['#tab-officials']],
  ['town-vote', '/town/goffstown', ['#tab-vote']],
  ['town-services', '/town/goffstown', ['#tab-services']],
  ['officials', '/officials'],
  ['officials-seat', '/officials', ['#tab-legislators', '#tab-seat']],
  ['calendar', '/calendar'],
  ['laws', '/laws'],
  ['laws-chapter', '/laws/659'],
  ['bills', '/bills'],
  ['search', '/search'],
  ['guide-how-to-vote', '/guides/how-to-vote'],
  ['guide-medicare', '/guides/medicare-and-social-security'],
  ['guide-renew-license', '/guides/renew-drivers-license'],
  ['learn-bill-law', '/learn/how-a-bill-becomes-law'],
  ['learn-general-court', '/learn/general-court'],
];
const only = process.argv[2] ? process.argv[2].split(',') : null;
const VIEWS = [];
for (const w of [390, 1280]) for (const m of ['light', 'dark', 'forced', 'text24']) VIEWS.push([w, m]);

async function open(b, w, m, path, steps) {
  const ctx = await b.newContext({
    viewport: { width: w, height: w < 600 ? 844 : 900 }, isMobile: w < 600, hasTouch: w < 600,
    colorScheme: m === 'dark' ? 'dark' : 'light', forcedColors: m === 'forced' ? 'active' : 'none',
  });
  const p = await ctx.newPage();
  if (m === 'text24') {
    const cdp = await ctx.newCDPSession(p);
    await cdp.send('Page.enable');
    await cdp.send('Page.setFontSizes', { fontSizes: { standard: 24, fixed: 20 } });
  }
  await p.goto(BASE + path, { waitUntil: path.startsWith('/laws/') ? 'load' : 'networkidle', timeout: 90000 }); if (path.startsWith('/laws/')) await p.waitForTimeout(3000);
  for (const s of steps || []) { await p.click(s); await p.waitForTimeout(600); }
  await p.waitForTimeout(400);
  return { ctx, p };
}

const MEASURE = () => {
  const vw = document.documentElement.clientWidth;
  const out = { sideways: document.documentElement.scrollWidth - vw, rootPx: parseFloat(getComputedStyle(document.documentElement).fontSize) };
  const vis = e => { const r = e.getBoundingClientRect(); const c = getComputedStyle(e); return r.width > 0 && r.height > 0 && c.visibility !== 'hidden' && c.display !== 'none'; };
  // Elements sticking out past the right edge (not inside a scroller).
  const inScroller = e => { for (let a = e.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return a !== document.documentElement && a !== document.body; } return false; };
  out.pastEdge = [...document.querySelectorAll('body *')].filter(e => vis(e) && e.getBoundingClientRect().right > vw + 1 && !inScroller(e) && e.children.length === 0)
    .slice(0, 6).map(e => `${e.tagName.toLowerCase()}${e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''} "${(e.textContent || '').trim().slice(0, 40)}" right=${Math.round(e.getBoundingClientRect().right)}`);
  // Text cut off: a box with hidden overflow whose text is wider or taller than it.
  out.clipped = [...document.querySelectorAll('body *')].filter(e => {
    if (!vis(e) || !e.textContent.trim()) return false;
    const c = getComputedStyle(e);
    const hid = c.overflowX === 'hidden' || c.overflowY === 'hidden' || c.overflow === 'clip';
    return hid && (e.scrollWidth > e.clientWidth + 2 || e.scrollHeight > e.clientHeight + 2) && c.textOverflow !== 'ellipsis' && e.clientHeight > 0;
  }).slice(0, 6).map(e => `${e.tagName.toLowerCase()}${typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : ''} "${e.textContent.trim().slice(0, 40)}" ${e.scrollWidth}x${e.scrollHeight} in ${e.clientWidth}x${e.clientHeight}`);
  // Headings in order.
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role=heading]')].filter(vis);
  const lv = hs.map(h => +(h.getAttribute('aria-level') || h.tagName[1]));
  out.h1 = lv.filter(l => l === 1).length;
  out.skips = [];
  for (let i = 1; i < lv.length; i++) if (lv[i] > lv[i - 1] + 1) out.skips.push(`h${lv[i - 1]} "${hs[i - 1].textContent.trim().slice(0, 30)}" -> h${lv[i]} "${hs[i].textContent.trim().slice(0, 30)}"`);
  if (lv.length && lv[0] !== 1) out.skips.unshift(`first heading is h${lv[0]}`);
  out.live = [...document.querySelectorAll('[aria-live],[role=status],[role=alert],[role=log]')].map(e => `${e.tagName.toLowerCase()}#${e.id}[${e.getAttribute('aria-live') || e.getAttribute('role')}] "${e.textContent.trim().slice(0, 40)}"`);
  return out;
};

async function axe(p) {
  await p.addScriptTag({ content: AXE });
  return await p.evaluate(async () => {
    const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] }, resultTypes: ['violations'] });
    return r.violations.map(v => ({ id: v.id, impact: v.impact, tags: v.tags.filter(t => /^wcag\d/.test(t)), help: v.help, n: v.nodes.length,
      eg: v.nodes.slice(0, 4).map(n => ({ t: n.target.join(' '), h: n.html.slice(0, 140), s: (n.any[0] || n.all[0] || n.none[0] || {}).message })) }));
  });
}

async function keyboard(p, forced) {
  return await p.evaluate(() => 0).then(async () => {
    const seen = []; let same = 0, last = null;
    for (let i = 0; i < 120; i++) {
      await p.keyboard.press('Tab');
      const f = await p.evaluate((forced) => {
        const e = document.activeElement;
        if (!e || e === document.body) return null;
        const c = getComputedStyle(e);
        const ring = (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0) || (!forced && c.boxShadow !== 'none');
        // A ring drawn on a child or ::after counts too: check the element's first child.
        const kid = e.firstElementChild && getComputedStyle(e.firstElementChild);
        const kidRing = kid && ((kid.outlineStyle !== 'none' && parseFloat(kid.outlineWidth) > 0) || (!forced && kid.boxShadow !== 'none'));
        const r = e.getBoundingClientRect();
        const cx = r.left + Math.min(r.width / 2, 10), cy = r.top + Math.min(r.height / 2, 10);
        const top = document.elementFromPoint(cx, cy);
        const covered = r.height > 0 && cy >= 0 && cy <= innerHeight && top && !(e === top || e.contains(top) || top.contains(e));
        const off = r.bottom < 0 || r.top > innerHeight || r.width === 0;
        const label = (e.getAttribute('aria-label') || e.textContent || e.value || e.id || '').trim().replace(/\s+/g, ' ').slice(0, 40);
        const path = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '');
        return { path, label, ring: ring || !!kidRing, covered: !!covered, coveredBy: covered ? top.tagName.toLowerCase() + (typeof top.className === 'string' ? '.' + top.className.split(' ')[0] : '') : '', off, key: path + '|' + label + '|' + Math.round(r.top + scrollY) };
      }, forced);
      if (!f) { if (seen.length) break; else continue; }
      if (last && f.key === last) { if (++same >= 3) { seen.push({ ...f, trap: 'focus did not move' }); break; } } else same = 0;
      last = f.key;
      if (seen.length > 3 && seen.slice(0, -1).some(s => s.key === f.key) && seen.filter(s => s.key === f.key).length >= 2) { seen.push({ ...f, trap: 'focus cycled' }); break; }
      seen.push(f);
    }
    return seen;
  });
}

(async () => {
  const b = await chromium.launch();
  const report = [];
  for (const [name, path, steps] of PAGES) {
    if (only && !only.includes(name)) continue;
    for (const [w, m] of VIEWS) {
      const id = `${name}_${w}_${m}`;
      try {
        const { ctx, p } = await open(b, w, m, path, steps);
        const r = { id, page: name, path, w, m, ...(await p.evaluate(MEASURE)) };
        if (m === 'light' || m === 'dark') r.axe = await axe(p);
        if (m === 'text24' && w === 390) r.axe = (await axe(p)).filter(v => v.id === 'target-size');
        if (w === 1280 && (m === 'light' || m === 'forced')) r.keys = await keyboard(p, m === 'forced');
        await p.screenshot({ path: `${OUT}/shots/run/${id}.png`, fullPage: false });
        report.push(r);
        console.log(id, 'sideways', r.sideways, 'axe', (r.axe || []).map(v => v.id + ':' + v.n).join(' '), r.keys ? 'keys ' + r.keys.length + ' noring ' + r.keys.filter(k => !k.ring).length : '');
        await ctx.close();
      } catch (e) { console.log(id, 'ERROR', e.message.split('\n')[0]); report.push({ id, error: e.message.split('\n')[0] }); }
    }
    fs.writeFileSync(OUT + '/results/sweep.json', JSON.stringify(report, null, 1));
  }
  await b.close();
})();
