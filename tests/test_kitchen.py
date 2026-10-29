import pytest

from shared import safety
from shared.kitchen import Kitchen, ToolError


def test_preferences_persist_across_instances(state):
    Kitchen(state).save_preference("allergies", "Peanuts")
    assert Kitchen(state).recall_preferences()["allergies"] == ["nuts"]


def test_search_hides_recipes_that_conflict_with_preferences(state):
    k = Kitchen(state)
    k.save_preference("allergies", "nuts")
    k.save_preference("diet", "vegetarian")
    result = k.search_recipes(limit=20)
    names = [r["name"] for r in result["results"]]
    assert "Pistachio Cake" not in names and "Chicken Soup" not in names
    assert "hidden" in result and len(result["results"]) <= 5


def test_plan_blocks_conflicting_recipe(state):
    k = Kitchen(state)
    k.save_preference("allergies", "nuts")
    with pytest.raises(ToolError, match="blocked"):
        k.add_to_meal_plan("thu", "dinner", "r05")
    assert k.plan() == []


def test_plan_slot_is_replaced_not_duplicated(state):
    k = Kitchen(state)
    k.add_to_meal_plan("sun", "dinner", "r01")
    k.add_to_meal_plan("sun", "dinner", "r02")
    assert [p["recipe_id"] for p in k.plan()] == ["r02"]


def test_shopping_list_scales_and_subtracts_pantry(state):
    k = Kitchen(state)
    k.save_preference("servings", "4")
    k.add_to_meal_plan("sun", "dinner", "r01")  # written for 2 -> doubled
    assert ["pasta", 400.0, "g"] in k.build_shopping_list()["items"]
    k.update_pantry([{"name": "Pasta", "qty": 1, "unit": "kg"}, {"name": "tomatoes", "qty": 300, "unit": "g"}])
    result = k.build_shopping_list()
    assert "pasta" in result["covered"]
    assert ["tomato", 500.0, "g"] in result["items"]  # 800 needed - 300 in pantry


def test_external_lookup_uses_injected_fetch_and_filters(state):
    meals = {"meals": [
        {"idMeal": "1", "strMeal": "Bacon Pasta", "strCategory": "Pasta", "strIngredient1": "Bacon", "strMeasure1": "1 pack"},
        {"idMeal": "2", "strMeal": "Garlic Pasta", "strCategory": "Pasta", "strIngredient1": "Spaghetti", "strMeasure1": "200g"}]}
    k = Kitchen(state, fetch_json=lambda url: meals)
    k.save_preference("diet", "vegetarian")
    result = k.lookup_external_recipe("pasta")
    assert [r["id"] for r in result["results"]] == ["ext-2"] and "hidden" in result
    assert k.add_to_meal_plan("wed", "dinner", "ext-2")["total"] == 1


def test_external_lookup_failure_is_a_tool_error(state):
    def boom(url):
        raise OSError("offline")
    with pytest.raises(ToolError, match="external lookup failed"):
        Kitchen(state, fetch_json=boom).lookup_external_recipe("pasta")


def test_safety_does_not_flag_coconut_milk_or_eggplant():
    assert safety.tags_for(["coconut milk", "eggplant"])["allergens"] == []
