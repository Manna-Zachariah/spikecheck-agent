"""The SpikeCheck tools.

ALL_TOOLS tells Python which file belongs to each tool name.
Every tool file has the same two functions:

    validate(argument)        -> (True or False, note)
    run(argument, context)    -> {"ok": ..., "message": ..., "data": {...}}
"""

from tools import ask_user, calculate_gl, find_alternatives, lookup_food, test_swap


ALL_TOOLS = {
    "lookup_food": lookup_food,
    "calculate_gl": calculate_gl,
    "find_alternatives": find_alternatives,
    "test_swap": test_swap,
    "ask_user": ask_user,
}