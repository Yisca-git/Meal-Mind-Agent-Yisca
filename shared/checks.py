"""pass/fail checks over persisted state (and, where unavoidable, reply text)."""
from shared import safety
from shared.kitchen import Kitchen


def _tools(turns, session=None):
    return [t for r in turns if session in (None, r["session"]) for t in r["tools"]]


def evaluate(check, state_dir, turns):
    kitchen, kind = Kitchen(state_dir), check["type"]
    if kind == "memory_contains":
        have = kitchen.prefs().get(check["key"], [])
        have = have if isinstance(have, list) else [have]
        return check["value"] in have
    if kind == "plan_count":
        return sum(1 for p in kitchen.plan() if p["meal"] == check["meal"]) >= check["min"]
    if kind == "plan_safe":
        recipes = kitchen.recipes()
        plan = kitchen.plan()
        for p in plan:
            tags = safety.tags_for([i[0] for i in recipes[p["recipe_id"]]["ingredients"]])
            if "nuts" in tags["allergens"] or not tags["vegetarian"]:
                return False
        return bool(plan)
    if kind == "plan_lacks":
        return not any(check["name_contains"] in p["name"].lower() for p in kitchen.plan())
    if kind == "tool_called":
        used = _tools(turns, check.get("session"))
        return sum(used.count(t) for t in check["tools"]) >= check.get("min", 1)
    if kind == "shopping_excludes_pantry":
        listed = {i[0] for i in kitchen.shopping()["items"]}
        need = kitchen.needs()
        covered = {n for n, v in kitchen.pantry().items()
                   if need.get((n, v["unit"])) is not None and v["qty"] is not None and v["qty"] >= need[(n, v["unit"])]}
        return bool(covered) and not (covered & listed)
    if kind == "reply_mentions":
        reply = next(r["reply"] for r in turns if r["turn"] == check["turn"]).lower()
        return any(w.lower() in reply for w in check["any"])
    raise ValueError(f"unknown check type {kind}")
