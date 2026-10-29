import asyncio
import json
from pathlib import Path

from tests.conftest import FakeClient, calls, text

import shared.kitchen as kitchen_module
from API.agent import MealAgent
from shared import runner
from SDK.tools import build_server

ROOT = Path(__file__).resolve().parent.parent
MEALS = {"meals": [{"idMeal": "9", "strMeal": "Garlic Spaghetti", "strCategory": "Pasta",
                    "strIngredient1": "Spaghetti", "strMeasure1": "200g", "strIngredient2": "Garlic", "strMeasure2": "2 cloves"}]}

SCRIPT = [
    calls(("save_preference", {"key": "allergies", "value": "nuts"}),
          ("save_preference", {"key": "diet", "value": "vegetarian"}),
          ("save_preference", {"key": "servings", "value": "2"})), text("saved"),
    calls(("add_to_meal_plan", {"day": "sun", "meal": "dinner", "recipe_id": "r01"}),
          ("add_to_meal_plan", {"day": "mon", "meal": "dinner", "recipe_id": "r02"}),
          ("add_to_meal_plan", {"day": "tue", "meal": "dinner", "recipe_id": "r03"})), text("planned"),
    calls(("lookup_external_recipe", {"query": "pasta"})),
    calls(("add_to_meal_plan", {"day": "wed", "meal": "dinner", "recipe_id": "ext-9"})), text("added"),
    calls(("build_shopping_list", {})), text("list"),
    calls(("recall_preferences", {}), ("get_meal_plan", {})), text("אלרגיה לאגוזים, 4 ארוחות"),
    calls(("update_pantry", {"items": [{"name": "pasta", "qty": 500, "unit": "g"},
                                       {"name": "tomato", "qty": 1, "unit": "kg"}]})),
    calls(("build_shopping_list", {})), text("updated"),
    calls(("add_to_meal_plan", {"day": "thu", "meal": "dinner", "recipe_id": "r05"})), text("nuts are blocked"),
]


def test_full_scenario_with_scripted_client_passes_all_checks(state, monkeypatch):
    monkeypatch.setattr(kitchen_module, "_fetch_json", lambda url: MEALS)
    client = FakeClient(SCRIPT)
    scenario = json.loads((ROOT / "scenario.json").read_text(encoding="utf-8"))
    results = runner.run_scenario(
        scenario, lambda n, s: MealAgent(state, client, "claude-opus-5-5", "medium", n),
        state, "api", "claude-opus-5-5", "medium", runner.api_line_counts)
    failed = [c["id"] for c in results["checks"] if not c["passed"]]
    assert failed == [] and results["checks_passed"] == "8/8"
    assert len(results["turns"]) == 7 and results["totals"]["calls"] == len(SCRIPT)
    assert set(results["turns"][0]["tokens"]) == {"input", "cache_read", "cache_write", "output"}


def test_checks_fail_when_state_is_wrong(state):
    client = FakeClient([text("whatever")] * 7)
    scenario = json.loads((ROOT / "scenario.json").read_text(encoding="utf-8"))
    results = runner.run_scenario(
        scenario, lambda n, s: MealAgent(state, client, "claude-opus-5-5", "medium", n),
        state, "api", "claude-opus-5-5", "medium", runner.api_line_counts)
    assert not any(c["passed"] for c in results["checks"] if c["id"] in ("memory-allergy", "plan-dinners"))


def test_sdk_tools_are_registered_and_save_preference_writes_claude_md(state):
    from shared.kitchen import Kitchen
    kitchen, workspace = Kitchen(state), state / "ws"
    workspace.mkdir(parents=True)
    server = build_server(kitchen, workspace)
    assert server["name"] == "meal"
    from SDK.tools import _wrap
    from shared.tool_specs import TOOL_SPECS
    save = _wrap(kitchen, workspace, next(s for s in TOOL_SPECS if s["name"] == "save_preference"))
    out = asyncio.run(save.handler({"key": "allergies", "value": "nuts"}))
    assert out["is_error"] is False and "nuts" in (workspace / "CLAUDE.md").read_text(encoding="utf-8")
    bad = _wrap(kitchen, workspace, next(s for s in TOOL_SPECS if s["name"] == "add_to_meal_plan"))
    assert asyncio.run(bad.handler({"day": "x", "meal": "dinner", "recipe_id": "r01"}))["is_error"] is True


def test_line_counts_cover_every_harness_part():
    api, sdk = runner.api_line_counts(), runner.sdk_line_counts()
    for part in ("loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"):
        assert api[part] > 0
    for part in ("loop", "tools", "history", "memory", "context", "tokens"):
        assert sdk[part] > 0
    assert sdk["total"] < api["total"]
