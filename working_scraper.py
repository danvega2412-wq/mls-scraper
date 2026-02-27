import os
import time
import sys
import json
import re
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv(dotenv_path='../.env')
BASE_URL = "https://matrix.ntreis.net"
USERNAME = os.environ.get("MATRIX_USERNAME")
PASSWORD = os.environ.get("MATRIX_PASSWORD")
SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_session", "state.json")

def log(msg):
    print(f"[*] {msg}")

def scrape_listing_data(page):
    data = {}
    try:
        full_text = page.inner_text("body")
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "LP:" in line and "OLP:" not in line:
                parts = line.split("LP:")
                if len(parts) > 1:
                    data["price"] = parts[1].strip().split()[0]
            if "DOM:" in line:
                parts = line.split("DOM:")
                if len(parts) > 1:
                    data["dom"] = parts[1].strip().split()[0]
            if "SqFt:" in line:
                parts = line.split("SqFt:")
                if len(parts) > 1:
                    data["sqft"] = parts[1].strip().split("/")[0].strip().split()[0]
            if "Yr Built:" in line:
                parts = line.split("Yr Built:")
                if len(parts) > 1:
                    data["year_built"] = parts[1].strip().split("/")[0].strip().split()[0]
            if "Beds:" in line:
                parts = line.split("Beds:")
                if len(parts) > 1:
                    data["beds"] = parts[1].strip().split()[0]
            if "Tot Bth:" in line:
                parts = line.split("Tot Bth:")
                if len(parts) > 1:
                    data["baths"] = parts[1].strip().split()[0]
            if "MUD Dst:" in line:
                data["mud"] = "Yes" if "Yes" in line else "No"
            if "PID:Yes" in line:
                data["pid"] = "Yes"
            elif "PID:No" in line:
                data["pid"] = "No"
        photo_match = re.search(r"(\d+) / (\d+)", full_text)
        if photo_match:
            data["photos_total"] = photo_match.group(2)
        addr_match = re.search(r"(\d+\s+[A-Za-z0-9 ]+),\s*([A-Za-z ]+),\s*(?:Texas|TX)", full_text)
        if addr_match:
            data["address"] = addr_match.group(1).strip()
            data["city"] = addr_match.group(2).strip()
        all_rooms = []
        missing_dims = []
        room_section = re.findall(r'([A-Z][a-zA-Z\s]+?)\s+(\d+\s*x\s*\d+|1\s*x\s*1)', full_text)
        for room, dim in room_section:
            room_clean = room.strip()
            dim_clean = dim.strip()
            all_rooms.append({"room": room_clean, "dimensions": dim_clean})
            is_key_room = any(k in room_clean.lower() for k in ["bedroom", "primary", "living room", "living area"])
            if is_key_room and dim_clean in ["1 x 1", "1x1"]:
                missing_dims.append(room_clean)
        key_room_names = ["bedroom", "primary", "living room", "living area"]
        found_key_rooms = [r["room"].lower() for r in all_rooms if any(k in r["room"].lower() for k in key_room_names)]
        for key in key_room_names:
            if key in ["bedroom", "primary"]:
                if not any(key in r for r in found_key_rooms):
                    missing_dims.append(key.title() + " (no dimensions found)")
        if all_rooms:
            data["rooms"] = all_rooms
        if missing_dims:
            data["bad_dimensions"] = "Yes"
            data["bad_dimension_rooms"] = missing_dims
    except Exception as e:
        log(f"Data scrape error: {e}")
    return data

def check_virtual_tour_and_floor_plan(page, context):
    result = {"virtual_tour": "No", "floor_plan": "No"}
    try:
        vt_link = page.locator("a:has-text('Virtual To')")
        if vt_link.count() == 0:
            log("No Virtual Transaction Desk link found.")
            return result
        log("Clicking Virtual Transaction Desk link...")
        with context.expect_page() as new_page_info:
            vt_link.first.click()
        popup = new_page_info.value
        popup.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        pp_link = popup.locator("a[href*='propertypanorama.com']")
        if pp_link.count() == 0:
            log("No Property Panorama link found.")
            popup.close()
            return result
        pp_url = pp_link.first.get_attribute("href")
        log(f"Found Property Panorama link: {pp_url}")
        tour_page = context.new_page()
        tour_page.goto(pp_url)
        tour_page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        body_text = tour_page.inner_text("body")
        tour_page.close()
        popup.close()
        if "Tour Unavailable" in body_text:
            log("Tour Unavailable.")
            return {"virtual_tour": "No", "floor_plan": "No"}
        else:
            log("Tour confirmed.")
            return {"virtual_tour": "Yes", "floor_plan": "Yes"}
    except Exception as e:
        log(f"Virtual tour check error: {e}")
        return {"virtual_tour": "Not confirmed", "floor_plan": "Not confirmed"}

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 working_scraper.py <MLS_NUMBER>")
        return
    mls_number = sys.argv[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if os.path.exists(SESSION_PATH):
            log("Loading saved session...")
            context = browser.new_context(storage_state=SESSION_PATH)
        else:
            log("No saved session, starting fresh...")
            context = browser.new_context()
        page = context.new_page()
        log(f"Targeting MLS# {mls_number}...")
        page.goto(f"{BASE_URL}/Matrix/Default.aspx")
        time.sleep(3)
        if "login" in page.url or "clareity" in page.url:
            log("Session expired — MFA required. Relaunching visible browser...")
            browser.close()
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"{BASE_URL}/Matrix/Default.aspx")
            time.sleep(3)
            try:
                page.wait_for_selector("input[name='username'], input[id='username']", timeout=10000)
                page.fill("input[name='username'], input[id='username']", USERNAME)
                page.fill("input[name='password'], input[id='password'], input[type='password']", PASSWORD)
                time.sleep(1)
                page.get_by_role("button", name="Login").click()
                time.sleep(5)
            except:
                log("Login form not found, waiting for MFA...")
            if "login" in page.url or "clareity" in page.url:
                log("MFA required. You have 60 seconds...")
                time.sleep(60)
            context.storage_state(path=SESSION_PATH)
            log("Session saved.")
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
        log("Checking virtual tour and floor plan...")
        tour_data = check_virtual_tour_and_floor_plan(page, context)
        listing_data["virtual_tour"] = tour_data["virtual_tour"]
        listing_data["floor_plan"] = tour_data["floor_plan"]
        log(f"Tour check: {tour_data}")
        photo_dir = f"photos/{mls_number}"
        os.makedirs(photo_dir, exist_ok=True)
        # Preserve existing visual flags if present
        existing_json_path = f"{photo_dir}/listing_data.json"
        visual_flag_keys = ["bad_lead_photo", "poor_photo_sequence", "no_professional_photography", "poor_photography_quality", "floor_plan_in_photos", "virtual_tour_in_photos"]
        if os.path.exists(existing_json_path):
            try:
                existing = json.load(open(existing_json_path))
                for k in visual_flag_keys:
                    if existing.get(k):
                        listing_data[k] = existing[k]
            except:
                pass
        with open(existing_json_path, "w") as f:
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
            log(f"Done. Saved to {photo_dir}")
        except Exception as e:
            log(f"Photo tab error: {e}")
        context.storage_state(path=SESSION_PATH)
        browser.close()

if __name__ == "__main__":
    main()
