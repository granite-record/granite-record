// GRANITE_VERSION: 2026-10-30.1
// node shoot.js BASE_URL OUT_DIR page1 [page2 ...]
// Screenshots each page at 390 and 1280 wide, light and dark, full page.
const { chromium } = require('playwright');
const [base, out, ...pages] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  for (const p of pages) {
    for (const width of [390, 1280]) {
      for (const scheme of ['light', 'dark']) {
        const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, deviceScaleFactor: 1 });
        const page = await ctx.newPage();
        await page.goto(`${base}/${p}`, { waitUntil: 'networkidle' }).catch(() => {});
        await page.waitForTimeout(500);
        const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        const name = `${out}/${p.replace(/\.html$/, '')}-${width}-${scheme}.png`;
        await page.screenshot({ path: name, fullPage: true });
        console.log(name, 'horizontal overflow px:', over);
        await ctx.close();
      }
    }
  }
  await browser.close();
})();
