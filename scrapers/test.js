const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false }); 
  const page = await browser.newPage();
  console.log("If you see this, the terminal is working!");
  await page.goto('https://www.google.com');
  await page.screenshot({ path: 'photos/it_works.png' });
  console.log("Success! Closing in 3 seconds.");
  await new Promise(r => setTimeout(r, 3000)); 
  await browser.close();
})();const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  // 1. Launch a visible browser window
  const browser = await chromium.launch({ headless: false }); 
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log("Opening Netris... PLEASE LOG IN NOW.");
  await page.goto('https://ntris.clareity.net/idp/login');

  // 2. This keeps the window open for 120 seconds so you can log in
  console.log("Waiting 2 minutes for you to reach the Matrix Dashboard...");
  await page.waitForTimeout(120000); 

  // 3. This saves your "Secret Handshake" (session cookies) to a file
  const storage = await context.storageState();
  
  // Create a config folder if it doesn't exist
  if (!fs.existsSync('config')) { fs.mkdirSync('config'); }
  fs.writeFileSync('config/auth.json', JSON.stringify(storage));
  
  console.log("SUCCESS: Login session saved to config/auth.json!");
  await browser.close();
})();