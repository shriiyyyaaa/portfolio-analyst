"""
Normalization layer for the dataset's inconsistent property_type labels.

OBSERVED INCONSISTENCY (see assignment Section 6.2 / DATASET.md):
Office-type properties appear under TWO different raw property_type values:
  - "Commercial Office"  (P002, P007, P008)
  - "Office"             (P011)
Both have sub_type values like "Office", "Office floor" - they are the same
underlying category, just labelled inconsistently in the source data.

DECISION: we normalize both into a single category, "Office", and keep the
raw property_type/sub_type columns untouched in the DB for transparency/audit.
All analytical tools (aggregation, exposure %, comparisons) operate on
normalized_type, never on the raw property_type, so "office exposure"
questions give one consistent answer regardless of which raw label a row used.

Retail and Residential labels are consistent in the seed data as-is, so they
pass through unchanged. If new data introduces new inconsistent labels, add
the mapping here - this is the single place that decision lives.
"""

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
