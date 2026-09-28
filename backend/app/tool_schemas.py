
from app.models import Property
from app import tools

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": (
                "Search the current user's properties by normalized type (Retail, Office, "
                "Residential), a location substring, and/or a value range. Returns full "
                "property details including value, rent, occupancy and gross yield."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "property_type": {"type": "string", "description": "Normalized type: Retail, Office, or Residential"},
                    "location_contains": {"type": "string", "description": "Case-insensitive substring, e.g. 'Mumbai' or 'Bandra'"},
                    "min_value": {"type": "number", "description": "Minimum current_estimated_value_inr, inclusive"},
                    "max_value": {"type": "number", "description": "Maximum current_estimated_value_inr, inclusive"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "portfolio_summary",
            "description": (
                "Get the current user's full portfolio summary: total value, total annual "
                "rent, and a breakdown by normalized property type with each type's share of "
                "the portfolio. Use for 'what does my portfolio look like', 'how much is "
                "retail', 'total value' style questions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "highest_rent_property",
            "description": "Find the current user's property with the highest annual rent (vacant/self-occupied properties are excluded).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extreme_value_property",
            "description": "Find the current user's highest- or lowest-value property by current_estimated_value_inr.",
            "parameters": {
                "type": "object",
                "properties": {"mode": {"type": "string", "enum": ["highest", "lowest"]}},
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_segments",
            "description": "Compare two normalized property types head-to-head for the current user (count, value, rent, % of portfolio each).",
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_a": {"type": "string", "description": "Retail, Office, or Residential"},
                    "segment_b": {"type": "string", "description": "Retail, Office, or Residential"},
                },
                "required": ["segment_a", "segment_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_exclusion",
            "description": (
                "READ-ONLY what-if: recompute the current user's portfolio summary as if the "
                "given property_ids did not exist. Does NOT modify any data. Use this whenever "
                "the user asks a hypothetical question like 'what if I exclude/sold X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exclude_property_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "property_id values to exclude, e.g. ['P001']",
                    },
                },
                "required": ["exclude_property_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_property",
            "description": (
                "Add a new property to the current user's portfolio. WRITES to the database. "
                "Only call once the user has clearly asked to add a property with at least "
                "type, location, and value."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "property_type": {"type": "string", "description": "Retail, Office, or Residential"},
                    "location": {"type": "string", "description": "Format: 'Locality, City'"},
                    "current_estimated_value_inr": {"type": "number"},
                    "sub_type": {"type": "string"},
                    "area_sqft": {"type": "number"},
                    "annual_rent_inr": {"type": "number", "description": "Defaults to 0 if not given (vacant/self-occupied)"},
                    "occupancy_status": {"type": "string", "description": "Tenanted, Vacant, or Self-occupied"},
                    "tenant_status": {"type": "string", "description": "Yes or No"},
                },
                "required": ["property_type", "location", "current_estimated_value_inr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_property",
            "description": (
                "Update fields on an existing property. WRITES to the database. You must "
                "first identify the correct property_id (e.g. via search_properties) before "
                "calling this - never guess an ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "string", "description": "e.g. 'P001'"},
                    "fields": {
                        "type": "object",
                        "description": 'Column name -> new value, e.g. {"current_estimated_value_inr": 125000000}',
                    },
                },
                "required": ["property_id", "fields"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict, user_id: str, db) -> dict:
    """Dispatches a model-requested tool call to the real function, injecting/verifying user_id."""
    if name == "search_properties":
        return tools.search_properties(db, user_id, **arguments)
    if name == "portfolio_summary":
        return tools.portfolio_summary(db, user_id)
    if name == "highest_rent_property":
        result = tools.highest_rent_property(db, user_id)
        return result if result is not None else {"message": "No rent-generating properties found."}
    if name == "extreme_value_property":
        result = tools.extreme_value_property(db, user_id, **arguments)
        return result if result is not None else {"message": "No properties found."}
    if name == "compare_segments":
        return tools.compare_segments(db, user_id, **arguments)
    if name == "simulate_exclusion":
        return tools.simulate_exclusion(db, user_id, **arguments)
    if name == "create_property":
        return tools.create_property(db, user_id=user_id, **arguments)
    if name == "update_property":
        prop_id = arguments["property_id"]
        prop = db.get(Property, prop_id)
        if prop is None:
            raise ValueError(f"Unknown property_id: {prop_id}")
        if prop.user_id != user_id:
            raise PermissionError("Cannot update a property that doesn't belong to this user.")
        return tools.update_property(db, prop_id, arguments["fields"])
    raise ValueError(f"Unknown tool: {name}")
