#!/usr/bin/env python3
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://matrix.ntreis.net"
CITIES_FILE = "cities_final.txt"
AUTH_FILE = "auth.json"

def load_cities():
    with open(CITIES_FILE, 'r') as f:
        cities = [line.strip().upper() for line in f if line.strip()]
    print(f"Loaded cities: {cities}")
    return cities

def load_session():
    with open(AUTH_FILE, 'r') as f:
        return json.load(f)

def city_in_row(row_text, target_cities):
    row_upper = row_text.upper()
    for city in target_cities:
        if f" {city} " in f" {row_upper} " or f" {city}," in f" {row_upper} ":
            return city
    return None

def scan_page(page, target_cities):
    matches = []
    page.wait_for_selector('tr.d-even, tr.d-odd', timeout=10000)
    time.sleep(1)
    rows = page.locator('tr.d-even, tr.d-odd').all()
    print(f"  Scanning {len(rows)} rows...")
    for idx, row in enumerate(rows):
        try:
            row_text = row.inner_text(timeout=2000)
            matched_city = city_in_row(row_text, target_cities)
            if matched_city:
                print(f"    ✓ {matched_city} at row {idx}")
                matches.append((matched_city, idx))
        except:
            continue
    return matches

def has_next_page(page):
    return page.locator('a:has-text("next")').count() > 0

def go_to_next_page(page):
    try:
        page.locator('a:has-text("next")').first.click()
        page.wait_for_load_state('networkidle', timeout=15000)
        time.sleep(2)
        return True
    except:
        return False

def main():
    cities = load_cities()
    session = load_session()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(session['cookies'])
        page = context.new_page()
        
        page.goto(f"{BASE_URL}/Matrix/Search/MarketWatch")
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        page.locator('a:has-text("Expired")').first.click()
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        page_num = 1
        while True:
            print(f"\nPage {page_num}:")
            matches = scan_page(page, cities)
            
            if not has_next_page(page):
                break
            go_to_next_page(page)
            page_num += 1
        
        print("\nDone!")
        browser.close()

if __name__ == "__main__":
    main()
