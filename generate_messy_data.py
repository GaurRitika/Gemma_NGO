import pandas as pd
import random
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

def generate_messy_ngo_data():
    data = []
    
    # Generate 15 distinct baseline users
    baselines = []
    for i in range(15):
        baselines.append({
            "donor_id": f"DONOR-{(i+1)*100}",
            "full_name": fake.name(),
            "contact_email": fake.email().lower(),
            "phone_number": "+" + fake.msisdn()[:11],
            "registration_date": fake.date_this_decade().isoformat(),
            "donation_amount": round(random.uniform(10, 500), 2)
        })

    # Add Baselines
    for row in baselines:
        # Add pure rows
        if random.random() > 0.5:
            data.append(dict(row))
        
        # Add HEAVILY Corrupted rows to trigger [STANDARDIZE], [HANDLE_MISSING], [DEDUPLICATE]
        dirty = dict(row)
        r = random.random()
        
        # 1. Messy Name (needs strip/lowercase logic)
        if r > 0.3: dirty["full_name"] = f"   {dirty['full_name'].upper()}  "
        
        # 2. Messy Email (needs lowercase and strip)
        if r > 0.5: dirty["contact_email"] = dirty["contact_email"].upper() + " "
        elif r > 0.8: dirty["contact_email"] = None # force missing handling
        
        # 3. Messy Phone (needs regex / e164 formatting)
        if dirty["phone_number"] and r > 0.4:
            raw = dirty["phone_number"].replace("+", "")
            dirty["phone_number"] = f"({raw[:3]}) {raw[3:6]}-{raw[6:]} ext {random.randint(10,99)}"
            
        # 4. Messy Dates (needs datetime parsing)
        if r > 0.6: dirty["registration_date"] = dirty["registration_date"].replace("-", "/")
        elif r > 0.85: dirty["registration_date"] = "13/13/2021" # Totally invalid date
        
        # 5. Missing Amount
        if r > 0.7: dirty["donation_amount"] = None

        data.append(dirty)

    # Add completely fake spam entries (bot rows) to trigger intelligent drops
    for _ in range(5):
        data.append({
            "donor_id": f"TEMP-{random.randint(1000, 9999)}",
            "full_name": "UNKNOWN VOLUNTEER",
            "contact_email": f"spam_bot{random.randint(1,99)}@offline.temp",
            "phone_number": "+00000000000",
            "registration_date": "1970-01-01",
            "donation_amount": 0.00
        })

    # Shuffle everything so it's chaotic
    random.shuffle(data)
    
    df = pd.DataFrame(data)
    df.to_csv("SUPER_MESSY_NGO_DONORS.csv", index=False)
    print("✅ Created SUPER_MESSY_NGO_DONORS.csv")

if __name__ == "__main__":
    generate_messy_ngo_data()
