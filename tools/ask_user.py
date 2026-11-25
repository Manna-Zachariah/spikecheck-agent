"""Tool: ask_user

Argument: {"question": "How many grams of pasta did you eat?"}
Asks the person at the keyboard. In tests or batch runs nobody can answer,
so the tool reports "no_answer" and the agent must report what is missing.
"""


def validate(argument):
    if type(argument) != dict:
        return False, "Argument must be a dictionary like {\"question\": \"...\"}."
    if set(argument) != {"question"}:
        return False, "Argument must contain exactly one key: question."
    if type(argument["question"]) != str or argument["question"].strip() == "":
        return False, "question must be non-empty text."
    if len(argument["question"]) > 300:
        return False, "question must be shorter than 300 characters."
    return True, "Argument is valid."


def no_answer_result(question, message):
    return {
        "ok": False,
        "message": message,
        "data": {"problem": "no_answer", "problems": [{"food": "", "problem": "no_answer"}],
                 "question": question},
    }


def run(argument, context):
    valid, note = validate(argument)
    if not valid:
        return {"ok": False, "message": note, "data": {}}

    if not context.get("interactive", False):
        return no_answer_result(argument["question"],
                                "No user is available to answer in this run. Report what is missing instead.")

    answer = input("\nAGENT ASKS: " + argument["question"] + "\nYour answer: ").strip()
    if answer == "":
        return no_answer_result(argument["question"],
                                "The user gave no answer. Report what is missing instead.")

    return {
        "ok": True,
        "message": "The user answered: " + answer,
        "data": {"question": argument["question"], "answer": answer},
    }