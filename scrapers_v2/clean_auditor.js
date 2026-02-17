const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const C_FILE = path.join(__dirname, '..', 'cities_clean.txt');
const OUT = path.join(__dirname, '..', 'audit_results.csv');
(async () => {
const cities = fs.readFileSync(C_FILE, 'utf8').split(',').map(c => c.trim()).filter(Boolean);
if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, "Address,City,Photos,Status\n");
const browser = await chromium.launch({ headless: false });
const context = await browser.newContext({ storageState: './config/auth.json' });
const page = await context.newPage();
try {
for (const cat of ["Expired", "Canceled"]) {
console.log(`🔎 Opening ${cat}...`);
await page.goto('https://ntrdd.mlsmatrix.com/Matrix/Default.aspx');
await page.locator('a').filter({ hasText: new RegExp(`${cat} \\(\\d+\\)`, 'i') }).first().click();
let lastP = "";
while (true) {
await page.waitForTimeout(5000);
const curP = await page.locator('.d-pagination .active').first().innerText().catch(() => "1");
if (curP === lastP) break;
lastP = curP;
const rows = await page.locator('tr.d-even, tr.d-odd').all();
console.log(`📄 Page ${curP}: checking ${rows.length} rows...`);
for (const row of rows) {
const txt = await row.innerText();
const match = cities.find(c => txt.includes(c));
if (match) {
console.log(`🎯 Found ${match}`);
await row.locator('a[href*="InLineReport"]').first().click();
await page.waitForLoadState('networkidle');
const pTxt = await page.locator('.v-photo-count').first().innerText().catch(() => "1/0");
const count = parseInt(pTxt.split('/')[1]) || 0;
const addr = await page.locator('div.d-fontSize14.d-fontWeightBold').first().innerText().catch(() => "N/A");
fs.appendFileSync(OUT, `"${addr}","${match}",${count},${count < 30 ? "FLAGGED" : "PASS"}\n`);
console.log(`   ${count < 30 ? "
cat << 'EOF' >> scrapers_v2/clean_auditor.js
const n = page.locator('a.d-paginationItem').filter({ hasText: "Next" }).first();
if (await n.isVisible()) { await n.click(); } else { break; }
}
}
await browser.close();
} catch (e) { console.error("Error:", e.message); await browser.close(); }
})();
