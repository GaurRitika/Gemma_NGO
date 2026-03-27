import pandas as pd
import numpy as np
from faker import Faker
import random

fake = Faker()
Faker.seed(101)
np.random.seed(101)
random.seed(101)

def generate_bot_row():
    return {
        "customer_id": "???",
        "name": str(random.randint(10000, 99999)),
        "email": "not_an_email_address",
        "signup_date": "random_spam_text",
        "phone": "abcd"
    }

def correlate_truth(truth_list):
    """Deeply corrupts a row, making transformations genuinely required and sometimes dropping data."""
    messy = []
    
    for r in truth_list:
        dirty = dict(r)
        # 1. Missing Data Chaos (Missing emails/phones)
        if random.random() > 0.8: dirty["email"] = None
        if random.random() > 0.8: dirty["phone"] = None
        
        # 2. String Chaos
        if dirty["name"]:
            dirty["name"] = f"  {dirty['name']}  " if random.random() > 0.5 else dirty["name"].upper()
        if dirty["email"]:
            dirty["email"] = dirty["email"].upper() if random.random() > 0.5 else dirty["email"]
            
        # 3. Date Chaos
        date_rand = random.random()
        if date_rand > 0.85: dirty["signup_date"] = "??/??/????"
        elif date_rand > 0.70: dirty["signup_date"] = "2023-13-12" # Invalid Month
        elif date_rand > 0.55: dirty["signup_date"] = None
        else: dirty["signup_date"] = r["signup_date"][:10].replace("-", "/")
        
        # 4. Phone Chaos
        if dirty["phone"]:
            raw_phone = dirty["phone"].replace("+", "")
            prand = random.random()
            if prand > 0.85: dirty["phone"] = raw_phone + " ext. " + str(random.randint(10, 999))
            elif prand > 0.70: dirty["phone"] = f"({raw_phone[:3]}) {raw_phone[3:6]}-{raw_phone[6:]}"
            elif prand > 0.55: dirty["phone"] = "Invalid Number"
                
        messy.append(dirty)
        
        # 5. Deduplication Chaos (Fuzzy Matches, Nicknames)
        if random.random() > 0.75:
            dup = dict(dirty)
            # Nickname duplicate
            if r["name"] and len(r["name"].split()) > 1:
                dup["name"] = fake.first_name() + " " + r["name"].split()[-1]
            dup["email"] = None # Missing field in duplicate
            messy.append(dup)
            
    return messy

def create_base_truth(size=50):
    truth = []
    for i in range(size):
        truth.append({
            "customer_id": f"CUST_{1000+i}",
            "name": fake.name(),
            "email": fake.email().lower(),
            "signup_date": fake.date_this_decade().isoformat(),
            "phone": "+" + fake.msisdn()
        })
    return truth

def generate_easy_task():
    """Task 1: Clean, Dedup, and Drop Bots from 1 file"""
    truth = create_base_truth(40)
    messy_rows = correlate_truth(truth)
    
    # 6. Bot/Spam Outliers Injection
    for _ in range(8):
        messy_rows.append(generate_bot_row())
        
    random.shuffle(messy_rows)
    
    return {
        "sources": {"web_forms": pd.DataFrame(messy_rows)},
        "hidden_truth": {"web_forms": pd.DataFrame(truth)},
        "schema": {
            "customer_id": "string",
            "name": "string (stripped)",
            "email": "string (lowercase, stripped)",
            "signup_date": "string ISO 8601 or empty",
            "phone": "string E.164 format (+1...) or empty"
        }
    }

def generate_medium_task():
    """Task 2: 2 data sources with severe duplicates and missing data."""
    t1 = generate_easy_task()
    df_truth = t1["hidden_truth"]["web_forms"].copy()
    
    # Second chaotic source
    truth2 = create_base_truth(20)
    messy2 = correlate_truth(truth2)
    for _ in range(5): messy2.append(generate_bot_row())
    
    df_truth = pd.concat([df_truth, pd.DataFrame(truth2)]).drop_duplicates(subset=["email"]).reset_index(drop=True)
    
    return {
        "sources": {"legacy_db": pd.DataFrame(messy2).sample(frac=1).reset_index(drop=True), "web_forms": t1["sources"]["web_forms"]},
        "hidden_truth": {"merged_output": df_truth},
        "schema": t1["schema"]
    }

def generate_hard_task():
    """Task 3: 3-way merge conflict with full chaos engine."""
    truth = create_base_truth(60)
    
    salesforce = []
    web_leads = []
    legacy = []
    
    for r in truth:
        # Salesforce is generally mostly reliable, sometimes missing phone
        sf_phone = r["phone"] if random.random() > 0.3 else None
        salesforce.append({"customer_id": r["customer_id"], "email": r["email"], "phone": sf_phone})
        
        # Web leads has fresh emails but missing IDs 20% of the time, uses fake wrong phones
        wl_cid = r["customer_id"] if random.random() > 0.2 else None
        wl_phone = "+" + fake.msisdn() if random.random() > 0.5 else None
        web_leads.append({"customer_id": wl_cid, "email": r["email"], "phone": wl_phone})
        
        # Legacy DB uses old ID format and random junk
        old_cid = r["customer_id"].replace("CUST_", "OLD-") if r["customer_id"] else None
        legacy.append({"legacy_id": old_cid, "contact_email": r["email"].upper() if r["email"] else None, "home_phone": r["phone"]})
        
    df_sf = pd.DataFrame(salesforce).sample(frac=0.9).reset_index(drop=True)
    df_wl = pd.DataFrame(web_leads).sample(frac=0.8).reset_index(drop=True)
    df_leg = pd.DataFrame(legacy).sample(frac=0.85).reset_index(drop=True)
    
    # Inject bots into all 3
    for _ in range(5):
        df_sf.loc[len(df_sf)] = {"customer_id": "???", "email": "bot@spam", "phone": "000"}
        df_wl.loc[len(df_wl)] = {"customer_id": None, "email": "spam@bot", "phone": "111"}
        df_leg.loc[len(df_leg)] = {"legacy_id": "???", "contact_email": "bot", "home_phone": "222"}
    
    return {
        "sources": {"salesforce": df_sf.sample(frac=1).reset_index(drop=True), 
                    "web_leads": df_wl.sample(frac=1).reset_index(drop=True), 
                    "legacy_db": df_leg.sample(frac=1).reset_index(drop=True)},
        "hidden_truth": {"merged_output": pd.DataFrame(truth)},
        "schema": {
            "customer_id": "string",
            "email": "string",
            "phone": "string"
        }
    }

def get_task_data(task_id: str):
    if task_id == "t1": return generate_easy_task()
    if task_id == "t2": return generate_medium_task()
    if task_id == "t3": return generate_hard_task()
    raise ValueError(f"Unknown task {task_id}")
