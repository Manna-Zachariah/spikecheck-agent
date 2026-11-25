"""Tool: lookup_food

Argument: {"food": "white rice"}
Returns the food's GI, carbohydrate per 100 g, category and serving size,
or reports that the food is not in the table.
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
        return unknown_food_result(argument["food"],
                                   argument["food"] + " is not in the food table. Its GI is unknown.")

    return {"ok": True, "message": "Found " + food["name"] + " in the food table.", "data": food}