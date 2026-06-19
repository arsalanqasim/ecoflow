import csv
import os
import random
from datetime import datetime, timedelta

def generate_sample_shipments():
    # Setup path
    output_dir = os.path.join("data", "sample_inputs")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "shipments_2025_q1_q2.csv")

    # Define possible values
    suppliers = [
        {"name": "Acme Steel Co.", "origin": "CN"},
        {"name": "Bengal Aluminum Ltd.", "origin": "IN"},
        {"name": "Euro Metalworks", "origin": "DE"},
        {"name": "US Alloys Corp", "origin": "US"}
    ]
    
    # Products mapped to HS code
    products = [
        {"hs_code": "720810", "unit": "tonnes"},
        {"hs_code": "730630", "unit": "tonnes"},
        {"hs_code": "760110", "unit": "tonnes"},
        {"hs_code": "760410", "unit": "tonnes"}
    ]

    start_date = datetime(2025, 1, 1)
    
    headers = ["shipment_date", "supplier_name", "hs_code", "quantity", "unit", "origin_country", "dest_country"]
    
    # Generate 50 shipment entries
    rows = []
    for _ in range(50):
        supplier = random.choice(suppliers)
        product = random.choice(products)
        
        # Steel is imported in larger quantities (e.g. 50-200 tonnes), Aluminum in smaller (e.g. 10-50 tonnes)
        if product["hs_code"] in ["720810", "730630"]:
            quantity = round(random.uniform(50.0, 250.0), 2)
        else:
            quantity = round(random.uniform(10.0, 80.0), 2)
            
        date_offset = random.randint(0, 180) # 6 months range
        ship_date = start_date + timedelta(days=date_offset)
        
        rows.append({
            "shipment_date": ship_date.strftime("%Y-%m-%d"),
            "supplier_name": supplier["name"],
            "hs_code": product["hs_code"],
            "quantity": quantity,
            "unit": product["unit"],
            "origin_country": supplier["origin"],
            "dest_country": "DE" # EU destination
        })
        
    # Sort by date
    rows.sort(key=lambda x: x["shipment_date"])
    
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Generated {len(rows)} sample shipments and saved to {file_path}")

if __name__ == "__main__":
    generate_sample_shipments()
