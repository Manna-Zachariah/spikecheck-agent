"""Fast offline checks for SpikeCheck.

No model, Ollama or Internet is needed. Run with:
    python tests.py        (on some Macs: python3 tests.py)

The expected numbers were calculated by hand:
GL = GI x carbs / 100, carbs = carbs_per_100g x grams / 100.
"""

from pathlib import Path

import mock_model
from agent.checks import check_scope, parse_model_reply, validate_proposal
from agent.prompt import DEMO_GOALS
from agent.state import new_state
from spikecheck_agent import run_agent
from tools import calculate_gl, find_alternatives, lookup_food, test_swap, ask_user
from tools.food_table import FOOD_TABLE_PATH, load_food_table
from tools.meal_math import gl_rating


CONTEXT = {"interactive": False}
BROKEN_CONTEXT = {"interactive": False, "table_path": Path("missing_foods.csv")}

RICE_MEAL = [
    {"food": "white rice", "grams": 150},
    {"food": "chicken breast", "grams": 150},
    {"food": "orange juice", "grams": 250},
]


def run_test(name, test_function):
    test_function()
    print("PASS:", name)


def quiet_run(demo_name, context):
    """Run the agent with the fake model and no trace file."""
    return run_agent(DEMO_GOALS[demo_name], context, mock_model.make_mock_model(demo_name), None)


# --- Part 1. The food table and the math -----------------------------------

def test_table_loads():
    foods, aliases, error = load_food_table(FOOD_TABLE_PATH)
    assert error == ""
    assert len(foods) >= 25
    assert aliases["rice"] == "white rice"


def test_rice_meal_gl_matches_hand_calculation():
    # white rice: 28 x 150 / 100 = 42 g carbs, 73 x 42 / 100 = 30.66 -> 30.7
    # orange juice: 10 x 250 / 100 = 25 g carbs, 50 x 25 / 100 = 12.5
    # chicken breast: no carbohydrate -> 0.0
    result = calculate_gl.run({"items": RICE_MEAL}, CONTEXT)
    assert result["ok"] is True
    assert result["data"]["items"][0]["gl"] == 30.7
    assert result["data"]["items"][1]["gl"] == 0.0
    assert result["data"]["items"][2]["gl"] == 12.5
    assert result["data"]["total_gl"] == 43.2


def test_gl_ratings():
    assert gl_rating(10) == "low"
    assert gl_rating(10.5) == "medium"
    assert gl_rating(19.9) == "medium"
    assert gl_rating(20) == "high"


def test_alias_lookup():
    result = lookup_food.run({"food": "Rice"}, CONTEXT)
    assert result["ok"] is True
    assert result["data"]["name"] == "white rice"


# --- Part 2. Problem cases inside the tools --------------------------------

def test_unknown_food_is_reported_not_guessed():
    result = lookup_food.run({"food": "dragon fruit chips"}, CONTEXT)
    assert result["ok"] is False
    assert result["data"]["problem"] == "unknown_food"


def test_missing_portion_is_reported():
    result = calculate_gl.run({"items": [{"food": "pasta"}]}, CONTEXT)
    assert result["ok"] is False
    assert result["data"]["problems"][0]["problem"] == "missing_portion"


def test_tool_failure_is_reported():
    result = calculate_gl.run({"items": RICE_MEAL}, BROKEN_CONTEXT)
    assert result["ok"] is False
    assert "TOOL ERROR" in result["message"]


def test_ask_user_without_a_user():
    result = ask_user.run({"question": "How many grams?"}, CONTEXT)
    assert result["ok"] is False
    assert result["data"]["problem"] == "no_answer"


# --- Part 3. Swaps ----------------------------------------------------------

def test_alternatives_are_lower_gi_same_category_closest_first():
    result = find_alternatives.run({"food": "white bread"}, CONTEXT)
    names = []
    for alternative in result["data"]["alternatives"]:
        names.append(alternative["food"])
    assert names == ["whole wheat bread", "chapati", "corn tortilla"]


def test_swap_below_target_does_not_pass():
    meal = [{"food": "white bread", "grams": 60}, {"food": "cheddar cheese", "grams": 30},
            {"food": "apple", "grams": 150}]
    result = test_swap.run({"items": meal, "replace": "white bread", "with": "whole wheat bread"}, CONTEXT)
    assert result["data"]["before_total_gl"] == 26.6
    assert result["data"]["after_total_gl"] == 22.3
    assert result["data"]["passed"] is False


def test_swap_above_target_passes():
    meal = [{"food": "white bread", "grams": 60}, {"food": "cheddar cheese", "grams": 30},
            {"food": "apple", "grams": 150}]
    result = test_swap.run({"items": meal, "replace": "white bread", "with": "chapati"}, CONTEXT)
    assert result["data"]["after_total_gl"] == 19.0
    assert result["data"]["reduction_percent"] == 28.6
    assert result["data"]["passed"] is True


# --- Part 4. Parser, validator and scope check ------------------------------

def test_bad_json_is_caught_by_parser():
    proposal, note = parse_model_reply("Sure! Here is my answer.")
    assert proposal is None
    assert "PARSER ERROR" in note

def test_disallowed_action_is_blocked():
    state = new_state(DEMO_GOALS["rice"], CONTEXT)
    valid, note = validate_proposal({"action": "delete_files", "argument": {}}, state)
    assert valid is False


def test_invented_portion_is_blocked():
    state = new_state(DEMO_GOALS["rice"], CONTEXT)
    proposal = {"action": "calculate_gl", "argument": {"items": [{"food": "white rice", "grams": 200}]}}
    valid, note = validate_proposal(proposal, state)
    assert valid is False
    assert "not given by the user" in note


def test_portion_from_another_food_is_blocked():
    # Found in a real Qwen run: the user gave 100 g only for the chips,
    # but the model reused 100 g for the pasta.
    state = new_state(DEMO_GOALS["missing"], CONTEXT)
    proposal = {"action": "calculate_gl", "argument": {"items": [{"food": "pasta", "grams": 100},
                                                                 {"food": "dragon fruit chips", "grams": 100}]}}
    valid, note = validate_proposal(proposal, state)
    assert valid is False
    assert "pasta" in note


def test_user_portions_are_accepted():
    state = new_state(DEMO_GOALS["rice"], CONTEXT)
    proposal = {"action": "calculate_gl", "argument": {"items": [{"food": "white rice", "grams": 150},
                                                                 {"food": "chicken breast", "grams": 150},
                                                                 {"food": "orange juice", "grams": 250}]}}
    valid, note = validate_proposal(proposal, state)
    assert valid is True


def test_swap_on_a_changed_meal_is_blocked():
    # Found in a real Qwen run: the model added the new food to the meal
    # instead of replacing the old one, so the comparison was wrong.
    state = new_state(DEMO_GOALS["rice"], CONTEXT)
    state["last_meal"] = calculate_gl.run({"items": RICE_MEAL}, CONTEXT)["data"]
    changed_meal = RICE_MEAL + [{"food": "brown rice", "grams": 150}]
    proposal = {"action": "test_swap", "argument": {"items": changed_meal,
                                                    "replace": "white rice", "with": "brown rice"}}
    valid, note = validate_proposal(proposal, state)
    assert valid is False
    assert "exactly the meal" in note

def test_insulin_question_is_refused():
    in_scope, note = check_scope("How much insulin should I take?")
    assert in_scope is False


# --- Part 5. The whole loop with the fake model -----------------------------

def test_rice_demo_succeeds():
    result = quiet_run("rice", CONTEXT)
    assert result["stop_reason"] == "success"


def test_sandwich_demo_retries_after_failed_swap():
    result = quiet_run("sandwich", CONTEXT)
    assert result["stop_reason"] == "success"
    swap_results = []
    for record in result["trace"]:
        if record["action"] == "test_swap":
            swap_results.append(record["observation"]["data"]["passed"])
    assert swap_results == [False, True]


def test_missing_information_demo_stops_with_needs_info():
    result = quiet_run("missing", CONTEXT)
    assert result["stop_reason"] == "needs_info"


def test_broken_table_demo_stops_with_cannot_complete():
    result = quiet_run("broken", BROKEN_CONTEXT)
    assert result["stop_reason"] == "cannot_complete"


def test_insulin_demo_is_refused_without_calling_the_model():
    result = quiet_run("insulin", CONTEXT)
    assert result["stop_reason"] == "refused"


def test_messy_model_mistakes_are_all_caught():
    result = quiet_run("messy", CONTEXT)
    trace = result["trace"]
    assert trace[0]["parse_ok"] is False                 # not JSON
    assert trace[1]["validation_ok"] is False            # delete_files
    assert trace[2]["validation_ok"] is False            # invented 200 g portion
    assert trace[4]["check_result"] is False             # invented number 99
    assert trace[5]["check_result"] is False             # high GL food, no swap tested
    assert result["stop_reason"] == "success"


def test_model_that_never_finishes_hits_the_budget():
    def endless_model(messages):
        return '{"action": "lookup_food", "argument": {"food": "apple"}}'
    result = run_agent(DEMO_GOALS["rice"], CONTEXT, endless_model, None)
    assert result["stop_reason"] == "budget_exceeded"


if __name__ == "__main__":
    run_test("food table loads", test_table_loads)
    run_test("rice meal GL matches hand calculation", test_rice_meal_gl_matches_hand_calculation)
    run_test("GL ratings", test_gl_ratings)
    run_test("alias lookup", test_alias_lookup)
    run_test("unknown food is reported, not guessed", test_unknown_food_is_reported_not_guessed)
    run_test("missing portion is reported", test_missing_portion_is_reported)
    run_test("tool failure is reported", test_tool_failure_is_reported)
    run_test("ask_user without a user", test_ask_user_without_a_user)
    run_test("alternatives: lower GI, same category, closest first",
             test_alternatives_are_lower_gi_same_category_closest_first)
    run_test("swap below 20% does not pass", test_swap_below_target_does_not_pass)
    run_test("swap above 20% passes", test_swap_above_target_passes)
    run_test("bad JSON is caught by the parser", test_bad_json_is_caught_by_parser)
    run_test("disallowed action is blocked", test_disallowed_action_is_blocked)
    run_test("portion from another food is blocked", test_portion_from_another_food_is_blocked)
    run_test("portions the user gave are accepted", test_user_portions_are_accepted)
    run_test("swap on a changed meal is blocked", test_swap_on_a_changed_meal_is_blocked)
    run_test("invented portion is blocked", test_invented_portion_is_blocked)
    run_test("insulin question is refused", test_insulin_question_is_refused)
    run_test("rice demo succeeds", test_rice_demo_succeeds)
    run_test("sandwich demo retries after a failed swap", test_sandwich_demo_retries_after_failed_swap)
    run_test("missing information -> needs_info", test_missing_information_demo_stops_with_needs_info)
    run_test("broken table -> cannot_complete", test_broken_table_demo_stops_with_cannot_complete)
    run_test("insulin demo refused before any model call", test_insulin_demo_is_refused_without_calling_the_model)
    run_test("messy model mistakes are all caught", test_messy_model_mistakes_are_all_caught)
    run_test("model that never finishes hits the budget", test_model_that_never_finishes_hits_the_budget)
    print("\nAll tests passed.")