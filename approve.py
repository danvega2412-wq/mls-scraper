import sys, json, os
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")

if len(sys.argv) < 2:
    print("Usage: python3 approve.py <MLS_NUMBER>")
    sys.exit(1)

mls = sys.argv[1]
photo_dir = "./photos/" + mls
report_path = photo_dir + "/earl_report.txt"
data_path = photo_dir + "/listing_data.json"

if not os.path.exists(report_path):
    print("No report found. Run earl_forensics.py first.")
    sys.exit(1)

report = open(report_path).read()
listing_data = json.load(open(data_path))

print("Saving to RAG...")
from rag_system import save_approved_audit
result = save_approved_audit(mls, listing_data, report)
if result:
    print("Approved and saved to Pinecone.")
else:
    print("Save failed.")
