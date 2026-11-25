"""A fake model for tests and for running the demo without Ollama.

Like mock_model in Homework 2, it stands in for the language model.
It is deterministic: each demo has a fixed list of replies, and the fake
model returns the next one each time it is called. Python still parses,
validates, runs tools and checks the evidence exactly as with a real model.

The "messy" script deliberately makes mistakes (bad JSON, a forbidden
action, an invented portion, an invented number, a premature done) to show
that Python catches each of them.
"""

import json


def reply(action, argument):
    """Build one model reply as JSON text, the way a real model would answer."""
    return json.dumps({"action": action, "argument": argument})


RICE_MEAL = [
    {"food": "white rice", "grams": 150},
    {"food": "chicken breast", "grams": 150},
    {"food": "orange juice", "grams": 250},
]

BREAKFAST_MEAL = [
    {"food": "cornflakes", "grams": 40},
    {"food": "whole milk", "grams": 250},
    {"food": "banana", "grams": 120},
]

SANDWICH_MEAL = [
    {"food": "white bread", "grams": 60},
    {"food": "cheddar cheese", "grams": 30},
    {"food": "apple", "grams": 150},
]


SCRIPTS = {
    # Python refuses the insulin question before any model call, so no replies are needed.
    "insulin": [],

    "rice": [
        reply("calculate_gl", {"items": RICE_MEAL}),
        reply("find_alternatives", {"food": "white rice"}),
        reply("test_swap", {"items": RICE_MEAL, "replace": "white rice", "with": "brown rice"}),
        reply("done", {
            "status": "complete",
            "answer": "Your meal has a glycemic load of 43.2. White rice has the highest GL (30.7, high). "
                      "Swapping it for brown rice lowers the meal GL to 33.9, which is 21.5% lower.",
            "recommended_swap": {"replace": "white rice", "with": "brown rice"},
        }),
    ],

    "breakfast": [
        reply("calculate_gl", {"items": BREAKFAST_MEAL}),
        reply("find_alternatives", {"food": "cornflakes"}),
        reply("test_swap", {"items": BREAKFAST_MEAL, "replace": "cornflakes", "with": "instant oat porridge"}),
        reply("test_swap", {"items": BREAKFAST_MEAL, "replace": "cornflakes", "with": "rolled oat porridge"}),
        reply("done", {
            "status": "complete",
            "answer": "Your breakfast has a glycemic load of 43.3. Cornflakes are high (GL 26.2). "
                      "Instant oat porridge only lowered the meal GL by 14.8%, below the 20% target. "
                      "A 250 g serving of rolled oat porridge lowers it from 43.3 to 30.9, which is 28.6% lower.",
            "recommended_swap": {"replace": "cornflakes", "with": "rolled oat porridge"},
        }),
    ],

    "sandwich": [
        reply("calculate_gl", {"items": SANDWICH_MEAL}),
        reply("find_alternatives", {"food": "white bread"}),
        reply("test_swap", {"items": SANDWICH_MEAL, "replace": "white bread", "with": "whole wheat bread"}),
        reply("test_swap", {"items": SANDWICH_MEAL, "replace": "white bread", "with": "chapati"}),
        reply("done", {
            "status": "complete",
            "answer": "Your lunch has a glycemic load of 26.6. White bread is high (GL 20.7). "
                      "Whole wheat bread only lowered the meal GL by 16.2%, below the 20% target. "
                      "Chapati lowers it to 19.0, which is 28.6% lower.",
            "recommended_swap": {"replace": "white bread", "with": "chapati"},
        }),
    ],

    "missing": [
        reply("calculate_gl", {"items": [{"food": "pasta"}, {"food": "dragon fruit chips", "grams": 100}]}),
        reply("ask_user", {"question": "How many grams of pasta did you eat?"}),
        reply("done", {
            "status": "needs_info",
            "answer": "I could not calculate this meal. Dragon fruit chips are not in my food table, "
                      "so their GI is unknown, and no portion was given for the pasta. "
                      "Please tell me the pasta portion in grams.",
            "recommended_swap": None,
        }),
    ],

    "broken": [
        reply("calculate_gl", {"items": RICE_MEAL}),
        reply("done", {
            "status": "cannot_complete",
            "answer": "The food table could not be loaded, so I cannot calculate the glycemic load right now.",
            "recommended_swap": None,
        }),
    ],

    "messy": [
        "Sure! I will calculate the meal now.",                                     # not JSON
        reply("delete_files", {}),                                                  # not an allowed action
        reply("calculate_gl", {"items": [{"food": "white rice", "grams": 200},      # 200 g was never given
                                         {"food": "chicken breast", "grams": 150},
                                         {"food": "orange juice", "grams": 250}]}),
        reply("calculate_gl", {"items": RICE_MEAL}),
        reply("done", {"status": "complete",                                        # 99 is invented
                       "answer": "Your meal GL is 99.", "recommended_swap": None}),
        reply("done", {"status": "complete",                                        # high food, no swap tested
                       "answer": "Your meal GL is 43.2.", "recommended_swap": None}),
        reply("find_alternatives", {"food": "white rice"}),
        reply("test_swap", {"items": RICE_MEAL, "replace": "white rice", "with": "brown rice"}),
        reply("done", {"status": "complete",
                       "answer": "Your meal GL is 43.2. Brown rice instead of white rice lowers it to 33.9.",
                       "recommended_swap": {"replace": "white rice", "with": "brown rice"}}),
    ],
}


def make_mock_model(script_name):
    """Return a fake model function that follows one script."""
    replies = SCRIPTS[script_name]

    def mock_model(messages):
        # Count how many times the model has already answered.
        answered = 0
        for message in messages:
            if message["role"] == "assistant":
                answered = answered + 1

        if answered >= len(replies):
            # Out of script: keep proposing an invalid action so the budget runs out.
            return reply("no_more_script", {})
        return replies[answered]

    return mock_model