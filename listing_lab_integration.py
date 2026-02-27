import comp_analysis

# --- SUBJECT PROPERTY CONFIGURATION ---
address = "2544 Bunkerton Dr"
city = "Little Elm"
state = "TX"
sqft = 1941
beds = 3
baths = 2
year_built = 2024
subject_price = 320000  # The "Anchor" for Location-Smart Math
rentcast_key = "PASTE_YOUR_KEY_HERE"

def run_gatsby_pipeline():
    print(f"Gatsby Engine: Running Page 3 Generation for {address}...")
    
    # Passing all required arguments, including the new subject_price
    comps = comp_analysis.get_comp_data(
        address, 
        city, 
        state, 
        beds, 
        baths, 
        sqft, 
        year_built, 
        rentcast_key, 
        subject_price
    )

    if comps:
        chart_url = comp_analysis.generate_quickchart_url(subject_price, comps)
        print("\n--- YOUR GATSBY CHART IS READY ---")
        print(chart_url)
        print("----------------------------------\n")
    else:
        print("\n[+] No comps found. Try widening the price or area parameters.")

if __name__ == "__main__":
    run_gatsby_pipeline()
