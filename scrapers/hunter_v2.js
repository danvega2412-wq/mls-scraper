const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');
const CITY_FILE = path.join(__dirname, '..', 'target_cities.txt');
const OUTPUT_PATH = path.join(require('os').homedir(), 'Desktop', 'leads_to_approve.csv');

(async () => {
  const cities = fs.readFileSync(CITY_FILE, 'utf8').trim();
  console.log(`🚀 Starting Hunter V2 for: ${cities}`);

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    console.log("1. Opening Matrix...");
    await page.goto('https://ntrdd.mlsmatrix.com/Matrix/Default.aspx'); 

    // Look for the Expired link directly on the dashboard
    console.log("2. Hunting for Expired Link...");
    const expiredLink = page.locator('a').filter({ hasText: /Expired \(\d+\)/ }).first();
    
    // If we can't see it, try to find the 'Market Watch' section
    await expiredLink.waitFor({ state: 'visible', timeout: 10000 });
    await expiredLink.click();

    console.log("3. Applying City Filters...");
    await page.locator('a').filter({ hasText: 'Criteria' }).click();
    await page.waitForTimeout(2000);
    
    // Fill the cities from your text file
    await page.locator('input[name*="city"]').first().fill(cities);
    await page.keyboard.press('Enter');

    console.log("🎉 Filter Applied! Creating your lead list...");
    // ... Extraction logic ...
    
    await browser.close();
  } catch (err) {
    console.error("Stopping: ", err.message);
  }
})();