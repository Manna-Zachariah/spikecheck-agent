"""Tool: find_alternatives

Argument: {"food": "white bread"}
Lists foods in the same category with a lower GI, closest GI first.
The closest food changes the meal the least, but it may not lower GL
enough. That is why the agent must test swaps and sometimes try another.
"""

from tools.argument_checks import validate_food_argument
from tools.food_table import (find_food, load_food_table, table_path_from,
                              tool_error_result, unknown_food_result)


def validate(argument):
    return validate_food_argument(argument)


def run(argument, context):
    valid, note = validate(argument)
    if not valid:
        return {"ok": False, "message": note, "data": {}}

    foods, aliases, error = load_food_table(table_path_from(context))
    if error != "":
        return tool_error_result(error)

    food = find_food(argument["food"], foods, aliases)
    if food is None:
        return unknown_food_result(argument["food"], argument["food"] + " is not in the food table.")

    alternatives = []
    if food["gi"] is not None:
        for name in foods:
            other = foods[name]
            if other["category"] != food["category"]:
                continue
            if other["gi"] is None or other["gi"] >= food["gi"]:
                continue
            alternatives.append({
                "food": other["name"],
                "gi": other["gi"],
                "carbs_per_100g": other["carbs_per_100g"],
                "serving_g": other["serving_g"],
            })

    # Sort by GI from highest to lowest (closest to the original first).
    # A plain selection sort keeps the logic visible.
    sorted_alternatives = []
    while len(alternatives) > 0:
        best = alternatives[0]
        for candidate in alternatives:
            if candidate["gi"] > best["gi"]:
                best = candidate
        sorted_alternatives.append(best)
        alternatives.remove(best)

    if len(sorted_alternatives) == 0:
        message = "No lower-GI food in the same category is in the table."
    else:
        message = "Found " + str(len(sorted_alternatives)) + " lower-GI alternatives, closest first."

    return {
        "ok": True,
        "message": message,
        "data": {"food": food["name"], "category": food["category"], "alternatives": sorted_alternatives},
    }