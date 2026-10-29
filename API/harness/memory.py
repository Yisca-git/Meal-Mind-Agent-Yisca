"""Long-term memory: preferences.json (written by the save_preference tool). This file decides what to retrieve."""
from API.harness import trace


def essentials(kitchen):
    """Always-on safety facts: allergies, diet, household size. One short line."""
    prefs = kitchen.prefs()
    parts = [f"{k}: {', '.join(prefs[k]) if isinstance(prefs[k], list) else prefs[k]}"
             for k in ("allergies", "diet", "servings") if prefs.get(k)]
    return "; ".join(parts)


def relevant_notes(kitchen, user_text):
    """Dislikes and free notes are only retrieved when the user's message mentions them."""
    text = user_text.lower()
    prefs = kitchen.prefs()
    hits = [d for d in prefs.get("dislikes", []) if d.lower() in text]
    hits += [n for n in prefs.get("notes", []) if any(w in text for w in n.lower().split() if len(w) > 3)]
    if hits:
        trace("memory", f"retrieved {len(hits)} relevant notes")
    return hits
