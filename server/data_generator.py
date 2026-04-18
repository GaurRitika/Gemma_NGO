import pandas as pd
import numpy as np
from faker import Faker
import random

fake = Faker()
Faker.seed(None)
np.random.seed(None)
random.seed(None)

# Conflict resolution priority rules for hard task
CONFLICT_RULES = {
    "email":  "prefer_volunteer_portal",   # Portal email is canonical
    "phone":  "prefer_donation_forms",    # Donation forms has fresher phone data
    "donor_id": "prefer_volunteer_portal",
}

_MISTAKE_DOMAINS = ["unverified-entry.local", "offline-form.temp", "no-email.xyz", "placeholder.co"]
_MISTAKE_NAMES   = ["Unknown Volunteer", "Missing Name", "Temp Entry", "TBD Info"]

def generate_bot_row():
    """Realistic-looking messy/anomaly row with subtle anomalies (bad domain, sequential-ish ID, bad phone)."""
    local = fake.user_name() + str(random.randint(1, 99))          # e.g.  john42
    domain = random.choice(_MISTAKE_DOMAINS)                           # shady domain
    return {
        "donor_id": f"TEMP{random.randint(10000, 99999)}",        # looks like an ID but TEMP prefix
        "name":        random.choice(_MISTAKE_NAMES),
        "email":       f"{local}@{domain}",                        # valid format, bad domain
        "signup_date": "1970-01-01",                               # epoch date — suspicious
        "phone":       "+" + "0" * 11                              # all-zeros phone
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
            "donor_id": f"DONOR_{1000+i}",
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
        "sources": {"donation_forms": pd.DataFrame(messy_rows)},
        "hidden_truth": {"donation_forms": pd.DataFrame(truth)},
        "schema": {
            "donor_id": "string",
            "name": "string (stripped)",
            "email": "string (lowercase, stripped)",
            "signup_date": "string ISO 8601 or empty",
            "phone": "string E.164 format (+1...) or empty"
        }
    }

def generate_medium_task():
    """Task 2: 2 data sources with severe duplicates and missing data."""
    t1 = generate_easy_task()
    df_truth = t1["hidden_truth"]["donation_forms"].copy()
    
    # Second chaotic source
    truth2 = create_base_truth(20)
    messy2 = correlate_truth(truth2)
    for _ in range(5): messy2.append(generate_bot_row())
    
    df_truth = pd.concat([df_truth, pd.DataFrame(truth2)]).drop_duplicates(subset=["email"]).reset_index(drop=True)
    
    return {
        "sources": {"legacy_ngo_db": pd.DataFrame(messy2).sample(frac=1).reset_index(drop=True), "donation_forms": t1["sources"]["donation_forms"]},
        "hidden_truth": {"merged_output": df_truth},
        "schema": t1["schema"]
    }

def _apply_conflict_rules(truth_list):
    """
    Build per-donor ground truth by applying CONFLICT_RULES priority logic.
    Priority order: Volunteer Portal > Donation Forms > Legacy NGO DB.
    """
    resolved = []
    for r in truth_list:
        # Start with base truth values
        row = {"donor_id": r["donor_id"], "email": r["email"], "phone": r["phone"]}
        resolved.append(row)
    return resolved

def generate_hard_task():
    """Task 3: 3-way merge conflict with full chaos engine and explicit conflict rules."""
    truth = create_base_truth(60)

    volunteer_portal = []
    donation_forms  = []
    legacy     = []

    # donation_forms_phones maps donor_id -> fresh phone used in donation_forms
    wl_phones = {}

    for r in truth:
        # --- Volunteer Portal: canonical email, mostly reliable phone ---
        sf_phone = r["phone"] if random.random() > 0.3 else None
        volunteer_portal.append({"donor_id": r["donor_id"], "email": r["email"], "phone": sf_phone})

        # --- Donation Forms: fresh phone (different from Portal), missing ID ~20% ---
        fresh_phone = "+" + fake.msisdn()                           # intentionally different
        wl_phones[r["donor_id"]] = fresh_phone                  # remember for truth building
        wl_cid  = r["donor_id"] if random.random() > 0.2 else None
        wl_ph   = fresh_phone if random.random() > 0.4 else None   # sometimes missing
        donation_forms.append({"donor_id": wl_cid, "email": r["email"], "phone": wl_ph})

        # --- Legacy NGO DB: old ID format, uppercased email, old phone ---
        old_cid = r["donor_id"].replace("DONOR_", "OLD-") if r["donor_id"] else None
        legacy.append({
            "legacy_id":     old_cid,
            "contact_email": r["email"].upper() if r["email"] else None,
            "home_phone":    r["phone"]
        })

    df_sf  = pd.DataFrame(volunteer_portal).sample(frac=0.9).reset_index(drop=True)
    df_wl  = pd.DataFrame(donation_forms).sample(frac=0.8).reset_index(drop=True)
    df_leg = pd.DataFrame(legacy).sample(frac=0.85).reset_index(drop=True)

    # --- Inject realistic-looking anomilies into all 3 sources ---
    for _ in range(5):
        bdom = random.choice(_MISTAKE_DOMAINS)
        bloc = fake.user_name() + str(random.randint(1, 99))
        df_sf.loc[len(df_sf)]  = {"donor_id": f"TEMP{random.randint(10000,99999)}",
                                   "email": f"{bloc}@{bdom}", "phone": "+00000000000"}
        df_wl.loc[len(df_wl)]  = {"donor_id": None,
                                   "email": f"{fake.user_name()}99@{bdom}", "phone": None}
        df_leg.loc[len(df_leg)] = {"legacy_id": f"TEMP{random.randint(10000,99999)}",
                                   "contact_email": f"BULK@{bdom.upper()}", "home_phone": "+00000000000"}

    # --- Build hidden truth using CONFLICT_RULES ---
    resolved_truth = []
    for r in truth:
        resolved_phone = wl_phones.get(r["donor_id"], r["phone"])  # Forms > Portal
        resolved_truth.append({
            "donor_id": r["donor_id"],   # prefer_volunteer_portal
            "email":       r["email"],          # prefer_volunteer_portal
            "phone":       resolved_phone,      # prefer_donation_forms
        })

    return {
        "sources": {
            "volunteer_portal": df_sf.sample(frac=1).reset_index(drop=True),
            "donation_forms":  df_wl.sample(frac=1).reset_index(drop=True),
            "legacy_ngo_db":  df_leg.sample(frac=1).reset_index(drop=True)
        },
        "hidden_truth": {"merged_output": pd.DataFrame(resolved_truth)},
        "conflict_rules": CONFLICT_RULES,
        "schema": {
            "donor_id": "string",
            "email":       "string (lowercase, canonical from Volunteer Portal)",
            "phone":       "string (E.164, prefer Donation Forms when available)"
        }
    }

def get_task_data(task_id: str):
    if task_id == "t1": return generate_easy_task()
    if task_id == "t2": return generate_medium_task()
    if task_id == "t3": return generate_hard_task()
    raise ValueError(f"Unknown task {task_id}")
