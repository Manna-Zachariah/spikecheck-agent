"""Tool: test_swap

Argument: {"items": [...the meal...], "replace": "white bread", "with": "chapati"}
Optional: "with_grams": a portion the user gave. Otherwise the table serving is used.

Python recalculates the meal with one food replaced and compares totals.
A swap PASSES only if meal GL drops by at least SWAP_TARGET_PERCENT (20%).
"""

from tools.argument_checks import is_number, validate_items, MAX_GRAMS
from tools.food_table import (find_food, load_food_table, table_path_from,
                              tool_error_result, unknown_food_result)
from tools.meal_math import calculate_meal, LOW_GL_MAX, SWAP_TARGET_PERCENT


def validate(argument):
    if type(argument) != dict:
        return False, "Argument must be a dictionary."
    for key in argument:
        if key not in ["items", "replace", "with", "with_grams"]:
            return False, "Unexpected key: " + str(key)
    for key in ["items", "replace", "with"]:
        if key not in argument:
            return False, "Argument needs items, replace and with."
    for key in ["replace", "with"]:
        if type(argument[key]) != str or argument[key].strip() == "":
            return False, key + " must be a food name."
    if "with_grams" in argument and argument["with_grams"] is not None:
        if not is_number(argument["with_grams"]):
            return False, "with_grams must be a number, or leave it out to use the table serving."
        if argument["with_grams"] <= 0 or argument["with_grams"] > MAX_GRAMS:
            return False, "with_grams must be more than 0 and at most " + str(MAX_GRAMS) + "."
    return validate_items(argument["items"])


def run(argument, context):
    valid, note = validate(argument)
    if not valid:
        return {"ok": False, "message": note, "data": {}}

    foods, aliases, error = load_food_table(table_path_from(context))
    if error != "":
        return tool_error_result(error)

    target = SWAP_TARGET_PERCENT
    if "swap_target_percent" in context:
        target = context["swap_target_percent"]

    old_food = find_food(argument["replace"], foods, aliases)
    new_food = find_food(argument["with"], foods, aliases)
    if new_food is None:
        return unknown_food_result(argument["with"],
                                   argument["with"] + " is not in the food table, so the swap cannot be tested.")

    before = calculate_meal(argument["items"], foods, aliases)
    if len(before["problems"]) > 0:
        return {
            "ok": False,
            "message": "The original meal has unknown foods or missing portions, so the swap cannot be compared.",
            "data": {"problem": before["problems"][0]["problem"], "problems": before["problems"]},
        }

    # Build the new meal: the same list, with one food replaced.
    new_items = []
    replaced = False
    new_grams = 0.0
    grams_note = ""
    for item in argument["items"]:
        item_food = find_food(item["food"], foods, aliases)
        if not replaced and old_food is not None and item_food["name"] == old_food["name"]:
            if "with_grams" in argument and argument["with_grams"] is not None:
                new_grams = float(argument["with_grams"])
                grams_note = "Used the portion the user gave."
            else:
                new_grams = new_food["serving_g"]
                grams_note = "Used the table serving size for " + new_food["name"] + "."
            new_items.append({"food": new_food["name"], "grams": new_grams})
            replaced = True
        else:
            new_items.append(item)

    if not replaced:
        return {
            "ok": False,
            "message": argument["replace"] + " is not one of the foods in this meal.",
            "data": {"problem": "not_in_meal", "problems": [{"food": argument["replace"], "problem": "not_in_meal"}]},
        }

    after = calculate_meal(new_items, foods, aliases)

    reduction = round(before["total_gl"] - after["total_gl"], 1)
    if before["total_gl"] > 0:
        reduction_percent = round(reduction / before["total_gl"] * 100, 1)
    else:
        reduction_percent = 0.0
    passed = reduction_percent >= target

    new_item = None
    for item in after["items"]:
        if item["food"] == new_food["name"]:
            new_item = item

    data = {
        "replace": old_food["name"],
        "with": new_food["name"],
        "with_grams": new_grams,
        "grams_note": grams_note,
        "before_total_gl": before["total_gl"],
        "after_total_gl": after["total_gl"],
        "reduction": reduction,
        "reduction_percent": reduction_percent,
        "target_percent": target,
        "passed": passed,
        "new_item_gl": new_item["gl"],
        "new_item_rating": new_item["rating"],
        "new_item_is_low": new_item["gl"] <= LOW_GL_MAX,
    }

    if passed:
        message = ("Swap PASSED: meal GL goes from " + str(before["total_gl"]) + " to "
                   + str(after["total_gl"]) + " (" + str(reduction_percent)
                   + "% lower, target " + str(target) + "%).")
    else:
        message = ("Swap did NOT reach the target: meal GL goes from " + str(before["total_gl"])
                   + " to " + str(after["total_gl"]) + " (" + str(reduction_percent)
                   + "% lower, target " + str(target) + "%). Try another alternative.")

    return {"ok": True, "message": message, "data": data}