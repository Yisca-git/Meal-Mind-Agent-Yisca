"""Tool names, descriptions and JSON schemas, shared by the API harness and the SDK server."""

SYSTEM_PROMPT = (
    "You are Meal-Mind, a concise kitchen assistant that plans dinners and shopping for the user. "
    "Reply in the user's language. Use the tools for every fact about their preferences, plan, pantry "
    "and shopping list; never invent them. Use English singular lowercase ingredient names in tool calls. "
    "Save any stated allergy, diet, dislike or household size with save_preference. "
    "If a request conflicts with a saved preference, do not do it: say which preference blocks it and "
    "offer a safe alternative. Keep answers short."
)

_STR = {"type": "string"}

TOOL_SPECS = [
    {"name": "save_preference",
     "description": "Remember a user preference. key: allergies|dislikes|notes (appended), diet (vegetarian|vegan|none), servings (integer).",
     "input_schema": {"type": "object", "properties": {"key": _STR, "value": _STR}, "required": ["key", "value"]}},
    {"name": "recall_preferences",
     "description": "Read saved preferences. Omit keys for all.",
     "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": _STR}}}},
    {"name": "search_recipes",
     "description": "Search the recipe book (already filtered by saved preferences). Max 5 results: id, name, minutes, veg.",
     "input_schema": {"type": "object", "properties": {
         "query": _STR, "ingredients": {"type": "array", "items": _STR},
         "max_minutes": {"type": "integer"}, "limit": {"type": "integer"}}}},
    {"name": "lookup_external_recipe",
     "description": "Search TheMealDB on the internet for new recipe ideas. Results can be planned with add_to_meal_plan.",
     "input_schema": {"type": "object", "properties": {"query": _STR}, "required": ["query"]}},
    {"name": "add_to_meal_plan",
     "description": "Put a recipe in a slot (replaces the slot). day: sun|mon|tue|wed|thu|fri|sat. meal: breakfast|lunch|dinner. Blocked if it conflicts with preferences.",
     "input_schema": {"type": "object", "properties": {"day": _STR, "meal": _STR, "recipe_id": _STR},
                      "required": ["day", "meal", "recipe_id"]}},
    {"name": "get_meal_plan",
     "description": "Current meal plan, one line per slot.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "update_pantry",
     "description": "Add (default) or remove pantry items. Items: name, optional qty and unit (g, ml, pcs, tbsp, tsp, kg, l).",
     "input_schema": {"type": "object", "properties": {
         "items": {"type": "array", "items": {"type": "object", "properties": {
             "name": _STR, "qty": {"type": "number"}, "unit": _STR}, "required": ["name"]}},
         "mode": {"type": "string", "enum": ["add", "remove"]}}, "required": ["items"]}},
    {"name": "build_shopping_list",
     "description": "Build and save the shopping list for the planned meals, scaled to servings, minus what the pantry covers.",
     "input_schema": {"type": "object", "properties": {}}},
]
