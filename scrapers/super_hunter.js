const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');
const CITY_FILE = path.join(__dirname, '..', 'target_cities.txt');
const OUTPUT_PATH = path.join(require('os').homedir(), 'Desktop', 'leads_to_approve.csv');

(async () => {
  // 1. Load your cities from the text file
  const cities = fs.readFileSync(CITY_FILE, 'utf8').trim();
  console.log(`🚀 Starting Super Hunter for: ${cities}`);

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    await page.goto('https://ntreis.clareityiam.net/idp/login');
    const [matrixPage] = await Promise.all([
      context.waitForEvent('page'),
      page.locator('div, span, a').filter({ hasText: /^Matrix$/ }).first().click(),
    ]);
    await matrixPage.waitForLoadState('networkidle');

    // 2. Loop through both Canceled and Expired
    const categories = ["Expired", "Canceled"];
    let allLeads = [];

    for (let cat of categories) {
      console.log(`🔎 Checking ${cat} row...`);
      await matrixPage.locator('a').filter({ hasText: "Home" }).first().click();
      await matrixPage.waitForTimeout(2000);
      
      const link = matrixPage.locator('a').filter({ hasText: new RegExp(`^${cat}`, 'i') }).first();
      await link.click();

      // 3. Apply the 7-city filter
      await matrixPage.locator('a').filter({ hasText: /^Criteria$/ }).first().click();
      await matrixPage.waitForTimeout(2000);
      await matrixPage.locator('input[name*="city"], input[id*="city"]').first().fill(cities);
      await matrixPage.keyboard.press('Enter');
      
      await matrixPage.waitForTimeout(3000);

      // 4. Extract the data
      const results = await matrixPage.evaluate((catName) => {
        const rows = Array.from(document.querySelectorAll('tr.d-table-row'));
        return rows.map(row => {
          const cells = row.querySelectorAll('td');
          return { status: catName, address: cells[3]?.innerText, city: cells[4]?.innerText, dom: cells[10]?.innerText };
        });
      }, cat);
      
      allLeads = [...allLeads, ...results];
    }

    // 5. Save the final "Drop-off" file
    const csv = "Status,Address,City,DOM\n" + allLeads.map(l => `"${l.status}","${l.address}","${l.city}","${l.dom}"`).join("\n");
    fs.writeFileSync(OUTPUT_PATH, csv);
    console.log(`🎉 Found ${allLeads.length} total properties! Check your Desktop.`);

    await browser.close();
  } catch (err) {
    console.error("Error:", err.message);
  }
})();