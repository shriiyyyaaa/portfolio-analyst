"""
Validates the tool functions against the assignment's OWN sample_requests.csv
expectations (R001-R006), using an isolated in-memory database so it never
touches your real portfolio.db.

Run from backend/ (with venv active):
    python test_tools.py
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import tools
from app.seed import load_properties, load_users

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)
db = Session()

load_users(db)
load_properties(db)

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        print(f"PASS - {label}")
        passed += 1
    else:
        print(f"FAIL - {label}")
        failed += 1


# R001: owner=U001; property_type=Retail -> P001, P003
r001 = tools.search_properties(db, "U001", property_type="Retail")
check("R001 returns exactly P001 and P003",
      r001["count"] == 2 and {p["property_id"] for p in r001["properties"]} == {"P001", "P003"})

# R002: owner=U001; value > 10 crore (100,000,000)
r002 = tools.search_properties(db, "U001", min_value=100_000_001)
check("R002 returns only P001 (>10cr)",
      r002["count"] == 1 and r002["properties"][0]["property_id"] == "P001")

# R003: owner=U002; location contains Mumbai -> P004, P005 (not P006, Alibaug)
r003 = tools.search_properties(db, "U002", location_contains="Mumbai")
check("R003 returns exactly P004 and P005",
      r003["count"] == 2 and {p["property_id"] for p in r003["properties"]} == {"P004", "P005"})

# R004: highest annual rent for U003 -> P007 (16,800,000)
r004 = tools.highest_rent_property(db, "U003")
check("R004 highest rent is P007", r004 is not None and r004["property_id"] == "P007")

# R005: add 3000 sqft retail property in Indiranagar worth 4.2cr for U004
r005 = tools.create_property(
    db, user_id="U004", property_type="Retail", location="Indiranagar, Bengaluru",
    area_sqft=3000, current_estimated_value_inr=42_000_000,
)
check("R005 creates a new property with correct fields",
      r005["property_type"] == "Retail" and r005["current_estimated_value_inr"] == 42_000_000
      and r005["area_sqft"] == 3000)

# R006: update P001's value to 12.5cr
r006 = tools.update_property(db, "P001", {"current_estimated_value_inr": 125_000_000})
check("R006 updates P001's value", r006["current_estimated_value_inr"] == 125_000_000)

# Bonus checks exercising things NOT in the sample requests, since the brief
# explicitly warns sample_requests.csv is not the full feature set:

# Normalization: "office" should match both "Commercial Office" and "Office" raw rows
office = tools.search_properties(db, "U003", property_type="Office")
check("Normalization groups 'Commercial Office' rows under 'Office'",
      office["count"] == 2 and {p["property_id"] for p in office["properties"]} == {"P007", "P008"})

office_u004 = tools.search_properties(db, "U004", property_type="Office")
check("Normalization also matches raw 'Office' label (P011)",
      office_u004["count"] == 1 and office_u004["properties"][0]["property_id"] == "P011")

# Missing purchase_price_inr should surface as None, not 0
summary = tools.portfolio_summary(db, "U001")
p001 = next(p for p in tools.search_properties(db, "U001")["properties"] if p["property_id"] == "P001")
check("Missing purchase_price_inr stays None (not defaulted to 0)", p001["purchase_price_inr"] is None)

# What-if: excluding Bandra retail property (P001) from U001's portfolio
before = tools.portfolio_summary(db, "U001")
whatif = tools.simulate_exclusion(db, "U001", ["P001"])
check("simulate_exclusion reduces total value and doesn't touch the DB",
      whatif["total_value_inr"] == before["total_value_inr"] - 125_000_000
      and tools.portfolio_summary(db, "U001")["total_value_inr"] == before["total_value_inr"])

# Geography + precomputed yields (added after the "Mumbai" hallucination found in testing)
s3 = tools.portfolio_summary(db, "U003")
check("by_city: U003 has 2 in Gurugram and 1 in Noida",
      s3["by_city"]["Gurugram"]["count"] == 2 and s3["by_city"]["Noida"]["count"] == 1)
check("by_city lists actual localities (nothing left for the model to guess)",
      set(s3["by_city"]["Gurugram"]["localities"]) == {"Golf Course Road", "Sector 29"})
check("Per-type gross yield is precomputed (Office 4.73, Retail 7.27)",
      s3["by_type"]["Office"]["gross_yield_percent"] == 4.73
      and s3["by_type"]["Retail"]["gross_yield_percent"] == 7.27)

check("by_city shows the types in each city (Gurugram: 1 Office + 1 Retail; Noida: 1 Office)",
      s3["by_city"]["Gurugram"]["types"] == {"Office": 1, "Retail": 1}
      and s3["by_city"]["Noida"]["types"] == {"Office": 1})

print(f"\n{passed} passed, {failed} failed")
