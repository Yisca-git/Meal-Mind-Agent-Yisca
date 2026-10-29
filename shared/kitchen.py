"""Domain logic for Meal-Mind. Both harnesses call these methods; state lives in `state_dir` as JSON."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

from shared import safety

DATA_DIR = Path(__file__).parent / "data"
DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
MEALS = ("breakfast", "lunch", "dinner")
LIST_KEYS = ("allergies", "dislikes", "notes")
MEALDB_URL = "https://www.themealdb.com/api/json/v1/1/search.php?s="
UNIT_ALIASES = {"gram": "g", "grams": "g", "gr": "g", "piece": "pcs", "pieces": "pcs", "unit": "pcs", "units": "pcs",
                "tablespoon": "tbsp", "teaspoon": "tsp", "liter": "l", "litre": "l", "milliliter": "ml"}


class ToolError(Exception):
    """Raised for bad input or blocked actions; the harness turns it into an is_error tool_result."""


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def norm_name(name):
    n = name.strip().lower()
    if n.endswith("oes"):
        return n[:-2]
    if n.endswith("s") and not n.endswith(("ss", "us")):
        return n[:-1]
    return n


def norm_qty(qty, unit):
    unit = UNIT_ALIASES.get((unit or "").strip().lower(), (unit or "").strip().lower())
    if qty is None:
        return None, unit
    if unit == "kg":
        return qty * 1000, "g"
    if unit == "l":
        return qty * 1000, "ml"
    return qty, unit


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "meal-mind/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


class Kitchen:
    def __init__(self, state_dir, fetch_json=None):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._fetch = fetch_json or _fetch_json

    # ---- persistence ----
    def _load(self, name, default):
        path = self.dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def _save(self, name, data):
        (self.dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def prefs(self):
        return self._load("preferences.json", {})

    def plan(self):
        return self._load("meal_plan.json", [])

    def pantry(self):
        return self._load("pantry.json", {})

    def shopping(self):
        return self._load("shopping_list.json", {"items": [], "covered": []})

    def recipes(self):
        local = json.loads((DATA_DIR / "recipes.json").read_text(encoding="utf-8"))
        return {r["id"]: r for r in local} | self._load("external_cache.json", {})

    # ---- memory ----
    def save_preference(self, key, value):
        prefs = self.prefs()
        if key in LIST_KEYS:
            item = safety.normalize_allergy(value) if key == "allergies" else value.strip()
            if item not in prefs.setdefault(key, []):
                prefs[key].append(item)
        elif key == "diet":
            prefs[key] = value.strip().lower()
        elif key == "servings":
            try:
                prefs[key] = int(value)
            except (TypeError, ValueError):
                raise ToolError("servings must be an integer")
        else:
            raise ToolError(f"unknown key '{key}'; use allergies, dislikes, notes, diet or servings")
        self._save("preferences.json", prefs)
        return {"saved": key, "now": prefs[key]}

    def recall_preferences(self, keys=None):
        prefs = self.prefs()
        return {k: v for k, v in prefs.items() if not keys or k in keys}

    # ---- recipes ----
    def _visible(self, recipe):
        return not safety.conflicts([i[0] for i in recipe["ingredients"]], self.prefs())

    def _brief(self, r):
        return {"id": r["id"], "name": r["name"], "min": r.get("minutes"),
                "veg": safety.tags_for([i[0] for i in r["ingredients"]])["vegetarian"]}

    def search_recipes(self, query="", ingredients=None, max_minutes=None, limit=5):
        words = query.lower().split()
        wanted = [norm_name(i) for i in (ingredients or [])]
        pantry = set(self.pantry())
        scored, hidden = [], []
        for r in self.recipes().values():
            names = [i[0] for i in r["ingredients"]]
            text = " ".join([r["name"].lower()] + names)
            if max_minutes and (r.get("minutes") or 0) > max_minutes:
                continue
            if words and not all(w in text for w in words):
                continue
            hits = sum(1 for w in wanted if any(w in n for n in names))
            if wanted and not hits:
                continue
            if not self._visible(r):
                hidden.append(r["name"])
                continue
            scored.append((hits + sum(1 for n in names if n in pantry), r))
        scored.sort(key=lambda s: -s[0])
        out = {"results": [self._brief(r) for _, r in scored[:min(limit, 5)]]}
        if hidden:
            out["hidden"] = f"{len(hidden)} hidden by saved preferences"
        return out

    def lookup_external_recipe(self, query):
        try:
            data = self._fetch(MEALDB_URL + urllib.parse.quote(query))
        except Exception as exc:
            raise ToolError(f"external lookup failed: {type(exc).__name__}")
        cache, results, hidden = self._load("external_cache.json", {}), [], 0
        for meal in (data.get("meals") or [])[:6]:
            ings = []
            for n in range(1, 21):
                name = (meal.get(f"strIngredient{n}") or "").strip()
                if name:
                    ings.append([norm_name(name), None, (meal.get(f"strMeasure{n}") or "").strip()])
            recipe = {"id": f"ext-{meal['idMeal']}", "name": meal["strMeal"], "servings": None,
                      "minutes": None, "ingredients": ings, "category": meal.get("strCategory")}
            if not self._visible(recipe):
                hidden += 1
                continue
            cache[recipe["id"]] = recipe
            results.append({**self._brief(recipe), "ing": [i[0] for i in ings][:12]})
            if len(results) == 3:
                break
        self._save("external_cache.json", cache)
        out = {"results": results}
        if hidden:
            out["hidden"] = f"{hidden} hidden by saved preferences"
        return out

    # ---- meal plan ----
    def add_to_meal_plan(self, day, meal, recipe_id):
        day, meal = day.lower(), meal.lower()
        if day not in DAYS or meal not in MEALS:
            raise ToolError(f"day must be one of {DAYS}, meal one of {MEALS}")
        recipe = self.recipes().get(recipe_id)
        if not recipe:
            raise ToolError(f"unknown recipe_id '{recipe_id}'; get ids from search_recipes")
        reasons = safety.conflicts([i[0] for i in recipe["ingredients"]], self.prefs())
        if reasons:
            raise ToolError(f"blocked: '{recipe['name']}' conflicts with saved preferences ({', '.join(reasons)})")
        plan = [p for p in self.plan() if (p["day"], p["meal"]) != (day, meal)]
        plan.append({"day": day, "meal": meal, "recipe_id": recipe_id, "name": recipe["name"]})
        plan.sort(key=lambda p: (DAYS.index(p["day"]), MEALS.index(p["meal"])))
        self._save("meal_plan.json", plan)
        return {"planned": f"{day}/{meal}: {recipe['name']}", "total": len(plan)}

    def get_meal_plan(self):
        return {"plan": [f"{p['day']}/{p['meal']}: {p['name']}" for p in self.plan()]}

    # ---- pantry & shopping ----
    def update_pantry(self, items, mode="add"):
        pantry = self.pantry()
        for item in items:
            name = norm_name(item["name"])
            qty, unit = norm_qty(item.get("qty"), item.get("unit"))
            if mode == "remove":
                pantry.pop(name, None)
                continue
            cur = pantry.get(name)
            if cur and qty is not None and cur["qty"] is not None and cur["unit"] == unit:
                qty += cur["qty"]
            pantry[name] = {"qty": qty, "unit": unit}
        self._save("pantry.json", pantry)
        return {"pantry": sorted(pantry)}

    def check_pantry(self):
        return {"pantry": [f"{n} {v['qty'] if v['qty'] is not None else ''}{v['unit']}".strip()
                           for n, v in sorted(self.pantry().items())]}

    def needs(self):
        """Aggregate ingredient needs for the planned meals, scaled to the saved servings."""
        recipes, servings, need = self.recipes(), self.prefs().get("servings"), {}
        for p in self.plan():
            r = recipes[p["recipe_id"]]
            scale = servings / r["servings"] if servings and r.get("servings") else 1
            for name, qty, unit in r["ingredients"]:
                key = (name, unit)
                need[key] = (need.get(key, 0) + qty * scale) if qty is not None else None
        return need

    def build_shopping_list(self):
        pantry, items, covered = self.pantry(), [], []
        for (name, unit), qty in sorted(self.needs().items()):
            have = pantry.get(name)
            if have and (have["qty"] is None or qty is None or have["unit"] != unit):
                covered.append(name)
                continue
            if have and have["unit"] == unit:
                if have["qty"] >= qty:
                    covered.append(name)
                    continue
                qty -= have["qty"]
            items.append([name, round(qty, 1) if qty is not None else None, unit])
        result = {"items": items, "covered": sorted(set(covered))}
        self._save("shopping_list.json", result)
        return result


def render_memory_md(prefs):
    """CLAUDE.md body for the SDK harness: the same preferences, as project memory."""
    lines = ["# Meal-Mind memory", ""]
    lines += [f"- {k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in prefs.items()]
    return "\n".join(lines) + "\n"
