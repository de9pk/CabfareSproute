"""
location_helper.py
──────────────────
Preset Jaipur locations for quick selection in the dashboard.
Add or modify locations as needed.
"""

# Popular Jaipur pickup/drop locations
JAIPUR_LOCATIONS = {
    "🏛️  Hawa Mahal":               "Hawa Mahal, Jaipur, Rajasthan",
    "✈️  Jaipur International Airport": "Jaipur International Airport, Sanganer",
    "🚉  Jaipur Railway Station":    "Jaipur Junction Railway Station",
    "🎓  JECRC University":          "JECRC University, Vidhani, Jaipur",
    "🛍️  Pink Square Mall":          "Pink Square Mall, Jhotwara, Jaipur",
    "🏥  SMS Hospital":              "Sawai Man Singh Hospital, Jaipur",
    "🎓  University of Rajasthan":   "University of Rajasthan, JLN Marg, Jaipur",
    "🏟️  SMS Stadium":               "Sawai Mansingh Stadium, Jaipur",
    "🛒  World Trade Park":          "World Trade Park, Malviya Nagar, Jaipur",
    "🏖️  Amer Fort":                 "Amer Fort, Amer, Jaipur",
    "🌆  Vaishali Nagar":            "Vaishali Nagar, Jaipur, Rajasthan",
    "🏢  Sitapura Industrial Area":  "Sitapura Industrial Area, Jaipur",
    "🎭  Jawahar Kala Kendra":       "Jawahar Kala Kendra, Jaipur",
    "🏦  Civil Lines":               "Civil Lines, Jaipur, Rajasthan",
    "🌿  Mansarovar":                "Mansarovar, Jaipur, Rajasthan",
    "🏘️  Malviya Nagar":             "Malviya Nagar, Jaipur, Rajasthan",
}


def get_location_names() -> list[str]:
    """Return list of friendly location names for dropdown."""
    return list(JAIPUR_LOCATIONS.keys())


def get_location_query(friendly_name: str) -> str:
    """Convert friendly name to search query string."""
    return JAIPUR_LOCATIONS.get(friendly_name, friendly_name)


def get_all_locations() -> dict:
    return JAIPUR_LOCATIONS
