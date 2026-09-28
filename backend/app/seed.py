
import csv
import os

from app.database import Base, SessionLocal, engine
from app.models import Property, User
from app.normalization import normalize_property_type

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _to_float(value):
    """Blank CSV cells become None (unknown), never 0 - see models.py docstring."""
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def load_users(db):
    path = os.path.join(DATA_DIR, "users.csv")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            user = db.get(User, row["user_id"])
            if user is None:
                user = User(user_id=row["user_id"])
                db.add(user)
            user.name = row["name"]
            user.city = row["city"]
            user.stated_preferences = row["preferences"]
            user.preferred_locations = row["preferred_locations"]
            user.portfolio_value_preference = row["portfolio_value_preference_inr"]
            count += 1
    db.commit()
    return count


def load_properties(db):
    path = os.path.join(DATA_DIR, "properties.csv")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            prop = db.get(Property, row["property_id"])
            if prop is None:
                prop = Property(property_id=row["property_id"])
                db.add(prop)
            prop.user_id = row["user_id"]
            prop.property_type = row["property_type"]
            prop.sub_type = row["sub_type"]
            prop.normalized_type = normalize_property_type(row["property_type"])
            prop.location = row["location"]
            prop.area_sqft = _to_float(row["area_sqft"])
            prop.current_estimated_value_inr = _to_float(row["current_estimated_value_inr"])
            prop.purchase_price_inr = _to_float(row["purchase_price_inr"])
            prop.annual_rent_inr = _to_float(row["annual_rent_inr"])
            prop.occupancy_status = row["occupancy_status"]
            prop.tenant_status = row["tenant_status"]
            prop.ownership_percent = _to_float(row["ownership_percent"])
            prop.status = row["status"]
            count += 1
    db.commit()
    return count


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        n_users = load_users(db)
        n_props = load_properties(db)
        print(f"Loaded {n_users} users and {n_props} properties.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
