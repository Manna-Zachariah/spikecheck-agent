"""Python's checks around the model. These are ENFORCED rules: they apply
no matter what the model says.

- check_scope:       refuse insulin / medication questions before any model call
- parse_model_reply: the parser    ("can Python read this reply?")
- validate_proposal: the validator ("is this proposal allowed and correct?")
- check_goal:        the stopping rule ("the model says done; does the evidence agree?")
"""

import json
import re

from tools import ALL_TOOLS
from tools.food_table import FOOD_TABLE_PATH, find_food, load_food_table, table_path_from
from tools.meal_math import SWAP_TARGET_PERCENT


# ---------------------------------------------------------------------------
# Part 1. Scope check (an enforced rule: Python checks before any model call)
# ---------------------------------------------------------------------------

OUT_OF_SCOPE_WORDS = ["insulin", "medication", "medicine", "metformin", "dose", "dosage"]


def check_scope(goal):
    """Refuse requests for medication or insulin advice before calling the model."""
    lowered = goal.lower()
    for word in OUT_OF_SCOPE_WORDS:
        if word in lowered:
            return False, ("SpikeCheck cannot give insulin or medication advice. "
                           "Please ask your doctor or diabetes care team. "
                           "SpikeCheck can only estimate the glycemic load of a meal.")
    return True, "Request is in scope."


# ---------------------------------------------------------------------------
# Part 2. The parser: is the model's reply readable?
# ---------------------------------------------------------------------------

def parse_model_reply(raw_reply):
    text = raw_reply.strip()

    # Small models sometimes wrap JSON in ``` fences. Remove them.
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        proposal = json.loads(text)
    except json.JSONDecodeError:
        return None, ('PARSER ERROR: The reply was not valid JSON. Reply with exactly one object like '
                      '{"action": "calculate_gl", "argument": {"items": [{"food": "apple", "grams": 150}]}}')
    return proposal, "Parsing succeeded."


# ---------------------------------------------------------------------------
# Part 3. The validator: is the parsed proposal acceptable?
# ---------------------------------------------------------------------------

def numbers_in_text(text):
    """All numbers written in a piece of text, as floats."""
    found = []
    for match in re.findall(r"\d+(?:\.\d+)?", text):
        found.append(float(match))
    return found


def validate_done(argument):
    for key in argument:
        if key not in ["status", "answer", "recommended_swap"]:
            return False, "Unexpected key in done: " + str(key)
    if argument.get("status") not in ["complete", "needs_info", "cannot_complete"]:
        return False, "done needs status complete, needs_info or cannot_complete."
    if type(argument.get("answer")) != str or argument["answer"].strip() == "":
        return False, "done needs a non-empty answer."
    swap = argument.get("recommended_swap")
    if swap is not None:
        if type(swap) != dict or "replace" not in swap or "with" not in swap:
            return False, "recommended_swap must be null or {\"replace\": ..., \"with\": ...}."
    return True, "Validation succeeded."


def validate_proposal(proposal, state):
    if type(proposal) != dict:
        return False, "The proposal must be a JSON object."
    if "action" not in proposal or "argument" not in proposal:
        return False, "The proposal needs action and argument."

    action = proposal["action"]
    argument = proposal["argument"]

    if type(action) != str:
        return False, "action must be text."
    if action != "done" and action not in ALL_TOOLS:
        return False, "That action is not allowed: " + action
    if type(argument) != dict:
        return False, "argument must be a JSON object."

    if action == "done":
        return validate_done(argument)

    valid, note = ALL_TOOLS[action].validate(argument)
    if not valid:
        return False, note

    foods, aliases, error = load_food_table(state.get("table_path", FOOD_TABLE_PATH))

    # Enforced rule: a portion must be one the user gave FOR THAT FOOD.
    # (A number the user gave for another food does not count.)
    if action == "calculate_gl" and error == "":
        for item in argument["items"]:
            if "grams" in item and item["grams"] is not None:
                if not portion_was_given(item["food"], item["grams"], state, foods, aliases):
                    return False, ("The portion " + str(item["grams"]) + " g for " + item["food"]
                                   + " was not given by the user for that food. "
                                   + "Leave grams out or ask the user.")

    # Enforced rule: a swap must be tested on the meal that calculate_gl checked.
    if action == "test_swap":
        if state.get("last_meal") is None:
            return False, "Run calculate_gl successfully before testing a swap."
        if error == "" and not same_meal(argument["items"], state["last_meal"], foods, aliases):
            return False, ("test_swap items must be exactly the meal from calculate_gl "
                           "(same foods and grams). Do not add the new food to items; "
                           "put it only in \"with\".")
        if argument.get("with_grams") is not None:
            if float(argument["with_grams"]) not in state["user_numbers"]:
                return False, "with_grams was not given by the user. Leave it out to use the table serving."

    return True, "Validation succeeded."


def names_for(food_name, foods, aliases):
    """Every name the table knows for a food: its main name and its aliases."""
    names = [food_name.lower().strip()]
    food = find_food(food_name, foods, aliases)
    if food is not None:
        names.append(food["name"])
        for alias in aliases:
            if aliases[alias] == food["name"]:
                names.append(alias)
    return names


def portion_was_given(food_name, grams, state, foods, aliases):
    """True if the user wrote this number in the same part of a sentence
    as this food, for example "150 g white rice", or in an answer to a
    question about this food."""
    for text in state["portion_texts"]:
        mentions_food = False
        for name in names_for(food_name, foods, aliases):
            if name in text:
                mentions_food = True
        if mentions_food and float(grams) in numbers_in_text(text):
            return True
    return False


def same_meal(items, meal, foods, aliases):
    """True if items (from test_swap) describe the same foods and grams as
    the meal that calculate_gl already checked."""
    if len(items) != len(meal["items"]):
        return False
    for item in items:
        food = find_food(item["food"], foods, aliases)
        if food is None or item.get("grams") is None:
            return False
        found = False
        for checked in meal["items"]:
            if checked["food"] == food["name"] and float(checked["grams"]) == float(item["grams"]):
                found = True
        if not found:
            return False
    return True


# ---------------------------------------------------------------------------
# Part 4. The stopping rule: the model says done, Python checks the evidence
# ---------------------------------------------------------------------------

ALWAYS_ALLOWED_NUMBERS = [10.0, 11.0, 19.0, 20.0, 100.0]
FORBIDDEN_PHRASES = ["insulin", "medication", "dose", "mg/dl", "mmol", "your blood sugar will"]


def number_is_supported(number, state):
    allowed = state["tool_numbers"] + state["user_numbers"] + ALWAYS_ALLOWED_NUMBERS
    for value in allowed:
        if abs(value - number) <= 0.05:
            return True
        if number == round(value):      # allow "about 43" for 43.2
            return True
    return False


def swap_matches(recommended, tested, foods, aliases):
    """True if a recommended swap is the same as a tested swap."""
    replace_food = find_food(recommended["replace"], foods, aliases)
    with_food = find_food(recommended["with"], foods, aliases)
    if replace_food is None or with_food is None:
        return False
    return replace_food["name"] == tested["replace"] and with_food["name"] == tested["with"]


def high_food_has_no_passing_swap(food_name, state):
    """True if Python saw that no swap could pass for this food:
    either there were no alternatives, or every alternative was tested and failed."""
    if food_name not in state["alternatives"]:
        return False
    alternatives = state["alternatives"][food_name]
    for alternative in alternatives:
        tested_and_failed = False
        for swap in state["swaps"]:
            if swap["replace"] == food_name and swap["with"] == alternative["food"] and not swap["passed"]:
                tested_and_failed = True
        if not tested_and_failed:
            return False
    return True


def check_goal(argument, state, context):
    """Decide whether Python accepts the model's done. Returns (accepted, note)."""
    answer = argument["answer"]
    status = argument["status"]
    lowered = answer.lower()

    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return False, "REJECTED: the answer mentions '" + phrase + "', which is outside SpikeCheck's scope."

    unsupported = []
    for number in numbers_in_text(answer):
        if not number_is_supported(number, state):
            unsupported.append(number)
    if len(unsupported) > 0:
        return False, ("REJECTED: these numbers did not come from any tool result: "
                       + str(unsupported) + ". Use only numbers from tool results.")

    if status == "cannot_complete":
        for problem in state["problems"]:
            if problem["problem"] == "tool_error":
                return True, "Accepted: a tool error was observed, so stopping is correct."
        return False, "REJECTED: no tool error was observed, so the task can still be completed."

    if status == "needs_info":
        missing_foods = []
        for problem in state["problems"]:
            if problem["problem"] in ["unknown_food", "missing_portion", "no_answer"]:
                missing_foods.append(problem["food"])
        if len(missing_foods) == 0:
            return False, "REJECTED: no tool reported missing information."
        for food in missing_foods:
            if food != "" and food.lower() in lowered:
                return True, "Accepted: the answer names the missing information that tools reported."
        return False, "REJECTED: the answer must name the food that is unknown or missing a portion."

    # status == "complete"
    meal = state["last_meal"]
    if meal is None:
        return False, "REJECTED: calculate_gl has not succeeded for the whole meal yet."

    foods, aliases, error = load_food_table(table_path_from(context))
    if error != "":
        return False, "REJECTED: the food table could not be read to check the answer."

    recommended = argument.get("recommended_swap")
    if recommended is not None:
        for swap in state["swaps"]:
            if (swap["passed"] and swap_matches(recommended, swap, foods, aliases) and swap["before_total_gl"] == meal["total_gl"]):
                state["accepted_swap"] = swap
                return True, ("Accepted: meal GL came from calculate_gl and the recommended swap "
                              "passed test_swap (" + str(swap["reduction_percent"]) + "% lower).")
        return False, ("REJECTED: the recommended swap was not tested, or it did not lower meal GL by "
                       "at least " + str(SWAP_TARGET_PERCENT) + "%.")

    for item in meal["items"]:
        if item["rating"] == "high" and not high_food_has_no_passing_swap(item["food"], state):
            return False, ("REJECTED: " + item["food"] + " has a high GL. Find and test a swap, "
                           "or show that no alternative passes.")

    return True, "Accepted: meal GL came from calculate_gl and no untested swap is recommended."