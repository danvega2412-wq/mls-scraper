# MLS Scraper

Scrapes NTREIS Matrix (Market Watch: Expired & Canceled listings), extracts listing data, and scores leads with an 8-point failure metric. Outputs to CSV.

## Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Save your login session** (run once; log in when the browser opens)
   ```bash
   node scrapers/login.js
   ```
   Session is stored in `config/auth.json` (git-ignored).

3. **Run the extract & score script**
   ```bash
   node scrapers/extract-and-score.js
   ```

## What it does

- Opens the NTREIS portal, clicks **Matrix** (new tab), closes Rental Beast popup
- Finds the **Market Watch** widget (in iframes), sets Property Type to **Residential**
- Clicks **Expired** then **Canceled** count links (row-specific)
- Waits for the property list, then opens each listing by **click** (no `page.goto`; Matrix uses postbacks)
- Extracts: MLS#, Address, Bedrooms, Bathrooms, Price, DOM, Description (plus fields for the 8 flags)
- Computes **Failure Fraction** (X/8) from: DOM > 85, photos < 40, room-dimension mismatch, no floorplan, no virtual tour, irregular price ending, “shoe list” description, price drops > 2
- Writes **my_daily_leads.csv** with a Failure Flags column

## Requirements

- Node.js
- Playwright (`npx playwright install` if browsers are missing)
- Valid NTREIS login (session in `config/auth.json`)

## License

ISC
