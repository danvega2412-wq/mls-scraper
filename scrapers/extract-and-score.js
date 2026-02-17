/**
 * Data Extraction and Scoring Engine
 * Uses saved login (config/auth.json). Run login.js first if session expired.
 * 1. Navigate to Matrix → Market Watch widget → Expired & Canceled links
 * 2. Filter by cities (Grapevine, Colleyville, Southlake, Euless, Bedford, Hurst)
 * 3. Extract listing data and compute 8-point failure score
 * 4. Output: my_daily_leads.csv
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const TARGET_CITIES = ['Grapevine', 'Colleyville', 'Southlake', 'Euless', 'Bedford', 'Hurst'];
const AUTH_PATH = path.join(__dirname, '..', 'config', 'auth.json');
const OUTPUT_PATH = path.join(__dirname, '..', 'my_daily_leads.csv');

// --- Helpers ---
function escapeCsv(value) {
  if (value == null || value === '') return '';
  const s = String(value).replace(/"/g, '""');
  return s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r') ? `"${s}"` : s;
}

function parsePrice(str) {
  if (!str) return null;
  const num = parseInt(String(str).replace(/[^0-9]/g, ''), 10);
  return isNaN(num) ? null : num;
}

function priceEndsIrregular(priceNum) {
  if (priceNum == null) return true;
  const last3 = priceNum % 1000;
  return last3 !== 0 && last3 !== 900; // 000 or 900 = regular
}

function isShoeListDescription(desc) {
  if (!desc || typeof desc !== 'string') return true;
  const t = desc.trim();
  if (t.length < 200) return true;
  // Boring list: lots of commas/semicolons, short segments
  const segments = t.split(/[,;]/).map(s => s.trim()).filter(Boolean);
  const avgLen = segments.length ? segments.reduce((a, s) => a + s.length, 0) / segments.length : 0;
  return segments.length >= 5 && avgLen < 40;
}

// --- 8-Point Failure Score ---
function computeFailureScore(listing) {
  let failures = 0;
  const flags = [];

  // Flag 1: DOM > 85
  const dom = parseInt(listing.dom, 10);
  if (!isNaN(dom) && dom > 85) {
    failures++;
    flags.push(1);
  }

  // Flag 2: Total Photos < 40
  const photoCount = listing.photoCount != null ? parseInt(listing.photoCount, 10) : 0;
  if (isNaN(photoCount) || photoCount < 40) {
    failures++;
    flags.push(2);
  }

  // Flag 3: Bedrooms/Bathrooms count vs unique Room Dimension entries don't match 1:1
  const beds = parseInt(listing.bedrooms, 10) || 0;
  const baths = parseFloat(listing.bathrooms) || 0;
  const roomDims = listing.roomDimensionCount != null ? parseInt(listing.roomDimensionCount, 10) : 0;
  const expectedRooms = beds + Math.ceil(baths);
  if (expectedRooms > 0 && roomDims !== expectedRooms) {
    failures++;
    flags.push(3);
  }

  // Flag 4: No 'Floorplan' in Supplements or last 5 photo labels
  const hasFloorplan = listing.hasFloorplan === true;
  if (!hasFloorplan) {
    failures++;
    flags.push(4);
  }

  // Flag 5: No Virtual Tour link
  if (!listing.hasVirtualTour) {
    failures++;
    flags.push(5);
  }

  // Flag 6: Price ends in irregular number (not 000 or 900)
  if (priceEndsIrregular(listing.priceNum)) {
    failures++;
    flags.push(6);
  }

  // Flag 7: Description is "shoe list" (boring, under 200 chars)
  if (isShoeListDescription(listing.description)) {
    failures++;
    flags.push(7);
  }

  // Flag 8: Price drop history > 2 reductions
  const priceDrops = listing.priceDropCount != null ? parseInt(listing.priceDropCount, 10) : 0;
  if (!isNaN(priceDrops) && priceDrops > 2) {
    failures++;
    flags.push(8);
  }

  return { failures, fraction: `${failures}/8`, flags };
}

async function closeRentalBeastPopup(page) {
  const targets = [page, ...page.frames()];
  for (const frame of targets) {
    try {
      const popup = frame.locator('[class*="modal"], [class*="dialog"], [class*="popup"], [id*="Modal"], [id*="Dialog"], iframe').filter({ hasText: /Rental Beast|Welcome/i }).first();
      if ((await popup.count()) > 0 && (await popup.isVisible().catch(() => false))) {
        let closeBtn = popup.locator('button, a, [role="button"], span').filter({ hasText: /Close|X|\u00D7/ }).first();
        if ((await closeBtn.count()) === 0) closeBtn = frame.locator('button:has-text("Close"), [title="Close"], [aria-label="Close"]').first();
        if ((await closeBtn.count()) > 0 && (await closeBtn.isVisible().catch(() => false))) {
          await closeBtn.click();
          console.log('Closed Rental Beast / Welcome popup.');
          await page.waitForTimeout(800);
          return true;
        }
      }
    } catch (_) {}
  }
  return false;
}

/** Must close Rental Beast before interacting with Market Watch. Retries until overlay is gone or max attempts. */
async function ensureRentalBeastClosed(page) {
  await page.waitForTimeout(2000);
  for (let attempt = 1; attempt <= 8; attempt++) {
    const closed = await closeRentalBeastPopup(page);
    if (!closed) break;
    console.log('Rental Beast close attempt', attempt);
  }
  console.log('Proceeding to Market Watch (Rental Beast overlay cleared or not present).');
}

/** Find frame that contains the widget specifically titled 'Market Watch' (not just any text). */
async function findFrameWithMarketWatch(page, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const frames = page.frames();
    for (const frame of frames) {
      try {
        const titleEl = frame.locator('th, h2, h3, h4, caption, .widget-title, [class*="title"]').filter({ hasText: /^Market Watch$/i }).first();
        if ((await titleEl.count()) > 0 && (await titleEl.isVisible().catch(() => false))) {
          return frame;
        }
      } catch (_) {}
    }
    await page.waitForTimeout(500);
  }
  return null;
}

/** Get the widget container that has the title 'Market Watch' (so we only read from that widget). */
function getMarketWatchWidgetLocator(frame) {
  return frame.locator('table, div, section').filter({ has: frame.locator('th, h2, h3, caption, .widget-title').filter({ hasText: /^Market Watch$/i }) }).first();
}

async function ensureMatrixAndMarketWatch(page) {
  const numberLinkRegex = /\(\d+\)/;

  // Wait for the property list to appear
  async function waitForResultsTable() {
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    const gridOrBar = page.locator('.d-grid, #DisplayBar, table tbody tr').first();
    await gridOrBar.waitFor({ state: 'visible', timeout: 25000 });
    await page.waitForTimeout(2000);
  }

  // Find frame that has the widget specifically titled 'Market Watch'
  let frame = await findFrameWithMarketWatch(page, 30000);
  if (!frame) {
    console.log('Debug — Could not find widget titled "Market Watch". Detected iframes:');
    for (const f of page.frames()) {
      try {
        console.log('  name:', f.name() || '(none)', 'url:', f.url());
      } catch (_) {}
    }
    throw new Error('Market Watch widget not found in any frame. See iframe debug above.');
  }

  const widget = getMarketWatchWidgetLocator(frame);
  await widget.waitFor({ state: 'visible', timeout: 8000 });

  // Ensure Property Type is set to Residential before reading numbers
  const propertyTypeSelect = widget.locator('select').filter({ hasText: /Property Type|Residential/i }).first();
  if ((await propertyTypeSelect.count()) > 0) {
    await propertyTypeSelect.selectOption({ label: /Residential/i }).catch(() => propertyTypeSelect.selectOption({ index: 1 }).catch(() => {}));
    await page.waitForTimeout(1500);
  }

  // --- Expired: only inside the Market Watch widget; log full row text and cross-check
  const expiredRow = widget.locator('tr').filter({ hasText: /Expired/ }).first();
  await expiredRow.waitFor({ state: 'visible', timeout: 10000 });
  const expiredRowText = (await expiredRow.textContent()).trim().replace(/\s+/g, ' ');
  console.log('Expired row text:', expiredRowText);
  if (!/Expired\s*\(\d+\)/.test(expiredRowText)) {
    console.log('Debug — Row does not look like "Expired (44)". Trying other frames.');
    frame = null;
    for (const f of page.frames()) {
      try {
        const w = f.locator('table, div, section').filter({ has: f.locator('th, h2, h3, caption').filter({ hasText: /^Market Watch$/i }) }).first();
        if ((await w.count()) === 0) continue;
        const row = w.locator('tr').filter({ hasText: /Expired/ }).first();
        if ((await row.count()) === 0) continue;
        const text = (await row.textContent()).trim().replace(/\s+/g, ' ');
        console.log('  Frame row text:', text);
        if (/Expired\s*\(\d+\)/.test(text)) {
          frame = f;
          break;
        }
      } catch (_) {}
    }
    if (!frame) throw new Error('No frame had a row like "Expired (44)". Check logs above.');
    const w2 = getMarketWatchWidgetLocator(frame);
    await w2.waitFor({ state: 'visible', timeout: 5000 });
    const sel = w2.locator('select').filter({ hasText: /Property Type|Residential/i }).first();
    if ((await sel.count()) > 0) await sel.selectOption({ label: /Residential/i }).catch(() => {});
    await page.waitForTimeout(500);
    await w2.locator('tr').filter({ hasText: /Expired/ }).locator('a').filter({ hasText: numberLinkRegex }).first().click();
  } else {
    const expiredLink = expiredRow.locator('a').filter({ hasText: numberLinkRegex }).first();
    await expiredLink.click();
  }
  await waitForResultsTable();

  // Go back to dashboard, then do Canceled (same precision)
  await page.goBack();
  frame = await findFrameWithMarketWatch(page, 30000);
  if (!frame) throw new Error('Market Watch widget not found after going back.');

  const widget2 = getMarketWatchWidgetLocator(frame);
  await widget2.waitFor({ state: 'visible', timeout: 8000 });
  const propertyTypeSelect2 = widget2.locator('select').filter({ hasText: /Property Type|Residential/i }).first();
  if ((await propertyTypeSelect2.count()) > 0) {
    await propertyTypeSelect2.selectOption({ label: /Residential/i }).catch(() => {});
    await page.waitForTimeout(1000);
  }

  const canceledRow = widget2.locator('tr').filter({ hasText: /Canceled/ }).first();
  await canceledRow.waitFor({ state: 'visible', timeout: 10000 });
  const canceledRowText = (await canceledRow.textContent()).trim().replace(/\s+/g, ' ');
  console.log('Canceled row text:', canceledRowText);
  const canceledLink = canceledRow.locator('a').filter({ hasText: numberLinkRegex }).first();
  await canceledLink.click();
  await waitForResultsTable();
}

async function applyCityFilter(page) {
  // Try common filter patterns: City dropdown, search field, or filter panel
  const cityInput = page.locator('input[placeholder*="City"], select[name*="city"], [data-field="City"]').first();
  await cityInput.waitFor({ state: 'visible', timeout: 8000 }).catch(() => {});
  for (const city of TARGET_CITIES) {
    await cityInput.fill(city).catch(() => {});
    await page.waitForTimeout(300);
  }
  // If it's a multi-select or dropdown, you may need to select each city; adjust as needed
  const applyBtn = page.getByRole('button', { name: /apply|search|filter|go/i }).first();
  await applyBtn.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(3000);
}

// Matrix property links are JavaScript postbacks — we open by clicking, not page.goto()
const PROPERTY_LIST_SELECTOR = 'table tbody tr a, .d-grid a, #DisplayBar a, .listing-row a, a[href*="listing"], a[href*="detail"]';

async function getListingCountAndSelector(page) {
  await page.locator(PROPERTY_LIST_SELECTOR).first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {});
  const links = await page.locator(PROPERTY_LIST_SELECTOR).all();
  const count = links.length;
  return { count, selector: PROPERTY_LIST_SELECTOR };
}

async function firstText(page, ...selectors) {
  for (const sel of selectors) {
    try {
      const t = await page.locator(sel).first().textContent({ timeout: 1500 });
      if (t != null && t.trim()) return t.trim();
    } catch (_) {}
  }
  return '';
}

async function extractListingDetail(page, listingUrl = null) {
  // Matrix uses JavaScript postbacks — only use goto when explicitly opening by URL (e.g. from a saved link)
  if (listingUrl) {
    await page.goto(listingUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1500);
  } else {
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);
  }

  // MLS#, Address, Bedrooms, Bathrooms, Price, DOM, Description (adjust selectors to your Matrix detail page)
  const mls = await firstText(page, '[data-field="MLSNumber"]', '.mls-number', 'td:has-text("MLS")');
  const address = await firstText(page, '[data-field="Address"]', '.address', '[data-field="StreetAddress"]');
  const bedrooms = await firstText(page, '[data-field="Bedrooms"]', '.bedrooms');
  const bathrooms = await firstText(page, '[data-field="Bathrooms"]', '.bathrooms');
  const priceText = await firstText(page, '[data-field="Price"]', '.price', '[data-field="ListPrice"]');
  const dom = await firstText(page, '[data-field="DOM"]', '.dom');
  const description = await firstText(page, '[data-field="PublicRemarks"]', '.description', '.remarks', '[data-field="Remarks"]');

  // Photo count
  const photoEls = await page.locator('[data-photo-index], .photo-thumb, .gallery img, [class*="photo"] img').count();
  const photoLabelText = await firstText(page, '[data-label*="Photo"]', '*:has-text("Photos")');
  const photoCount = photoEls > 0 ? photoEls : (photoLabelText.replace(/\D/g, '') || '0');

  // Room dimensions (unique entries) – e.g. "Living: 15x12", "Bedroom: 12x10"
  const roomText = await page.locator('[data-field*="Room"], .room-dimensions').allTextContents().then(a => a.join(' ')).catch(() => '');
  const roomMatches = roomText.match(/\d+\s*[x×]\s*\d+/g) || [];
  const roomDimensionCount = new Set(roomMatches).size;

  // Supplements and last 5 photo labels for "Floorplan"
  const supplements = (await page.locator('.supplements, [class*="supplement"]').allTextContents()).join(' ').toLowerCase();
  const photoLabels = await page.locator('.photo-label, [class*="photo-caption"], .gallery [title]').allTextContents().then(a => a.slice(-5).join(' ').toLowerCase()).catch(() => '');
  const hasFloorplan = /floorplan|floor plan/.test(supplements) || /floorplan|floor plan/.test(photoLabels);

  // Virtual Tour link
  const hasVirtualTour = await page.locator('a[href*="virtual"], a[href*="tour"], a:has-text("Virtual Tour"), a:has-text("3D Tour")').first().isVisible().catch(() => false);

  // Price drop count (e.g. "Price Change" or "History" section)
  const historyText = await page.locator('[class*="history"], [class*="price-change"]').allTextContents().then(a => a.join(' ')).catch(() => '');
  const priceDropCount = (historyText.match(/price\s*reduc|reduc|price\s*change/gi) || []).length;

  const priceNum = parsePrice(priceText);

  return {
    mls,
    address,
    bedrooms,
    bathrooms,
    price: priceText,
    priceNum,
    dom,
    description,
    photoCount,
    roomDimensionCount,
    hasFloorplan,
    hasVirtualTour,
    priceDropCount,
  };
}

async function main() {
  if (!fs.existsSync(AUTH_PATH)) {
    console.error('No config/auth.json found. Run node scrapers/login.js first and log in.');
    process.exit(1);
  }

  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: false, slowMo: 100 });
  const context = await browser.newContext({ storageState: AUTH_PATH });
  const page = await context.newPage();

  try {
    // Navigate to the main portal (direct Matrix URL is broken — Matrix opens via new tab only)
    console.log('Opening Portal...');
    await page.goto('https://ntreis.clareityiam.net/idp/login', { waitUntil: 'domcontentloaded' });

    await page.waitForTimeout(1500); // let the page (and any iframes) settle

    // Matrix is a button/div/span, not an <a> — find it by exact text
    const matrixButton = page.locator('div, span, button, a').filter({ hasText: /^Matrix$/ }).first();
    await matrixButton.waitFor({ state: 'visible', timeout: 15000 });

    // Catch the new tab when Matrix is clicked, then force-click the button
    console.log('Clicking Matrix (opens new tab)...');
    const [matrixPage] = await Promise.all([
      context.waitForEvent('page', { timeout: 60000 }),
      matrixButton.click({ force: true }),
    ]);

    await matrixPage.waitForLoadState('domcontentloaded');
    try {
      console.log('Switched to Matrix tab:', await matrixPage.title());
    } catch (_) {
      console.log('Switched to Matrix tab (title unavailable — page may have navigated).');
    }

    // Must close Rental Beast overlay before Market Watch or links won't be clickable
    await ensureRentalBeastClosed(matrixPage);

    // All scoring and extracting use matrixPage (the new tab)
    await ensureMatrixAndMarketWatch(matrixPage);
    await applyCityFilter(matrixPage);

    // Open properties by clicking (Matrix uses postbacks; page.goto() causes ERR_ABORTED)
    const { count, selector } = await getListingCountAndSelector(matrixPage);
    console.log(`Found ${count} listing(s). Extracting by clicking each...`);

    const rows = [];
    const csvHeader = ['MLS#', 'Address', 'Bedrooms', 'Bathrooms', 'Price', 'DOM', 'Description', 'Failure Fraction', 'Failure Flags'];

    for (let i = 0; i < count; i++) {
      console.log(`  [${i + 1}/${count}] Clicking property...`);
      try {
        const link = matrixPage.locator(selector).nth(i);
        await link.click();
        await matrixPage.waitForLoadState('domcontentloaded');
        await matrixPage.waitForTimeout(2000);

        const listing = await extractListingDetail(matrixPage); // no URL — we're on the detail page
        const cityMatch = TARGET_CITIES.some(c => (listing.address || '').toLowerCase().includes(c.toLowerCase()));
        if (listing.address && !cityMatch) continue;

        const { fraction, flags } = computeFailureScore(listing);
        rows.push([
          listing.mls,
          listing.address,
          listing.bedrooms,
          listing.bathrooms,
          listing.price,
          listing.dom,
          listing.description,
          fraction,
          flags.join(';'),
        ]);
      } catch (e) {
        console.warn('  Skip listing:', e.message);
      }

      await matrixPage.goBack().catch(() => {});
      await matrixPage.waitForLoadState('domcontentloaded');
      await matrixPage.locator(selector).first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {});
      await matrixPage.waitForTimeout(500);
    }

    const csvLines = [csvHeader.map(escapeCsv).join(','), ...rows.map(r => r.map(escapeCsv).join(','))];
    fs.writeFileSync(OUTPUT_PATH, csvLines.join('\r\n'), 'utf8');
    console.log(`\nDone. Saved ${rows.length} leads to ${OUTPUT_PATH}`);
  } catch (err) {
    console.error('Error:', err);
  } finally {
    await browser.close();
  }
}

main();
