"""Shared checks on the arguments the model proposes.

A validator answers: "is this proposal acceptable?" It never runs a tool.
"""

MAX_GRAMS = 2000   # anything larger is treated as a mistake
MAX_ITEMS = 10     # a single meal may contain at most 10 foods


def is_number(value):
    """True for int or float, but not for True/False."""
    if type(value) == bool:
        return False
    return type(value) == int or type(value) == float


def validate_items(items):
    """Check the shape of a meal list such as
    [{"food": "white rice", "grams": 150}, {"food": "apple", "grams": 150}].

    A missing "grams" is allowed here: the tool will report it as a
    missing portion, so the agent learns it has to ask the user.
    """
    if type(items) != list:
        return False, "items must be a list of {\"food\": ..., \"grams\": ...}."
    if len(items) == 0:
        return False, "items must contain at least one food."
    if len(items) > MAX_ITEMS:
        return False, "A meal may contain at most " + str(MAX_ITEMS) + " foods."

    for item in items:
        if type(item) != dict:
            return False, "Each item must be a dictionary."
        for key in item:
            if key not in ["food", "grams"]:
                return False, "Unexpected key in item: " + str(key)
        if "food" not in item or type(item["food"]) != str or item["food"].strip() == "":
            return False, "Each item needs a food name."
        if len(item["food"]) > 60:
            return False, "Food names must be shorter than 60 characters."
        if "grams" in item and item["grams"] is not None:
            if not is_number(item["grams"]):
                return False, "grams must be a number. If the user gave no portion, leave grams out."
            if item["grams"] <= 0 or item["grams"] > MAX_GRAMS:
                return False, "grams must be more than 0 and at most " + str(MAX_GRAMS) + "."

    return True, "Items are valid."


def validate_food_argument(argument):
    """Shared check for tools whose argument is {"food": "..."}."""
    if type(argument) != dict:
        return False, "Argument must be a dictionary like {\"food\": \"apple\"}."
    if set(argument) != {"food"}:
        return False, "Argument must contain exactly one key: food."
    if type(argument["food"]) != str or argument["food"].strip() == "":
        return False, "food must be non-empty text."
    if len(argument["food"]) > 60:
        return False, "food must be shorter than 60 characters."
    return True, "Argument is valid."