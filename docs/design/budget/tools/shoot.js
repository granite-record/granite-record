// Scratch: full-page screenshots of pages on the local server.
// node shoot.js BASEURL OUTDIR name=path [name=path ...]
const { chromium } = require('playwright');
const [base, outDir, ...pages] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  for (const spec of pages) {
    const [name, path] = spec.split('=');
    for (const width of [390, 1280]) {
      for (const theme of ['light', 'dark']) {
        const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, deviceScaleFactor: 1 });
        const page = await ctx.newPage();
        const errs = [];
        page.on('pageerror', e => errs.push(String(e)));
        await page.goto(base + path, { waitUntil: 'networkidle' });
        await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
        await page.waitForTimeout(300);
        const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        const file = `${outDir}/${name}-${width}-${theme}.png`;
        await page.screenshot({ path: file, fullPage: true });
        console.log(file, 'horizontal overflow px:', over, errs.length ? 'errors: ' + errs.join(' | ') : '');
        await ctx.close();
      }
    }
  }
  await browser.close();
})();
