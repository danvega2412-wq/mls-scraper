import sys, subprocess

if len(sys.argv) < 2:
    print("Usage: python3 run.py <MLS_NUMBER>")
    sys.exit(1)

mls = sys.argv[1]
print("=" * 50)
print(f"LISTING LAB - MLS# {mls}")
print("=" * 50)

print("\nStep 1: Scraping listing data and photos...")
result = subprocess.run(["python3", "working_scraper.py", mls])
if result.returncode != 0:
    print("Scraper failed.")
    sys.exit(1)

print("\nStep 2: Running Earl's audit...")
subprocess.run(["python3", "earl_forensics.py", mls])
print("\nTo approve this audit: python3 approve.py " + mls)
