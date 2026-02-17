import streamlit as st
import pandas as pd
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="MLS Review", page_icon="🎯", layout="wide")

st.title("🎯 MLS Review")
st.markdown("Scan MLS for Expired/Canceled listings in your target cities")

# Target cities
CITIES = ["GRAPEVINE", "COLLEYVILLE", "SOUTHLAKE", "EULESS", "BEDFORD", "HURST", "FLOWER MOUND"]

# Paths
AUTH_FILE = Path("/Users/danielvega/Desktop/Real Estate Tool/mls-scraper/config/auth.json")
MLS_URL = "https://matrix.ntreis.net/Matrix/Search/MarketWatch"

def city_in_text(text):
    upper = text.upper()
    for city in CITIES:
        if city in upper:
            return city
    return None

def run_scraper():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        with open(AUTH_FILE) as f:
            auth = json.load(f)
        context = browser.new_context()
        context.add_cookies(auth.get("cookies", []))
        page = context.new_page()
        page.goto(MLS_URL)
        page.wait_for_timeout(3000)
        for listing_type in ["Expired", "Canceled"]:
            page.locator(f'a:has-text("{listing_type}")').first.click()
            page.wait_for_timeout(8000)
            page_num = 1
            while page_num <= 5:
                rows = page.locator("table tbody tr").all()
                for row in rows:
                    try:
                        text = row.inner_text()
                        city = city_in_text(text)
                        if city:
                            mls = row.locator("td a").first.inner_text()
                            address = row.locator("td").nth(3).inner_text()
                            results.append({
                                "MLS#": mls,
                                "Address": address,
                                "City": city,
                                "Type": listing_type,
                                "Approve": False
                            })
                    except:
                        continue
                next_btn = page.locator('a.d-paginationItem:has-text("Next")')
                if next_btn.count() == 0:
                    break
                next_btn.click()
                page.wait_for_timeout(8000)
                page_num += 1
            page.goto(MLS_URL)
            page.wait_for_timeout(3000)
        browser.close()
    return results

# Info bar
st.info("📍 Target Cities: Grapevine, Colleyville, Southlake, Euless, Bedford, Hurst, Flower Mound")

# Scrape button
if st.button("🔄 Scrape MLS Now", type="primary"):
    with st.spinner("Scanning MLS... 30-60 seconds..."):
        try:
            listings = run_scraper()
            st.session_state["listings"] = listings
            st.success(f"✅ Found {len(listings)} listings!")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Show results
if "listings" in st.session_state and st.session_state["listings"]:
    st.markdown("---")
    st.subheader(f"📋 Found {len(st.session_state['listings'])} Listings")
    
    cols = st.columns([1.5, 3, 2, 1.5, 1])
    cols[0].markdown("**MLS #**")
    cols[1].markdown("**Address**")
    cols[2].markdown("**City**")
    cols[3].markdown("**Type**")
    cols[4].markdown("**Approve**")
    st.markdown("---")
    
    for idx, listing in enumerate(st.session_state["listings"]):
        cols = st.columns([1.5, 3, 2, 1.5, 1])
        mls = listing["MLS#"]
        cols[0].markdown(f"[{mls}](https://matrix.ntreis.net/Matrix/Public/Portal.aspx?ID={mls})")
        cols[1].write(listing["Address"])
        cols[2].write(listing["City"])
        badge = "🔴" if listing["Type"] == "Expired" else "🟡"
        cols[3].write(f"{badge} {listing['Type']}")
        approved = cols[4].checkbox("✓", key=f"approve_{idx}")
        st.session_state["listings"][idx]["Approve"] = approved
    
    approved_list = [l for l in st.session_state["listings"] if l["Approve"]]
    if approved_list:
        st.success(f"✅ {len(approved_list)} listing(s) approved - ready for audit!")
else:
    st.info("👆 Click 'Scrape MLS Now' to find listings")