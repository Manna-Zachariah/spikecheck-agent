"""Calling the language model: Qwen3 8B, served locally by Ollama.

This is the ONLY file that talks to the model. The rest of the program
never needs to know which model is used.

Before running SpikeCheck, start Ollama (open the Ollama app, or run
`ollama serve`) and make sure the model is downloaded (`ollama pull qwen3:8b`).
"""

import requests


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


def call_model(messages):
    """Send the whole conversation to Qwen and return its reply text.

    The model does not remember earlier calls, so every call sends all
    messages: the system prompt, the goal, every model reply and every
    tool result so far.
    """
    request_body = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "think": False,          # Qwen3: answer directly, without a long reasoning section
        "format": "json",        # ask Ollama for JSON; the parser still checks it
        "options": {"temperature": 0},
    }
    response = requests.post(OLLAMA_URL, json=request_body, timeout=300)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]