
from app.models import Property, User
from app.normalization import normalize_property_type


def _property_to_dict(p: Property) -> dict:
    return {
        "property_id": p.property_id,
        "user_id": p.user_id,
        "property_type": p.property_type,
        "normalized_type": p.normalized_type,
        "sub_type": p.sub_type,
        "location": p.location,
        "area_sqft": p.area_sqft,
        "current_estimated_value_inr": p.current_estimated_value_inr,
        "purchase_price_inr": p.purchase_price_inr,  # may be None - that's honest, not a bug
        "annual_rent_inr": p.annual_rent_inr,
        "occupancy_status": p.occupancy_status,
        "tenant_status": p.tenant_status,
        "gross_yield_percent": _yield_percent(p),
    }


def _yield_percent(p: Property):
    if not p.current_estimated_value_inr or p.annual_rent_inr is None:
        return None
    if p.current_estimated_value_inr == 0:
        return None
    return round((p.annual_rent_inr / p.current_estimated_value_inr) * 100, 2)


def search_properties(
    db,
    user_id: str,
    property_type: str | None = None,
    location_contains: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
) -> dict:
    """
    Filter a user's properties. property_type is matched against the
    NORMALIZED type (so "office" matches both "Commercial Office" and
    "Office" raw rows). location_contains is a case-insensitive substring
    match against the free-text location field.
    """
    rows = db.query(Property).filter(Property.user_id == user_id).all()

    if property_type:
        wanted = property_type.strip().lower()
        rows = [p for p in rows if (p.normalized_type or "").lower() == wanted]
    if location_contains:
        needle = location_contains.strip().lower()
        rows = [p for p in rows if needle in (p.location or "").lower()]
    if min_value is not None:
        rows = [p for p in rows if (p.current_estimated_value_inr or 0) >= min_value]
    if max_value is not None:
        rows = [p for p in rows if (p.current_estimated_value_inr or 0) <= max_value]

    return {"count": len(rows), "properties": [_property_to_dict(p) for p in rows]}


def _city_of(location):
    """City = last comma-separated part of 'Locality, City' (there is no city column)."""
    if not location:
        return "Unknown"
    return location.split(",")[-1].strip() or "Unknown"


def _locality_of(location):
    if not location:
        return "Unknown"
    return location.split(",")[0].strip() or "Unknown"


def _finish(buckets, total_value):
    """Adds share-of-portfolio and gross yield to every bucket so the model never does this maths."""
    for b in buckets.values():
        b["percent_of_portfolio_value"] = (
            round(b["value_inr"] / total_value * 100, 1) if total_value else None
        )
        b["gross_yield_percent"] = (
            round(b["annual_rent_inr"] / b["value_inr"] * 100, 2) if b["value_inr"] else None
        )


def _summarize(rows):
    """Single source of truth for portfolio maths (used by the real summary AND the what-if)."""
    total_value = sum((p.current_estimated_value_inr or 0) for p in rows)
    total_rent = sum((p.annual_rent_inr or 0) for p in rows)
    by_type, by_city = {}, {}
    for p in rows:
        bt = by_type.setdefault(p.normalized_type or "Unknown", {"count": 0, "value_inr": 0, "annual_rent_inr": 0})
        bc = by_city.setdefault(_city_of(p.location), {"count": 0, "value_inr": 0, "annual_rent_inr": 0, "localities": [], "types": {}})
        for b in (bt, bc):
            b["count"] += 1
            b["value_inr"] += p.current_estimated_value_inr or 0
            b["annual_rent_inr"] += p.annual_rent_inr or 0
        bc["localities"].append(_locality_of(p.location))
        t = p.normalized_type or "Unknown"
        bc["types"][t] = bc["types"].get(t, 0) + 1
    _finish(by_type, total_value)
    _finish(by_city, total_value)
    return {
        "property_count": len(rows),
        "total_value_inr": total_value,
        "total_annual_rent_inr": total_rent,
        "gross_yield_percent": round(total_rent / total_value * 100, 2) if total_value else None,
        "by_type": by_type,
        "by_city": by_city,
    }


def portfolio_summary(db, user_id: str) -> dict:
    """
    Total value, total rent, overall gross yield, and breakdowns by normalized
    property type AND by city (count, value, rent, share of portfolio, gross yield,
    localities). Covers "what does my portfolio look like", "how much is retail",
    "where are my properties" and yield questions in one call.
    """
    rows = db.query(Property).filter(Property.user_id == user_id).all()
    return {"user_id": user_id, **_summarize(rows)}


def highest_rent_property(db, user_id: str):
    rows = db.query(Property).filter(Property.user_id == user_id).all()
    rows = [p for p in rows if p.annual_rent_inr]
    if not rows:
        return None
    best = max(rows, key=lambda p: p.annual_rent_inr)
    return _property_to_dict(best)


def extreme_value_property(db, user_id: str, mode: str = "highest"):
    """mode: 'highest' or 'lowest', by current_estimated_value_inr."""
    rows = db.query(Property).filter(Property.user_id == user_id).all()
    rows = [p for p in rows if p.current_estimated_value_inr is not None]
    if not rows:
        return None
    fn = max if mode == "highest" else min
    result = fn(rows, key=lambda p: p.current_estimated_value_inr)
    return _property_to_dict(result)


def compare_segments(db, user_id: str, segment_a: str, segment_b: str) -> dict:
    """
    Compare two normalized property types head-to-head for one user, e.g.
    compare_segments(db, "U001", "Retail", "Office").
    """
    summary = portfolio_summary(db, user_id)
    by_type = summary["by_type"]
    empty = {"count": 0, "value_inr": 0, "annual_rent_inr": 0, "percent_of_portfolio_value": 0, "gross_yield_percent": None}
    return {
        "user_id": user_id,
        segment_a: by_type.get(segment_a, dict(empty)),
        segment_b: by_type.get(segment_b, dict(empty)),
    }


def simulate_exclusion(db, user_id: str, exclude_property_ids: list) -> dict:
    """
    Read-only what-if: recompute the summary as if the given property_ids did not
    exist. Nothing is written to the database; the result is flagged hypothetical.
    """
    excluded = set(exclude_property_ids)
    rows = db.query(Property).filter(Property.user_id == user_id).all()
    rows = [p for p in rows if p.property_id not in excluded]
    return {
        "user_id": user_id,
        "excluded_property_ids": exclude_property_ids,
        "hypothetical": True,
        **_summarize(rows),
    }


def _next_property_id(db) -> str:
    existing = [pid for (pid,) in db.query(Property.property_id).all()]
    numbers = []
    for pid in existing:
        digits = "".join(ch for ch in pid if ch.isdigit())
        if digits:
            numbers.append(int(digits))
    next_n = (max(numbers) + 1) if numbers else 1
    return f"P{next_n:03d}"


def create_property(
    db,
    user_id: str,
    property_type: str,
    location: str,
    current_estimated_value_inr: float,
    sub_type: str = None,
    area_sqft: float = None,
    annual_rent_inr: float = 0,
    occupancy_status: str = None,
    tenant_status: str = None,
) -> dict:
    if db.get(User, user_id) is None:
        raise ValueError(f"Unknown user_id: {user_id}")

    prop = Property(
        property_id=_next_property_id(db),
        user_id=user_id,
        property_type=property_type,
        sub_type=sub_type,
        normalized_type=normalize_property_type(property_type),
        location=location,
        area_sqft=area_sqft,
        current_estimated_value_inr=current_estimated_value_inr,
        purchase_price_inr=None,
        annual_rent_inr=annual_rent_inr,
        occupancy_status=occupancy_status,
        tenant_status=tenant_status,
        ownership_percent=100,
        status="Active",
    )
    db.add(prop)
    db.commit()
    return _property_to_dict(prop)


def update_property(db, property_id: str, fields: dict) -> dict:
    """
    fields is a dict of column_name -> new_value, e.g.
    {"current_estimated_value_inr": 125000000}.
    Raises ValueError for an unknown property_id or an unrecognized field,
    rather than silently ignoring a typo'd field name.
    """
    prop = db.get(Property, property_id)
    if prop is None:
        raise ValueError(f"Unknown property_id: {property_id}")

    allowed = {
        "property_type", "sub_type", "location", "area_sqft",
        "current_estimated_value_inr", "purchase_price_inr", "annual_rent_inr",
        "occupancy_status", "tenant_status",
    }
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Cannot update field: {key}")
        setattr(prop, key, value)

    if "property_type" in fields:
        prop.normalized_type = normalize_property_type(prop.property_type)

    db.commit()
    return _property_to_dict(prop)
