const { chromium } = require('playwright');
const path = require('path');
const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');

(async () => {
  console.log("🚀 Launching Hunter V1...");
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    console.log("1. Opening Dashboard...");
    await page.goto('https://ntreis.clareityiam.net/idp/login');

    console.log("2. Waiting for Matrix Tab...");
    const [matrixPage] = await Promise.all([
      context.waitForEvent('page'),
      page.locator('div, span, a').filter({ hasText: /^Matrix$/ }).first().click(),
    ]);

    // This ensures the Matrix page is actually ready before we look for the widget
    await matrixPage.waitForLoadState('networkidle');
    console.log("✅ Inside Matrix. Looking for 'Expired'...");

    // 3. Clear the popup if it exists
    const closePopup = matrixPage.locator('button:has-text("Close"), .modal-close').first();
    if (await closePopup.isVisible()) {
        await closePopup.click();
    }

    // 4. Click 'Expired' directly based on your screenshot
    // Using a 'regex' search to find "Expired" even if the number (44) changes
    const expiredLink = matrixPage.locator('a').filter({ hasText: /^Expired/i }).first();
    
    await expiredLink.waitFor({ state: 'visible', timeout: 15000 });
    const fullText = await expiredLink.innerText();
    
    console.log(`🎯 Found link: "${fullText}". Clicking now...`);
    await expiredLink.click();

    console.log("🎉 Success! You should see the Results Table now.");
    
    // This keeps the browser open so you can see it work
    await new Promise(() => {});

  } catch (err) {
    console.error("Stopping due to error:", err.message);
  }
})();