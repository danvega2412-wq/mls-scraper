const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  console.log("Launching browser...");
  const browser = await chromium.launch({ headless: false }); 
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log("Opening NTREIS... PLEASE LOG IN NOW.");
    await page.goto('https://ntreis.clareityiam.net/idp/login');

    // Forces the window to stay open for 3 minutes so you can log in
    console.log("Waiting 3 minutes for you to reach the Matrix Dashboard...");
    await page.waitForTimeout(180000); 

    if (!fs.existsSync('config')) { fs.mkdirSync('config'); }
    const storage = await context.storageState();
    fs.writeFileSync('config/auth.json', JSON.stringify(storage));
    
    console.log("SUCCESS: Login session saved to config/auth.json!");
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await browser.close();
  }
})();