"""Tool: calculate_gl

Argument: {"items": [{"food": "white rice", "grams": 150}, {"food": "apple", "grams": 150}]}
Python calculates GL for each food and for the whole meal.
Unknown foods and missing portions are reported, never guessed.
"""

from tools.argument_checks import validate_items
from tools.food_table import load_food_table, table_path_from, tool_error_result
from tools.meal_math import calculate_meal, gl_rating


def validate(argument):
    if type(argument) != dict:
        return False, "Argument must be a dictionary like {\"items\": [...]}."
    if set(argument) != {"items"}:
        return False, "Argument must contain exactly one key: items."
    return validate_items(argument["items"])


def run(argument, context):
    valid, note = validate(argument)
    if not valid:
        return {"ok": False, "message": note, "data": {}}

    foods, aliases, error = load_food_table(table_path_from(context))
    if error != "":
        return tool_error_result(error)

    meal = calculate_meal(argument["items"], foods, aliases)

    if len(meal["problems"]) > 0:
        meal["problem"] = meal["problems"][0]["problem"]
        problem_text = []
        for problem in meal["problems"]:
            problem_text.append(problem["food"] + " (" + problem["problem"] + ")")
        return {
            "ok": False,
            "message": "Could not calculate the whole meal. Problems: " + ", ".join(problem_text)
                       + ". The total only covers the foods that could be calculated.",
            "data": meal,
        }

    meal["rating"] = gl_rating(meal["total_gl"])
    return {
        "ok": True,
        "message": "Meal glycemic load is " + str(meal["total_gl"]) + ".",
        "data": meal,
    }