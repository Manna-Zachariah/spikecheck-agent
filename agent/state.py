"""The agent's state: a record of what the tools ACTUALLY returned.

check_goal in checks.py only trusts this record, never the model's words.
"""

import re

from agent.checks import numbers_in_text
from tools.food_table import table_path_from


# ---------------------------------------------------------------------------
# Part 1. A new, empty state at the start of a run
# ---------------------------------------------------------------------------

def split_into_parts(text):
    """Split the user's meal into parts, so "150 g white rice, 250 ml orange juice"
    becomes ["150 g white rice", "250 ml orange juice"]. A portion only counts
    for a food in the same part."""
    parts = re.split(r",|;| and | with | plus ", text.lower())
    cleaned = []
    for part in parts:
        if part.strip() != "":
            cleaned.append(part.strip())
    return cleaned


def new_state(goal, context):
    return {
        "user_numbers": numbers_in_text(goal),      # every number the user typed
        "portion_texts": split_into_parts(goal),    # where each number was typed
        "table_path": table_path_from(context),
        "tool_numbers": [],                         # every number any tool returned
        "problems": [],                             # unknown foods, missing portions, tool errors
        "last_meal": None,                          # the last successful calculate_gl result
        "alternatives": {},                         # find_alternatives results by food
        "swaps": [],                                # every test_swap result
        "accepted_swap": None,
    }


# ---------------------------------------------------------------------------
# Part 2. State update: remember the evidence each tool produced
# ---------------------------------------------------------------------------

def collect_numbers(value, numbers):
    """Walk through a tool result and collect every number in it."""
    if type(value) == dict:
        for key in value:
            collect_numbers(value[key], numbers)
    elif type(value) == list:
        for item in value:
            collect_numbers(item, numbers)
    elif type(value) == bool:
        return
    elif type(value) == int or type(value) == float:
        numbers.append(float(value))
    elif type(value) == str:
        for number in numbers_in_text(value):
            numbers.append(number)


def update_state(state, action, argument, result):
    """Record what the tool actually returned. check_goal uses only this record."""
    collect_numbers(result, state["tool_numbers"])
    data = result.get("data", {})

    for problem in data.get("problems", []):
        state["problems"].append(problem)

    if action == "calculate_gl" and result["ok"]:
        state["last_meal"] = data

    if action == "find_alternatives" and result["ok"]:
        state["alternatives"][data["food"]] = data["alternatives"]

    if action == "test_swap" and result["ok"]:
        state["swaps"].append(data)

    if action == "ask_user" and result["ok"]:
        # A portion the user types in an answer counts for the food in the question.
        for number in numbers_in_text(data["answer"]):
            state["user_numbers"].append(number)
        state["portion_texts"].append((data["question"] + " " + data["answer"]).lower())


# ---------------------------------------------------------------------------
# Part 3. Printing a summary that Python builds from tool results only
# ---------------------------------------------------------------------------

def verified_summary(state):
    lines = []
    meal = state["last_meal"]
    if meal is None:
        lines.append("No complete meal calculation was verified.")
    else:
        lines.append("Meal glycemic load (calculated by Python):")
        for item in meal["items"]:
            gi_text = "none"
            if item["gi"] is not None:
                gi_text = str(item["gi"])
            lines.append("  - " + item["food"] + ", " + str(item["grams"]) + " g: carbs "
                         + str(item["carbs_g"]) + " g, GI " + gi_text
                         + ", GL " + str(item["gl"]) + " (" + item["rating"] + ")")
        lines.append("  TOTAL GL: " + str(meal["total_gl"]))

    for swap in state["swaps"]:
        result_word = "PASSED" if swap["passed"] else "did not pass"
        lines.append("Swap tested: " + swap["replace"] + " -> " + swap["with"] + " ("
                     + str(swap["with_grams"]) + " g): " + str(swap["before_total_gl"]) + " -> "
                     + str(swap["after_total_gl"]) + ", " + str(swap["reduction_percent"])
                     + "% lower, " + result_word)

    for problem in state["problems"]:
        lines.append("Problem reported by a tool: " + problem["problem"]
                     + (" (" + problem["food"] + ")" if problem["food"] != "" else ""))

    lines.append("Note: an estimate from a small food table, not a prediction of blood sugar.")
    return "\n".join(lines)