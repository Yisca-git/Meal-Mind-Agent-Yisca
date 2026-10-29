"""Dietary tagging and preference-conflict detection, shared by local and external recipes."""

ALLERGEN_KEYWORDS = {
    "nuts": ("almond", "walnut", "pecan", "pistachio", "cashew", "hazelnut", "peanut", "macadamia"),
    "dairy": ("milk", "butter", "cheese", "parmesan", "feta", "cream", "yogurt", "yoghurt", "mozzarella"),
    "eggs": ("egg", "mayonnaise"),
    "gluten": ("flour", "pasta", "noodle", "bread", "bun", "pita", "couscous", "spaghetti"),
    "sesame": ("sesame", "tahini"),
}
MEAT_KEYWORDS = (
    "chicken", "beef", "lamb", "pork", "bacon", "ham", "sausage", "turkey", "mince",
    "fish", "salmon", "tuna", "shrimp", "prawn", "anchovy", "gelatin",
)
ALLERGY_ALIASES = {
    "nut": "nuts", "nuts": "nuts", "tree nuts": "nuts", "peanut": "nuts", "peanuts": "nuts",
    "milk": "dairy", "dairy": "dairy", "lactose": "dairy",
    "egg": "eggs", "eggs": "eggs",
    "gluten": "gluten", "wheat": "gluten",
    "sesame": "sesame",
}


def normalize_allergy(value):
    key = value.strip().lower()
    return ALLERGY_ALIASES.get(key, key)


def _flat(names):
    # "coconut milk" is not dairy and "coconut" is not a nut.
    return [n.lower().replace("coconut milk", "coconut").replace("eggplant", "aubergine") for n in names]


def tags_for(ingredient_names):
    names = _flat(ingredient_names)
    allergens = {a for a, kws in ALLERGEN_KEYWORDS.items() if any(k in n for n in names for k in kws)}
    meat = any(k in n for n in names for k in MEAT_KEYWORDS)
    return {"allergens": sorted(allergens), "vegetarian": not meat}


def conflicts(ingredient_names, prefs):
    """Human-readable reasons this recipe breaks the saved preferences (empty list = safe)."""
    tags = tags_for(ingredient_names)
    reasons = []
    for allergy in prefs.get("allergies", []):
        if normalize_allergy(allergy) in tags["allergens"]:
            reasons.append(allergy)
    diet = prefs.get("diet", "")
    if diet in ("vegetarian", "vegan") and not tags["vegetarian"]:
        reasons.append("not vegetarian")
    if diet == "vegan" and {"dairy", "eggs"} & set(tags["allergens"]):
        reasons.append("not vegan")
    names = " ".join(ingredient_names).lower()
    for dislike in prefs.get("dislikes", []):
        if dislike.lower() in names:
            reasons.append(f"dislikes {dislike}")
    return reasons
