

_RAW_TO_NORMALIZED = {
    "commercial office": "Office",
    "office": "Office",
    "retail": "Retail",
    "residential": "Residential",
}


def normalize_property_type(raw_property_type: str) -> str:
    """
    Map a raw property_type string to its normalized category.
    Unknown/new labels pass through title-cased rather than being dropped,
    so the system degrades gracefully instead of silently losing data.
    """
    if not raw_property_type:
        return "Unknown"
    key = raw_property_type.strip().lower()
    return _RAW_TO_NORMALIZED.get(key, raw_property_type.strip())
