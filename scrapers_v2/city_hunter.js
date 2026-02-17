const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const CITIES_FILE = path.join(__dirname, '..', 'cities_final.txt');
const AUTH_FILE = path.join(__dirname, '..', 'config', 'auth.json');
const cities = fs.readFileSync(CITIES_FILE, 'utf8').split(',').map(c => c.trim().toUpperCase()).filter(Boolean);
console.log('Target cities:', cities);
function cityInText(text, targetCities) {
  const upper = text.toUpperCase();
  for (const city of targetCities) {
    if (upper.includes(city)) return city;
  }
  return null;
}
(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_FILE });
  const page = await context.newPage();
  await page.goto('https://matrix.ntreis.net/Matrix/Search/MarketWatch');
  await page.waitForTimeout(3000);
  for (const listingType of ['Expired', 'Canceled']) {
    console.log('\n=== ' + listingType + ' ===');
    await page.locator('a:has-text("' + listingType + '")').first().click();
    await page.waitForTimeout(8000);
    let pageNum = 1;
    while (pageNum <= 5) {
      console.log('Page ' + pageNum + ':');
      const allCityElements = await page.locator('td').filter({ hasText: /Grapevine|Colleyville|Southlake|Euless|Bedford|Hurst|Flower Mound/i }).all();
      console.log('  Found ' + allCityElements.length + ' matching city cells');
      for (let i = 0; i < allCityElements.length; i++) {
        const cityText = await allCityElements[i].innerText();
        console.log('  MATCH #' + (i + 1) + ': ' + cityText.trim());
      }
      const nextBtn = page.locator('a.d-paginationItem:has-text("Next")');
      if (await nextBtn.count() === 0) {
        console.log('  Last page');
        break;
      }
      await nextBtn.click();
      await page.waitForTimeout(8000);
      pageNum++;
    }
    await page.goto('https://matrix.ntreis.net/Matrix/Search/MarketWatch');
    await page.waitForTimeout(3000);
  }
  console.log('\nComplete!');
  await browser.close();
})();
