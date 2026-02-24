import os, glob, base64, httpx, json, sys, re
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
CLAUDE_KEY = "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"

EARL_SYSTEM = (
    "You are Earl, a real estate agent writing a personal note to a homeowner whose listing has not sold. "
    "TONE: Warm and direct, like a knowledgeable neighbor. Not corporate. "
    "NEVER USE: em dashes, bullet points, bold headers, leverage, optimize, utilize, seamlessly, game-changer, robust, streamline, transform, innovative, synergy, empower, unlock, delve, crucial, pivotal, vibrant, dynamic, reprice, drop the price, adjust the price, position the price, capture the bracket. "
    "You will write exactly 3 labeled sections: P1, P2, P4. "
    "P1: Exactly one sentence. Start with I know having your listing sit for [X] days is frustrating. Nothing else. "
    "P2: Start with I took a look at your listing. Include the exact price sentence provided. Then list confirmed marketing issues with real numbers. No price advice anywhere. "
    "P4: One warm sentence about the home or location. "
    "Output format: P1 then P2 then P4. Nothing else. "
    "If example audits are provided, match that exact tone, length, and style."
)

PARA3 = "Here is what I would do differently. I reverse prospect to 600 KW agents in my office and 4,500 across DFW. I syndicate to 455 websites. Most agents wait for buyers to find the listing. We find the buyers first."
PARA5 = "I will be in your area next week. Let me know if you want to walk through a game plan. I have included a market analysis and listing guide so you can see where we would position this."

def build_price_sentence(listing_data):
    try:
        raw = listing_data.get("price", "").replace("$","").replace(",","").strip()
        price_num = int(float(raw))
        thousands = price_num // 1000
        last_digit = thousands % 10
        if last_digit == 0 or last_digit == 5:
            return ""
        round_below = (thousands // 5) * 5 * 1000
        return f"At ${price_num:,}, you are just above the ${round_below//1000}k search filter, meaning 3-4 percent of buyers never see your listing."
    except:
        return ""

def get_similar_audits(listing_data):
    try:
        from rag_system import get_similar_audits as rag_search
        examples = rag_search(listing_data, n=3)
        if examples:
            print(f"Found {len(examples)} similar audits in RAG.")
        return examples
    except Exception as e:
        print("RAG not available: " + str(e))
        return []

def run_earl_audit(mls):
    photo_dir = "./photos/" + mls
    json_path = photo_dir + "/listing_data.json"

    if not os.path.exists(json_path):
        print("No listing data found. Run the scraper first.")
        return

    with open(json_path) as f:
        listing_data = json.load(f)
    print("Loaded listing data: " + str(listing_data))

    image_files = sorted(glob.glob(photo_dir + "/grid_part_*.jpg"))
    if not image_files:
        print("No photos found.")
        return

    print("Loading " + str(len(image_files)) + " grid images...")
    parts = []
    for img_path in image_files:
        with Image.open(img_path) as img:
            img.thumbnail((1200, 1200))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}})

    parts.insert(0, {"text": "Scan these MLS listing photos. Only report what you can actually confirm you see. Look for: floor plan image present or absent, virtual tour screenshot present or absent, photo quality issues, photo sequence flow problems, lead photo subject. A virtual tour is only confirmed if you see a Matterport or 3D tour screenshot. Do not guess."})

    print("Gemini scanning photos...")
    try:
        with httpx.Client(timeout=120.0) as client:
            res = client.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_KEY, json={"contents": [{"parts": parts}]})
            data = res.json()
            if "candidates" not in data:
                print("Gemini error: " + str(data))
                return
            visual_notes = data["candidates"][0]["content"]["parts"][0]["text"]
            print("Gemini done.")
    except Exception as e:
        print("Gemini error: " + str(e))
        return

    price_sentence = build_price_sentence(listing_data)
    similar_audits = get_similar_audits(listing_data)

    rag_context = ""
    if similar_audits:
        rag_context = " Here are examples of approved audits to match in tone and style: " + " | ".join(similar_audits[:2])

    print("Earl writing report...")
    human_prompt = (
        "CONFIRMED listing data: " + json.dumps(listing_data) +
        ". Visual observations: " + visual_notes +
        ". P2 MUST start with this exact price sentence if present: " + price_sentence +
        rag_context +
        ". Write P1, P2, P4 only. No price advice anywhere."
    )

    try:
        with httpx.Client(timeout=60.0) as client:
            res = client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 800, "system": EARL_SYSTEM,
                      "messages": [{"role": "user", "content": human_prompt}]})
            data = res.json()
            if "content" not in data:
                print("Claude error: " + str(data))
                return
            raw = data["content"][0]["text"]

            p1_match = re.search(r"\*?\*?P1\*?\*?[:\s]+(.*?)(?=\*?\*?P2|$)", raw, re.DOTALL)
            p2_match = re.search(r"\*?\*?P2\*?\*?[:\s]+(.*?)(?=\*?\*?P4|$)", raw, re.DOTALL)
            p4_match = re.search(r"\*?\*?P4\*?\*?[:\s]+(.*?)$", raw, re.DOTALL)

            p1 = p1_match.group(1).strip().replace("**","") if p1_match else ""
            p2 = p2_match.group(1).strip().replace("**","") if p2_match else ""
            p4 = p4_match.group(1).strip().replace("**","") if p4_match else ""

            report = p1 + "\n\n" + p2 + "\n\n" + PARA3 + "\n\n" + p4 + "\n\n" + PARA5

            print("")
            print("=" * 50)
            print("EARLS REPORT - MLS# " + mls)
            print("=" * 50)
            print("")
            print(report)

            with open(photo_dir + "/earl_report.txt", "w") as f:
                f.write(report)
            print("")
            print("Report saved to " + photo_dir + "/earl_report.txt")
            print("To approve and save to RAG: python3 approve.py " + mls)
            return report
    except Exception as e:
        print("Claude error: " + str(e))

if __name__ == "__main__":
    mls = sys.argv[1] if len(sys.argv) > 1 else "21057509"
    run_earl_audit(mls)
