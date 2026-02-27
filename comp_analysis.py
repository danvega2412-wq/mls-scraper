import requests
import json

RENTCAST_KEY = "dda29a2c21934d8399af4c76678dab2c"

def get_comp_data(address, city, state, beds, baths, sqft, subject_price):
    url = (
        "https://api.rentcast.io/v1/avm/value"
        "?address=" + address.replace(' ', '%20') +
        "&city=" + city.replace(' ', '%20') +
        "&state=" + state +
        "&bedrooms=" + str(beds) +
        "&bathrooms=" + str(baths) +
        "&squareFootage=" + str(sqft) +
        "&compCount=8"
    )
    res = requests.get(url, headers={"X-Api-Key": RENTCAST_KEY}, timeout=15)
    if res.status_code != 200:
        print("RentCast error:", res.status_code, res.text)
        return None
    data = res.json()
    raw_comps = []
    for c in data.get("comparables", []):
        if not c.get("price"):
            continue
        raw_comps.append({
            "address": c.get("formattedAddress", "").split(",")[0],
            "price": c.get("price"),
            "sqft": c.get("squareFootage"),
            "beds": c.get("bedrooms"),
            "baths": c.get("bathrooms"),
            "dom": c.get("daysOnMarket"),
            "status": c.get("status"),
        })
    filtered = []
    for c in raw_comps:
        diff = abs(c["price"] - subject_price) / subject_price
        if diff <= 0.20:
            filtered.append(c)
        else:
            print("  [OUTLIER REMOVED] " + c["address"] + " $" + str(c["price"]) + " (" + str(round(diff*100)) + "% off)")
    return {
        "avm": data.get("price"),
        "subject_price": subject_price,
        "comps": filtered[:5]
    }

def build_label(comp):
    beds = comp.get("beds", "?")
    baths = comp.get("baths", "?")
    sqft = comp.get("sqft", "?")
    dom = comp.get("dom", "?")
    status = comp.get("status", "")
    addr = comp.get("address", "")
    if status == "Inactive":
        outcome = "SOLD " + str(dom) + "d"
    else:
        outcome = str(status).upper() + " " + str(dom) + "d"
    return addr + " (" + str(beds) + "/" + str(baths) + " - " + str(sqft) + "sf - " + outcome + ")"

def build_color(comp):
    status = comp.get("status", "")
    dom = comp.get("dom", 0) or 0
    if status == "Active" and dom > 180:
        return "#CC0000"
    elif status == "Active":
        return "#FF8C00"
    else:
        return "#002349"

def generate_quickchart_url(comp_data):
    if not comp_data or not comp_data["comps"]:
        return ""
    subject_price = comp_data["subject_price"]
    avm = comp_data["avm"]
    comps = comp_data["comps"]
    all_prices = [subject_price, avm] + [c["price"] for c in comps]
    y_min = int(min(all_prices) * 0.97)
    y_max = int(max(all_prices) * 1.03)
    labels = ["YOUR LISTING", "Market Value Est."] + [build_label(c) for c in comps]
    data = [subject_price, avm] + [c["price"] for c in comps]
    bg_colors = ["#D4AF37", "#C0C0C0"] + [build_color(c) for c in comps]
    chart = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Price",
                "data": data,
                "backgroundColor": bg_colors,
                "barPercentage": 0.75,
                "categoryPercentage": 0.85
            }]
        },
        "options": {
            "plugins": {
                "legend": {"display": False},
                "title": {"display": True, "text": "Your Listing vs The Market", "font": {"size": 16}}
            },
            "scales": {
                "y": {
                    "min": y_min,
                    "max": y_max,
                    "ticks": {"callback": "(val) => '$' + val.toLocaleString()"}
                }
            }
        }
    }
    config_str = json.dumps(chart)
    return "https://quickchart.io/chart?c=" + requests.utils.quote(config_str) + "&width=900&height=450&bkg=%23ffffff"


def generate_chart_image(comp_data):
    """
    Same as generate_quickchart_url: returns a QuickChart URL for the comp bar chart.
    Exists so audit_generator (and others) can import generate_chart_image.
    """
    return generate_quickchart_url(comp_data)


if __name__ == "__main__":
    import subprocess
    result = get_comp_data("2544 Bunkerton Drive", "Fort Worth", "TX", 3, 2, 1445, 320000)
    if result:
        print("AVM: $" + str(result["avm"]))
        print("Subject: $" + str(result["subject_price"]))
        print("Comps after outlier filter:")
        for c in result["comps"]:
            print("  " + build_label(c) + " - $" + str(c["price"]))
        url = generate_quickchart_url(result)
        print("Chart URL:")
        print(url)
        subprocess.run(["open", url])