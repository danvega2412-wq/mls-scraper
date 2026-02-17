const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const AUTH_FILE = path.join(__dirname, '..', 'config', 'auth.json');
(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_FILE });
  const page = await context.newPage();
  console.log('Going to Market Watch...');
  await page.goto('https://matrix.ntreis.net/Matrix/Search/MarketWatch');
  await page.waitForTimeout(3000);
  console.log('Clicking Expired...');
  await page.locator('a:has-text("Expired")').first().click();
  console.log('Waiting 10 seconds for page to fully load...');
  await page.waitForTimeout(10000);
  console.log('\nChecking for different table selectors:');
  const selectors = [
    'tr.d-even',
    'tr.d-odd',
    'table tr',
    'tbody tr',
    '.d-results tr',
    'tr[class*="d-"]'
  ];
  for (const sel of selectors) {
    const count = await page.locator(sel).count();
    console.log('  ' + sel + ': ' + count + ' elements');
  }
  console.log('\nGetting text from City column (if visible):');
  const cityTexts = await page.locator('td').filter({ hasText: /Flower Mound|Southlake|Grapevine|Colleyville/ }).allInnerTexts();
  console.log('  Found cities:', cityTexts);
  console.log('\nBrowser will stay open for 30 seconds so you can inspect...');
  await page.waitForTimeout(30000);
  await browser.close();
})();
