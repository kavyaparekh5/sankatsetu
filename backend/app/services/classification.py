"""
Keyword-based disaster category classification.

Deliberately NOT an ML model: for a hackathon demo we need something that
is instant, deterministic, has zero external dependencies/API keys, and
is trivial to extend by editing a dict. Each incoming report's text is
scored against a keyword list per category; the category with the most
keyword hits wins. Ties are broken by keyword-list order below.
"""

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "flood": [
        "flood", "flooding", "flooded", "water level", "waterlogged",
        "waterlogging", "submerged", "rising water", "heavy rain",
        "heavy rainfall", "overflow", "drowning", "inundated",
    ],
    "fire": [
        "fire", "burning", "smoke", "blaze", "explosion", "flames",
        "caught fire", "gas leak",
    ],
    "medical": [
        "injured", "injury", "medical", "hospital", "ambulance",
        "unconscious", "bleeding", "sick", "illness", "disease",
        "outbreak", "casualty", "casualties", "wounded",
    ],
    "rescue": [
        "trapped", "stuck", "rescue", "stranded", "missing", "evacuate",
        "evacuation", "help needed", "rooftop", "swept away", "sos",
    ],
    "infrastructure": [
        "bridge collapse", "building collapse", "road damage",
        "power outage", "electricity", "power cut", "infrastructure",
        "road closed", "collapsed", "debris", "power lines", "blackout",
    ],
}


def classify(text: str) -> str:
    """Return the best-matching category for a report's text.

    Falls back to "uncategorized" when no keyword matches at all.
    """
    lowered = text.lower()

    best_category = "uncategorized"
    best_score = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lowered)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category
