import os, time, json, re
from playwright.sync_api import sync_playwright

BASE_URL = "https://ntrdd.mlsmatrix.com"
SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_session", "state.json")

def parse_address(address):
    parts = address.strip().split()
    if len(parts) < 2:
        return None, None
    street_num = parts[0]
    street_name = parts[1]
    return street_num, street_name

def scrape_comp_details(address, status="Inactive"):
    street_num, street_name = parse_address(address)
    if not street_num or not street_name:
        return None
    result = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            if os.path.exists(SESSION_PATH):
                context = browser.new_context(storage_state=SESSION_PATH)
            else:
                context = browser.new_context()
            page = context.new_page()
            page.goto(f"https://ntrdd.mlsmatrix.com/Matrix/Default.aspx")
            time.sleep(3)
            # Fill street number
            page.locator("#Fm61_Ctrl120_TB").fill(street_num)
            # Fill street name
            page.locator("#Fm61_Ctrl121_TextBox").fill(street_name)
            # Click search
            page.locator("a#m_wm_w12_m_btnSearch").click()
            page.wait_for_url("**/Results.aspx**", timeout=15000)
            time.sleep(3)
            # Find rows and pick the one matching status, click MLS number by text
            rows = page.locator("table tbody tr").all()
            mls_number = None
            for row in rows:
                row_text = row.inner_text()
                if status.lower() in row_text.lower():
                    mls_match = re.search(r'\b(\d{7,})\b', row_text)
                    if mls_match:
                        mls_number = mls_match.group(1)
                    break
            if not mls_number:
                print(f"No {status} listing found for {address}")
                browser.close()
                return None
            # Go back to homepage first, then use Earl's exact speedbar method
            page.goto(f"https://ntrdd.mlsmatrix.com/Matrix/Default.aspx")
            time.sleep(3)
            page.wait_for_selector("input[placeholder*='Shorthand']", timeout=15000)
            search = page.locator("input[placeholder*='Shorthand']").first
            search.fill(mls_number)
            search.press("Enter")
            page.wait_for_selector(f"a:has-text('{mls_number}')", timeout=10000)
            page.locator(f"a:has-text('{mls_number}')").first.click()
            time.sleep(3)
            full_text = page.inner_text("body")
            # Extract description
            desc_match = re.search(r"(?:Remarks|Property Description)[:\s]+(.*?)(?:\n{2,}|Public Driving|Private Rmks)", full_text, re.DOTALL)
            description = desc_match.group(1).strip()[:800] if desc_match else ""
            # Extract features
            features = {}
            for field in ["Interior Feat", "Appliances", "Exterior Feat", "Common Feat"]:
                match = re.search(field + r"[:\s]+([^\n]+)", full_text)
                if match:
                    features[field] = match.group(1).strip()
            result = {
                "address": address,
                "description": description,
                "features": features
            }
            browser.close()
    except Exception as e:
        print(f"Comp scrape error for {address}: {e}")
    return result

def extract_keywords(descriptions):
    keywords = [
        "granite", "quartz", "updated", "renovated", "new roof", "stainless",
        "move-in ready", "open floor plan", "hardwood", "smart home", "pool",
        "covered patio", "community pool", "walk-in closet", "game room",
        "media room", "gourmet kitchen", "upgraded", "modern", "new hvac",
        "new flooring", "fresh paint", "two story", "single story"
    ]
    counts = {}
    for desc in descriptions:
        desc_lower = desc.lower()
        for kw in keywords:
            if kw in desc_lower:
                counts[kw] = counts.get(kw, 0) + 1
    # Return keywords found in at least half the descriptions
    threshold = max(1, len(descriptions) // 2)
    return [kw for kw, count in sorted(counts.items(), key=lambda x: -x[1]) if count >= threshold]

if __name__ == "__main__":
    result = scrape_comp_details("2156 Cloverfern Way", "Active")
    print(result)
