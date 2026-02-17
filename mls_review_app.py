import re
import threading
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
APP_DIR = Path(__file__).resolve().parent
AUTH_FILE = APP_DIR / "config" / "auth.json"
BROWSER_SESSION_DIR = APP_DIR / "browser_session"
STATE_FILE = BROWSER_SESSION_DIR / "state.json"
MLS_URL = "https://matrix.ntreis.net/Matrix/Search/MarketWatch"
MLS_LINK_BASE = "https://ntrdd.mlsmatrix.com/Matrix/Public/Portal.aspx?ID="

ROW_JUNK = ("agent 2 line", "try our new search", "try our", "subscribe")  # Skip entire row if present
ADDRESS_JUNK = ("mile", " mi ", "search", "click", "http", "matrix", "portal", "next", "prev", "agent 2")  # For cleaning address lines

def city_in_text(text):
    """Match target cities anywhere in row text, case-insensitive, ignoring extra spaces."""
    if not text:
        return None
    normalized = " ".join(str(text).upper().split())
    for city in CITIES:
        city_norm = " ".join(city.split())
        if city_norm in normalized:
            return city
    return None

def ensure_browser_session():
    """If browser_session/state.json exists, use it; else use auth.json cookies (legacy)."""
    BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)

def _open_view_live_in_browser(mls_number):
    """Run in background thread: headed browser, go to Matrix, type MLS# in search bar, press Enter to load Agent Full."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            if STATE_FILE.exists():
                context = browser.new_context(storage_state=str(STATE_FILE))
            else:
                context = browser.new_context()
                if AUTH_FILE.exists():
                    with open(AUTH_FILE) as f:
                        context.add_cookies(json.load(f).get("cookies", []))
            page = context.new_page()
            page.goto(MLS_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            search_selectors = [
                'input[placeholder*="Search" i]',
                'input[placeholder*="MLS" i]',
                'input[name*="search" i]',
                'input[name*="SpeedBar" i]',
                'input[id*="search" i]',
                'input[id*="SpeedBar" i]',
                'input[type="text"]',
            ]
            search_box = None
            for sel in search_selectors:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=2000)
                    search_box = el
                    break
                except Exception:
                    continue
            if not search_box:
                search_box = page.locator("input").first
                search_box.wait_for(state="visible", timeout=3000)
            search_box.fill(str(mls_number))
            search_box.press("Enter")
            page.wait_for_timeout(5000)
            page.wait_for_timeout(300000)  # Keep window open 5 min
            browser.close()
    except Exception as e:
        print(f"View Live error: {e}")

def run_scraper():
    ensure_browser_session()
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if STATE_FILE.exists():
            context = browser.new_context(storage_state=str(STATE_FILE))
        else:
            context = browser.new_context()
            if AUTH_FILE.exists():
                with open(AUTH_FILE) as f:
                    auth = json.load(f)
                context.add_cookies(auth.get("cookies", []))
        page = context.new_page()
        page.goto(MLS_URL)
        page.wait_for_timeout(3000)
        for listing_type in ["Expired", "Canceled"]:
            page.locator(f'a:has-text("{listing_type}")').first.click()
            page.wait_for_timeout(5000)  # Loading safety: wait for Matrix table to fully load
            page_num = 1
            while page_num <= 5:
                rows = page.locator("table tbody tr").all()
                for row in rows:
                    try:
                        row_text = row.inner_text()
                        row_lower = row_text.lower()
                        if any(j in row_lower for j in ROW_JUNK):
                            continue
                        city = city_in_text(row_text)
                        if not city:
                            continue
                        mls = ""
                        for link in row.locator("a").all():
                            link_text = link.inner_text().strip()
                            if link_text and re.search(r"\d{5,}", link_text):
                                mls = re.sub(r"\D", "", link_text)[:12]
                                break
                        if not mls or len(mls) < 5:
                            continue
                        lines = [ln.strip() for ln in row_text.splitlines() if ln.strip()]
                        lines = [ln for ln in lines if not any(j in ln.lower() for j in ADDRESS_JUNK) and len(ln) > 3]
                        address = ""
                        for ln in lines:
                            if re.match(r"^\d+\s+[A-Za-z]", ln) and re.search(r"\d", ln) and re.search(r"[A-Za-z]", ln):
                                if ln != mls and not re.search(r"\d+\.\d+\s*(mile|mi)", ln, re.I):
                                    address = ln
                                    break
                        if not address and lines:
                            for ln in lines:
                                if re.search(r"^\d+", ln) and re.search(r"[A-Za-z]{2,}", ln) and "mile" not in ln.lower():
                                    address = ln
                                    break
                            if not address:
                                address = lines[0] if lines else ""

                        mls_url = MLS_LINK_BASE + str(mls)
                        results.append({
                            "MLS#": mls,
                            "MLS_URL": mls_url,
                            "Address": address,
                            "City": city,
                            "Type": listing_type,
                            "Approve": False
                        })
                    except Exception:
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

# Persistent session: offer to save session if not yet saved
if not STATE_FILE.exists():
    st.warning("💾 No saved session. Log in once to stay logged into Matrix.")
    if st.button("🔐 Open browser to log in (save session)"):
        with st.spinner("Opening browser — log in to Matrix, then come back here."):
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                if AUTH_FILE.exists():
                    with open(AUTH_FILE) as f:
                        context.add_cookies(json.load(f).get("cookies", []))
                page = context.new_page()
                page.goto(MLS_URL)
                page.wait_for_timeout(90000)  # 90 s to log in
                BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(STATE_FILE))
                browser.close()
            st.success("Session saved. You can scrape without logging in again.")
            st.rerun()
else:
    st.caption("✅ Using saved session (browser_session/)")

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
    
    cols = st.columns([1, 1.8, 3, 1.5, 1.5, 1, 1.5])
    cols[0].markdown("**MLS #**")
    cols[1].markdown("**View Live**")
    cols[2].markdown("**Address**")
    cols[3].markdown("**City**")
    cols[4].markdown("**Type**")
    cols[5].markdown("**Approve**")
    cols[6].markdown("**Actions**")
    st.markdown("---")
    
    for idx, listing in enumerate(st.session_state["listings"]):
        cols = st.columns([1, 1.8, 3, 1.5, 1.5, 1, 1.5])
        mls = listing.get("MLS#", "")
        cols[0].write(mls)
        if mls and len(str(mls)) >= 5 and str(mls).isdigit():
            if cols[1].button("🚀 View Live in Matrix", key=f"viewlive_{idx}"):
                if STATE_FILE.exists() or AUTH_FILE.exists():
                    thread = threading.Thread(target=_open_view_live_in_browser, args=(str(mls),), daemon=True)
                    thread.start()
                    st.toast(f"Opening MLS {mls} in browser…")
                else:
                    st.warning("Save a session first (log in once) to use View Live.")
        else:
            cols[1].write("—")
        cols[2].write(listing["Address"])
        cols[3].write(listing["City"])
        badge = "🔴" if listing["Type"] == "Expired" else "🟡"
        cols[4].write(f"{badge} {listing['Type']}")
        approved = cols[5].checkbox("✓", key=f"approve_{idx}")
        st.session_state["listings"][idx]["Approve"] = approved
        if cols[6].button("Push to Mojo", key=f"mojo_{idx}"):
            print(f"Pushing {listing['Address']} to Mojo")
            st.toast(f"Pushing {listing['Address']} to Mojo")
    
    approved_list = [l for l in st.session_state["listings"] if l["Approve"]]
    if approved_list:
        st.success(f"✅ {len(approved_list)} listing(s) approved - ready for audit!")
else:
    st.info("👆 Click 'Scrape MLS Now' to find listings")