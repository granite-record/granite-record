// Open a page of the dry-run preview (the site as dev stands) in Chromium and report on it.
//   node site.cjs page /path [--width 1280] [--shot out.png] [--full]   -> JSON summary
//   node site.cjs text /path [--width 1280]                              -> the page's visible text
//   node site.cjs links /path                                            -> every link: text -> href
//   node site.cjs eval /path "js expression returning JSON-able"         -> run JS in the page
// Run with: NODE_USE_ENV_PROXY=1 NODE_PATH=$(npm root -g) node /tmp/claude-0/audit/site.cjs ...
// Use final paths: no trailing slash, no .html (a redirect escapes the route).
// As a module: const {open} = require('/tmp/claude-0/audit/site.cjs'); const {b, p, status} = await open('/x', 1280);
const { chromium } = require('playwright');
const B = 'https://dry-run.graniterecord.pages.dev';
async function routed(ctx) {
  await ctx.route('**/*', async route => {
    const u = route.request().url();
    if (!/^https:\/\/(dry-run\.graniterecord\.pages\.dev|fonts\.(googleapis|gstatic)\.com)\//.test(u)) return route.abort();
    try {
      const r = await fetch(u, { redirect: 'manual' });
      if (r.status >= 300 && r.status < 400)
        return route.fulfill({ status: r.status, headers: { location: new URL(r.headers.get('location'), u).href } });
      return route.fulfill({ status: r.status, headers: { 'content-type': r.headers.get('content-type') || '' }, body: Buffer.from(await r.arrayBuffer()) });
    } catch (e) { return route.abort(); }
  });
}
async function open(path, width = 1280, scheme = 'light') {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const ctx = await b.newContext({ viewport: { width, height: 900 }, colorScheme: scheme });
  await routed(ctx);
  const p = await ctx.newPage(); const errors = [];
  p.on('pageerror', e => errors.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
  const r = await p.goto(B + path, { waitUntil: 'load', timeout: 90000 });
  await p.waitForTimeout(1200);
  return { b, p, status: r ? r.status() : 0, errors };
}
module.exports = { open, routed, B };
if (require.main === module) (async () => {
  const [cmd, path, ...rest] = process.argv.slice(2);
  const opt = k => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : null; };
  const width = +(opt('--width') || 1280);
  const { b, p, status, errors } = await open(path, width, opt('--scheme') || 'light');
  if (cmd === 'page') {
    const info = await p.evaluate(() => {
      const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const main = document.querySelector('main') || document.body;
      const words = (main.innerText || '').split(/\s+/).filter(Boolean).length;
      const heads = [...document.querySelectorAll('h1,h2,h3,h4')].filter(vis).map(h => h.tagName + ' ' + h.textContent.trim().replace(/\s+/g, ' ').slice(0, 90));
      const nav = [...document.querySelectorAll('header a, nav a')].filter(vis).map(a => a.textContent.trim().replace(/\s+/g, ' ') + ' -> ' + a.getAttribute('href')).slice(0, 40);
      const tabs = [...document.querySelectorAll('[role=tab]')].map(t => t.textContent.trim());
      return { title: document.title, description: (document.querySelector('meta[name=description]') || {}).content,
        lang: document.documentElement.lang, words, headings: heads.slice(0, 60), nav, tabs,
        links: document.querySelectorAll('a').length, buttons: document.querySelectorAll('button').length,
        details: document.querySelectorAll('details').length, svgs: document.querySelectorAll('svg').length, imgs: document.querySelectorAll('img').length,
        overflowX: document.documentElement.scrollWidth > window.innerWidth + 1, scrollHeight: document.documentElement.scrollHeight };
    });
    console.log(JSON.stringify({ path, width, status, url: p.url(), errors, ...info }, null, 1));
    if (opt('--shot')) await p.screenshot({ path: opt('--shot'), fullPage: rest.includes('--full') });
  } else if (cmd === 'text') {
    console.log(await p.evaluate(() => (document.querySelector('main') || document.body).innerText));
  } else if (cmd === 'links') {
    const ls = await p.evaluate(() => [...document.querySelectorAll('a')].map(a => a.textContent.trim().replace(/\s+/g, ' ').slice(0, 80) + ' -> ' + a.getAttribute('href')));
    console.log(ls.join('\n'));
  } else if (cmd === 'eval') {
    console.log(JSON.stringify(await p.evaluate(rest[0]), null, 1));
  }
  if (errors.length && cmd !== 'page') console.error('ERRORS: ' + errors.join(' | '));
  await b.close();
})().catch(e => { console.error('FAILED: ' + e.message); process.exit(1); });
