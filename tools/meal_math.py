"""Glycemic load calculations. Pure Python: no model is involved.

Glycemic load (GL) = GI x available carbohydrate in grams / 100
GL rating per food serving: low <= 10, medium 11-19, high >= 20.
"""

from tools.food_table import find_food


SWAP_TARGET_PERCENT = 20   # a swap must lower meal GL by at least 20%
LOW_GL_MAX = 10            # GL of 10 or less is "low"
HIGH_GL_MIN = 20           # GL of 20 or more is "high"


def gl_rating(gl):
    """Turn a glycemic load number into low / medium / high."""
    if gl <= LOW_GL_MAX:
        return "low"
    if gl < HIGH_GL_MIN:
        return "medium"
    return "high"


def calculate_item(food, grams):
    """GL for one food at one portion size."""
    carbs = food["carbs_per_100g"] * grams / 100

    if food["gi"] is None:
        # Foods with almost no carbohydrate have no measured GI.
        gl = 0.0
        note = "No GI value: almost no carbohydrate, so GL is counted as 0."
    else:
        gl = food["gi"] * carbs / 100
        note = ""

    item = {
        "food": food["name"],
        "grams": grams,
        "gi": food["gi"],
        "carbs_g": round(carbs, 1),
        "gl": round(gl, 1),
        "rating": gl_rating(round(gl, 1)),
        "note": note,
    }
    return item


def calculate_meal(items, foods, aliases):
    """GL for every food in a meal plus the meal total.

    Returns a dictionary with "items", "total_gl", "total_carbs_g"
    and "problems". A problem is an unknown food or a missing portion.
    Known foods are still calculated so the user sees a partial result.
    """
    results = []
    problems = []
    total_gl = 0.0
    total_carbs = 0.0

    for item in items:
        food_name = item["food"]
        food = find_food(food_name, foods, aliases)

        if food is None:
            problems.append({"food": food_name, "problem": "unknown_food"})
            continue

        if "grams" not in item or item["grams"] is None:
            problems.append({"food": food_name, "problem": "missing_portion"})
            continue

        result = calculate_item(food, float(item["grams"]))
        results.append(result)
        total_gl = total_gl + result["gl"]
        total_carbs = total_carbs + result["carbs_g"]

    meal = {
        "items": results,
        "total_gl": round(total_gl, 1),
        "total_carbs_g": round(total_carbs, 1),
        "problems": problems,
    }
    return meal