import requests
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import subprocess

RENTCAST_KEY = "dda29a2c21934d8399af4c76678dab2c"

import datetime

def _fetch_comps_attempt(address, city, state, beds, baths, sqft, subject_price, sqft_pct, max_days):
    sqft_min = int(sqft * (1 - sqft_pct))
    sqft_max = int(sqft * (1 + sqft_pct))
    url = (
        "https://api.rentcast.io/v1/avm/value"
        "?address=" + address.replace(" ", "%20") +
        "&city=" + city.replace(" ", "%20") +
        "&state=" + state +
        "&bedrooms=" + str(beds) +
        "&bathrooms=" + str(baths) +
        "&squareFootage=" + str(sqft) +
        "&compCount=10"
    )
    try:
        res = requests.get(url, headers={"X-Api-Key": RENTCAST_KEY}, timeout=15)
        if res.status_code != 200:
            return [], None
        data = res.json()
        cutoff = datetime.datetime.now() - datetime.timedelta(days=max_days)
        comps = []
        for c in data.get("comparables", []):
            if not c.get("price"):
                continue
            c_sqft = c.get("squareFootage") or 0
            if c_sqft and not (sqft_min <= c_sqft <= sqft_max):
                continue
            removed = c.get("removedDate", "")
            status = c.get("status", "")
            if status == "Inactive" and removed:
                try:
                    if datetime.datetime.strptime(removed[:10], "%Y-%m-%d") < cutoff:
                        continue
                except Exception:
                    pass
            comps.append({
                "address": c.get("formattedAddress", "").split(",")[0],
                "price": c.get("price"),
                "sqft": c_sqft,
                "beds": c.get("bedrooms"),
                "baths": c.get("bathrooms"),
                "dom": c.get("daysOnMarket"),
                "status": status,
                "removed_date": removed,
            })
        return comps, data.get("price")
    except Exception as e:
        print("RentCast error:", e)
        return [], None


def get_comp_data(address, city, state, beds, baths, sqft, subject_price):
    stages = [
        (0.15, 90,  beds, baths),
        (0.15, 180, beds, baths),
        (0.15, 365, beds, baths),
        (0.30, 180, beds, baths),
        (0.30, 365, beds, baths),
        (0.40, 365, beds, baths),
        (0.40, 365, beds, 0),
        (0.40, 365, 0,    0),
    ]
    best_comps = []
    best_avm = None
    for i, (sqft_pct, max_days, use_beds, use_baths) in enumerate(stages):
        comps, avm = _fetch_comps_attempt(
            address, city, state,
            use_beds or beds, use_baths or baths,
            sqft, subject_price, sqft_pct, max_days
        )
        if avm:
            best_avm = avm
        if len(comps) > len(best_comps):
            best_comps = comps
        if len(comps) >= 2:
            print(f"Comps: {len(comps)} found at stage {i+1} (sqft+-{int(sqft_pct*100)}%, {max_days}d)")
            break
    if not best_comps:
        print("Comps: none found after all stages")
        return None
    # Deduplicate comps by address and sqft+price+status fingerprint
    seen_addr = set()
    seen_fp = set()
    deduped = []
    for c in best_comps:
        addr = c.get("address", "").strip().lower()
        sqft_r = round((c.get("sqft", 0) or 0) / 25) * 25
        fp = (sqft_r, c.get("price", 0), c.get("status", ""))
        if addr in seen_addr or fp in seen_fp:
            continue
        seen_addr.add(addr)
        seen_fp.add(fp)
        deduped.append(c)
    return {"avm": best_avm, "subject_price": subject_price, "comps": deduped[:5]}
def build_label(comp):
    beds = comp.get("beds", "?")
    baths = comp.get("baths", "?")
    sqft = comp.get("sqft", "?")
    dom = comp.get("dom", "?")
    status = comp.get("status", "")
    addr = comp.get("address", "")
    outcome = "SOLD " + str(dom) + "d" if status == "Inactive" else str(status).upper() + " " + str(dom) + "d"
    return addr + " (" + str(beds) + "/" + str(baths) + " - " + str(sqft) + "sf - " + outcome + ")"

def build_color(comp):
    status = comp.get("status", "")
    dom = comp.get("dom", 0) or 0
    if status == "Active" and dom > 180:
        return "#990000"
    elif status == "Active":
        return "#CC3333"
    else:
        return "#4A90D9"

def build_bar_label(comp):
    price = "$" + "{:,}".format(comp["price"])
    removed = comp.get("removed_date", "")
    if removed and len(removed) >= 10:
        date = removed[:10]
        return price + " (" + date + ")"
    return price

def generate_chart_image(comp_data, output_path, subject_beds=None, subject_baths=None, subject_sqft=None, subject_dom=None):
    subject_price = comp_data["subject_price"]
    avm = comp_data["avm"]
    comps = comp_data["comps"]
    subject_label = "YOUR LISTING"
    if subject_beds and subject_baths and subject_sqft and subject_dom:
        subject_label = "YOUR LISTING (" + str(subject_beds) + "/" + str(subject_baths) + " - " + str(subject_sqft) + "sf - " + str(subject_dom) + "d)"
    labels = [subject_label, "Market Value Est."] + [build_label(c) for c in comps]
    data = [subject_price, avm] + [c["price"] for c in comps]
    colors = ["#D4AF37", "#C0C0C0"] + [build_color(c) for c in comps]
    bar_labels = ["$" + "{:,}".format(subject_price), "$" + "{:,}".format(avm)] + [build_bar_label(c) for c in comps]
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#0A0A0A")
    ax.set_facecolor("#0A0A0A")
    for spine in ax.spines.values():
        spine.set_edgecolor("#C9A84C")
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    bars = ax.bar(range(len(labels)), data, color=colors, width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9, color="white")
    ax.set_ylim(0, int((max(data) * 1.15) / 50000 + 1) * 50000)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(50000))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: "$" + str(int(x))))
    ax.set_title("Your Listing vs The Market", fontsize=16, pad=15, color="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="#C9A84C")
    for bar, label in zip(bars, bar_labels):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3000,
                label, ha="center", va="bottom", fontsize=7, fontweight="bold", color="white")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0A0A0A")
    plt.close()
    return output_path

if __name__ == "__main__":
    result = get_comp_data("2544 Bunkerton Drive", "Fort Worth", "TX", 3, 2, 1445, 320000)
    if result:
        path = "/Users/danielvega/Desktop/comp_chart.png"
        generate_chart_image(result, path)
        print("Chart saved to:", path)
        subprocess.run(["open", path])

def generate_comp_narrative(comp_data, claude_key):
    subject_price = comp_data["subject_price"]
    avm = comp_data["avm"]
    comps = comp_data["comps"]
    gap = subject_price - avm
    sold = [c for c in comps if c["status"] == "Inactive"]
    active = [c for c in comps if c["status"] == "Active"]
    sold_doms = [c["dom"] for c in sold if c.get("dom")]
    avg_sold_dom = int(sum(sold_doms) / len(sold_doms)) if sold_doms else None
    sold_prices = [c["price"] for c in sold]
    avg_sold_price = int(sum(sold_prices) / len(sold_prices)) if sold_prices else None
    context = "Subject price: $" + str(subject_price) + ". Market value estimate: $" + str(avm) + ". Gap: $" + str(gap) + " above market."
    if avg_sold_price:
        context += " Average sold comp price: $" + str(avg_sold_price) + "."
    if avg_sold_dom:
        context += " Average days on market for sold comps: " + str(avg_sold_dom) + " days."
    if active:
        context += " There is " + str(len(active)) + " active competing listing(s) priced lower."
    prompt = "You are writing page 3 of a real estate marketing audit being dropped at a sellers door. They just read page 2 which explained their marketing failures. Now they are looking at a bar chart comparing their listing price to sold comps and a market value estimate. Write exactly 2 short paragraphs. No headers. No bullet points. No bold. No em dashes. Paragraph 1: Narrate what the chart is showing. Reference the bars visually without naming specific addresses or prices. Tell them their home is priced above what the market has been paying. Be direct but not harsh. Do not blame them. Paragraph 2: Tell them what the sold homes had in common - they were priced where the market was. Connect a small price adjustment combined with better marketing to getting their home sold. End with quiet confidence not a sales pitch. Keep it under 120 words total. Write in the same warm direct voice as the audit they just read. MARKET DATA: " + context
    import requests
    headers = {"x-api-key": claude_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {"model": "claude-sonnet-4-6", "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}
    try:
        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=30)
        return res.json().get("content", [{}])[0].get("text", "")
    except:
        return ""
