const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Point to your saved login file
const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');

(async () => {
  console.log("🚀 Starting the 'Real Deal' script...");

  // 1. Launch Browser
  const browser = await chromium.launch({ headless: false });
  // Load your saved login so you don't have to type passwords
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    console.log("1. Going to NTREIS Dashboard...");
    await page.goto('https://ntreis.clareityiam.net/idp/login');

    // 2. Click Matrix and CATCH the new tab
    console.log("2. Clicking 'Matrix' and waiting for the new tab...");
    const matrixButton = page.locator('div, span, button, a').filter({ hasText: /^Matrix$/ }).first();
    
    // This magic block waits for the new window to pop up
    const [matrixPage] = await Promise.all([
      context.waitForEvent('page'), // Wait for new tab
      matrixButton.click(),         // Click the button
    ]);

    // Now we switch our "eyes" to the new tab
    await matrixPage.waitForLoadState('domcontentloaded');
    console.log("✅ Switched to Matrix Tab!");

    // 3. Handle 'Rental Beast' or 'Welcome' Popups (The annoying overlay)
    console.log("3. Checking for popups...");
    await matrixPage.waitForTimeout(3000); // Give popups a second to appear
    const frames = matrixPage.frames();
    
    for (const frame of frames) {
        // Look for a close button inside any frame
        const closeBtn = frame.locator('button, a, span').filter({ hasText: /Close|No Thanks|Later/i }).first();
        if (await closeBtn.isVisible()) {
            console.log("   - Found a popup. Closing it...");
            await closeBtn.click();
            await matrixPage.waitForTimeout(1000);
        }
    }

    // 4. Find 'Market Watch' and click 'Expired'
    console.log("4. Hunting for 'Expired' in Market Watch...");
    let foundIt = false;

    // Scan all frames again because Market Watch is often inside one
    for (const frame of matrixPage.frames()) {
        // Find the row that actually says "Expired"
        const expiredRow = frame.locator('tr').filter({ hasText: /^Expired/ }).first();
        
        if (await expiredRow.isVisible()) {
            console.log("   - Found the Expired row!");
            
            // Find the number link inside that row (e.g., the "44")
            const numberLink = expiredRow.locator('a').first();
            const count = await numberLink.innerText();
            
            console.log(`   - Clicking Expired count: ${count}`);
            await numberLink.click();
            foundIt = true;
            break; // Stop looking, we found it
        }
    }

    if (foundIt) {
        console.log("🎉 SUCCESS! You should now see the Expired listings.");
        console.log("   - I will leave the browser open so you can verify.");
        // Keep browser open for you to see
        await new Promise(() => {}); 
    } else {
        console.log("❌ ERROR: Could not find the 'Expired' row. Please check the screen.");
    }

  } catch (err) {
    console.error("Critical Error:", err);
  }
})();