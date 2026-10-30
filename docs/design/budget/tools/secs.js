const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();
for (const [w,theme] of [[1280,'light'],[390,'dark']]){
const p=await b.newPage({viewport:{width:w,height:900},colorScheme:theme});
await p.goto(process.argv[2],{waitUntil:'networkidle'});
await p.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
for (const id of ['s-where-it-goes','s-the-capital-budget','s-compared-with-the-last-budget','s-now-under-way-the-2028-2029-budget']){
 await p.locator('#'+id).screenshot({path:`${process.argv[3]}/sec-${w}-${id}.png`});}
await p.close();}
await b.close();})();
