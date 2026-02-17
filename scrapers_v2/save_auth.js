const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  console.log('--- ACTION REQUIRED ---');
  console.log('1. Log into Matrix manually in the browser window that just opened.');
  console.log('2. Once you are looking at the Dashboard, come back here and press Enter.');
  
  await page.goto('https://ntrdd.mlsmatrix.com/Matrix/Default.aspx');

  process.stdin.resume();
  process.stdin.once('data', async () => {
    const authPath = path.join(__dirname, '..', 'config', 'auth.json');
    await context.storageState({ path: authPath });
    console.log(`✅ Success! Auth saved to ${authPath}`);
    await browser.close();
    process.exit();
  });
})();
