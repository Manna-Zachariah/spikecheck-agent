"""The parts of the SpikeCheck agent around the model.

qwen_model.py  calls Qwen through Ollama (the only file that talks to the model)
prompt.py      the system prompt and the demo meals
checks.py      Python's enforced rules: scope check, parser, validator, stopping rule
state.py       the record of what the tools actually returned
"""