const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');
const CITY_FILE = path.join(__dirname, '..', 'target_cities.txt');

(async () => {
  const cities = fs.readFileSync(CITY_FILE, 'utf8').trim();
  console.log(`🚀 Starting Super Auditor for: ${cities}`);

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    const categories = ["Expired", "Canceled"];
    
    for (const cat of categories) {
      console.log(`🔎 Hunting for ${cat} listings...`);
      await page.goto('https://ntrdd.mlsmatrix.com/Matrix/Default.aspx');
      
      // 1. Click the specific count (e.g., "Expired (44)")
      const countLink = page.locator('a').filter({ hasText: new RegExp(`${cat} \\(\\d+\\)`, 'i') }).first();
      await countLink.click();

      // 2. Open Criteria and apply cities
      console.log(`   📍 Filtering cities in ${cat}...`);
      await page.locator('a').filter({ hasText: 'Criteria' }).click();
      await page.waitForTimeout(1000);
      await page.locator('input[name*="city"]').first().fill(cities);
      await page.keyboard.press('Enter');
      await page.waitForTimeout(2000);

      // 3. Get the list of MLS Numbers
      const mlsLinks = await page.locator('a[href*="InLineReport"]').all();
      console.log(`   📈 Found ${mlsLinks.length} listings to audit.`);

      // 4. Audit each listing (The Photo Check)
      for (let i = 0; i < Math.min(mlsLinks.length, 5); i++) { // Testing first 5
          await mlsLinks[i].click();
          await page.waitForTimeout(2000);
          
          // Scrape Photo Count (e.g., "1 / 39")
          const photoText = await page.locator('.v-photo-count, .photo-count-text').first().innerText().catch(() => "0 / 0");
          const totalPhotos = parseInt(photoText.split('/')[1]) || 0;
          const address = await page.locator('div.d-fontSize14.d-fontWeightBold').first().innerText().catch(() => "Unknown");

          if (totalPhotos < 30) {
              console.log(`      🚩 FLAG: ${address} only has ${totalPhotos} photos.`);
          } else {
              console.log(`      ✅ PASS: ${address} has ${totalPhotos} photos.`);
          }
          
          await page.locator('a').filter({ hasText: 'Results' }).click();
          await page.waitForTimeout(1000);
      }
    }

    console.log("🎉 Audit Complete!");
    await browser.close();
  } catch (err) {
    console.error("Audit Error: ", err.message);
  }
})();