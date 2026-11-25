"""Reading the food table (foods.csv) and finding foods in it.

Every tool reads the table through this file, so if the table is missing
or damaged, every tool reports the same honest TOOL ERROR.
"""

import csv
from pathlib import Path


# foods.csv sits in the project folder, one level above this tools folder.
FOOD_TABLE_PATH = Path(__file__).parent.parent / "foods.csv"


def normalize_name(name):
    """Lower-case a food name and collapse extra spaces."""
    words = name.lower().strip().split()
    return " ".join(words)


def load_food_table(path):
    """Read foods.csv.

    Returns (foods, aliases, error).
    foods   maps a food name to its row (a dictionary).
    aliases maps another name, such as "rice", to the main food name.
    error   is "" when the table loaded, otherwise an explanation.
    """
    foods = {}
    aliases = {}

    try:
        with open(path, newline="", encoding="utf-8") as table_file:
            reader = csv.DictReader(table_file)
            for row in reader:
                name = normalize_name(row["name"])

                gi = None
                if row["gi"].strip() != "":
                    gi = float(row["gi"])

                food = {
                    "name": name,
                    "category": row["category"].strip(),
                    "gi": gi,
                    "carbs_per_100g": float(row["carbs_per_100g"]),
                    "serving_g": float(row["serving_g"]),
                    "note": row["note"].strip(),
                }
                foods[name] = food

                for alias in row["aliases"].split("|"):
                    if alias.strip() != "":
                        aliases[normalize_name(alias)] = name
    except FileNotFoundError:
        return {}, {}, "The food table file was not found: " + str(path)
    except (KeyError, ValueError) as error:
        return {}, {}, "The food table is damaged: " + str(error)

    if len(foods) == 0:
        return {}, {}, "The food table is empty."

    return foods, aliases, ""


def find_food(name, foods, aliases):
    """Return the table row for a food name, or None if it is not in the table.

    There is deliberately no fuzzy matching: an unknown food is reported
    as unknown instead of being guessed.
    """
    key = normalize_name(name)

    if key in foods:
        return foods[key]
    if key in aliases:
        return foods[aliases[key]]

    # Allow a simple plural, such as "bananas" -> "banana".
    if key.endswith("s"):
        singular = key[:-1]
        if singular in foods:
            return foods[singular]
        if singular in aliases:
            return foods[aliases[singular]]

    return None


def table_path_from(context):
    """The main program may point the tools at another table (used to test a tool failure)."""
    if "table_path" in context:
        return context["table_path"]
    return FOOD_TABLE_PATH


def unknown_food_result(food_name, message):
    """The standard result when a food is not in the table."""
    return {
        "ok": False,
        "message": message,
        "data": {"problem": "unknown_food", "problems": [{"food": food_name, "problem": "unknown_food"}]},
    }


def tool_error_result(error):
    """The standard result when a tool itself cannot work."""
    return {
        "ok": False,
        "message": "TOOL ERROR: " + error,
        "data": {"problem": "tool_error", "problems": [{"food": "", "problem": "tool_error"}]},
    }