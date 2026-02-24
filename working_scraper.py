import os
import time
import sys
import json
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv(dotenv_path='../.env')

BASE_URL = "https://matrix.ntreis.net"
USERNAME = os.environ.get("MATRIX_USERNAME")
PASSWORD = os.environ.get("MATRIX_PASSWORD")

def log(msg):
    print(f"[*] {msg}")

def scrape_listing_data(page):
    data = {}
    try:
        full_text = page.inner_text("body")
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]

        for i, line in enumerate(lines):
            if "LP:" in line:
                parts = line.split("LP:")
                if len(parts) > 1:
                    price = parts[1].strip().split()[0]
                    data["price"] = price
            if "DOM:" in line:
                parts = line.split("DOM:")
                if len(parts) > 1:
                    dom = parts[1].strip().split()[0]
                    data["dom"] = dom
            if "SqFt:" in line:
                parts = line.split("SqFt:")
                if len(parts) > 1:
                    sqft = parts[1].strip().split("/")[0].strip().split()[0]
                    data["sqft"] = sqft
            if "Yr Built:" in line:
                parts = line.split("Yr Built:")
                if len(parts) > 1:
                    yr = parts[1].strip().split("/")[0].strip().split()[0]
                    data["year_built"] = yr
            if "Beds:" in line:
                parts = line.split("Beds:")
                if len(parts) > 1:
                    beds = parts[1].strip().split()[0]
                    data["beds"] = beds
            if "Tot Bth:" in line:
                parts = line.split("Tot Bth:")
                if len(parts) > 1:
                    baths = parts[1].strip().split()[0]
                    data["baths"] = baths
            if "MUD Dst:" in line:
                if "Yes" in line:
                    data["mud"] = "Yes"
                else:
                    data["mud"] = "No"
            if "PID:" in line and "PID:No" not in line and "PID:Yes" in line:
                data["pid"] = "Yes"
            elif "PID:No" in line:
                data["pid"] = "No"

        photo_counter = page.locator("text=/\\d+ \/ 40/")
        if photo_counter.count() > 0:
            counter_text = photo_counter.first.inner_text()
            total = counter_text.split("/")[-1].strip()
            data["photo_count"] = total
        else:
            all_text = page.inner_text("body")
            import re
            match = re.search(r"(\d+)\s*/\s*40", all_text)
            if match:
                data["photo_count"] = "40"
                data["photos_shown"] = match.group(1)

        desc_text = ""
        try:
            desc = page.locator("text=Property Description").first
            if desc.count() > 0:
                parent_text = page.inner_text("body")
                if "Property\nDescription:" in parent_text:
                    idx = parent_text.index("Property\nDescription:")
                    desc_text = parent_text[idx+22:idx+300].strip()
                elif "Property Description" in parent_text:
                    idx = parent_text.index("Property Description")
                    desc_text = parent_text[idx+20:idx+300].strip()
        except:
            pass
        if desc_text:
            data["description"] = desc_text[:200]

        rooms_data = []
        try:
            import re
            room_matches = re.findall(r"(\w[\w\s]+?)\s+(\d+\s*x\s*\d+)", full_text)
            for room, dims in room_matches:
                rooms_data.append({"room": room.strip(), "dimensions": dims.strip()})
                if dims.strip() in ["1 x 1", "1x1"]:
                    data["bad_dimensions"] = "Yes"
        except:
            pass
        if rooms_data:
            data["rooms"] = rooms_data

        import re
        photo_match = re.search(r'(\d+)\s*/\s*(\d+)', full_text)
        if photo_match:
            data["photos_shown"] = photo_match.group(1)
            data["photos_total"] = photo_match.group(2)

        missing_dims = []
        room_section = re.findall(r'([A-Z][a-zA-Z\s]+?)\s+(\d+\s*x\s*\d+|1\s*x\s*1)', full_text)
        for room, dim in room_section:
            if dim.strip() in ["1 x 1", "1x1"]:
                missing_dims.append(room.strip())
        if missing_dims:
            data["bad_dimensions"] = "Yes"
            data["bad_dimension_rooms"] = missing_dims

        virtual_tour = page.locator("text=Virtual Te, a[href*='tour'], a[href*='matterport'], a[href*='3d']")
        if virtual_tour.count() > 0:
            data["virtual_tour"] = "Yes"
        else:
            data["virtual_tour"] = "Not confirmed"

    except Exception as e:
        log(f"Data scrape error: {e}")

    return data

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 working_scraper.py <MLS_NUMBER>")
        return

    mls_number = sys.argv[1]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        log(f"Targeting MLS# {mls_number}...")
        page.goto(f"{BASE_URL}/Matrix/Default.aspx")
        time.sleep(3)

        if "login" in page.url or "clareity" in page.url:
            log("Logging in automatically...")
            page.wait_for_selector("input[name='username'], input[id='username']", timeout=10000)
            page.fill("input[name='username'], input[id='username']", USERNAME)
            page.fill("input[name='password'], input[id='password'], input[type='password']", PASSWORD)
            time.sleep(1)
            page.get_by_role("button", name="Login").click()
            time.sleep(5)

            if "login" in page.url or "clareity" in page.url:
                log("MFA required. You have 60 seconds...")
                time.sleep(60)

        log("Navigating to Matrix...")
        page.goto(f"{BASE_URL}/Matrix/Default.aspx")
        time.sleep(3)

        log("Searching for listing...")
        page.wait_for_selector("input[placeholder*='Shorthand']", timeout=30000)
        search = page.locator("input[placeholder*='Shorthand']").first
        search.fill(mls_number)
        search.press("Enter")

        link_selector = f"a:has-text('{mls_number}')"
        page.wait_for_selector(link_selector, timeout=10000)
        page.locator(link_selector).first.click()
        log("Landed on listing page!")

        time.sleep(3)

        log("Scraping listing data...")
        listing_data = scrape_listing_data(page)
        listing_data["mls"] = mls_number
        log(f"Scraped: {listing_data}")

        photo_dir = f"photos/{mls_number}"
        os.makedirs(photo_dir, exist_ok=True)

        with open(f"{photo_dir}/listing_data.json", "w") as f:
            json.dump(listing_data, f, indent=2)
        log("Listing data saved.")

        try:
            log("Clicking Photos tab...")
            page.get_by_role("link", name="Photos").click()
            time.sleep(3)

            log("Capturing photo grid...")
            for i in range(1, 4):
                page.screenshot(path=f"{photo_dir}/grid_part_{i}.jpg", full_page=True)
                page.mouse.wheel(0, 1500)
                time.sleep(1)

            log(f"Success! Saved to {photo_dir}")
        except Exception as e:
            log(f"Photo tab error: {e}")

        browser.close()

if __name__ == "__main__":
    main()
