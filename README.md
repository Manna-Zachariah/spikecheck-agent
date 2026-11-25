# SpikeCheck: a glycemic load agent

CSYE 7374 Agentic AI mini project, Manna Meriah Zachariah (individual project)

SpikeCheck looks at a meal, estimates the **glycemic load (GL)** of each food and of the
whole meal, finds the foods with a high GL, and tests whether a lower-GI food swap would
lower the meal's GL by at least 20%.

A local language model (**Qwen3 8B through Ollama**) decides what to do next. **Python does
every calculation and checks the evidence** before the agent is allowed to stop.

> SpikeCheck gives an educational estimate from a small food table. It does **not** predict
> anyone's actual blood sugar and gives **no** insulin, medication or other clinical advice.

## Approved scope
| Professor's guidance | How SpikeCheck meets it |
|---|---|
| Small local nutrition table | `foods.csv`, 33 foods, no external API |
| Focus on estimating glycemic load | GL per food and per meal, calculated in Python |
| 2–3 fictional meals and one substitution | 3 demo meals (rice, breakfast, sandwich), each with a tested swap |
| Explain where information is missing | Unknown foods and missing portions are reported, never guessed |
| Verify whether the substitution changes GL | `test_swap` recalculates the meal; Python only accepts swaps that pass |
| No blood-sugar prediction or clinical advice | Insulin and medication questions are refused before the model is called |
| No cloud deployment or meal-history storage | Not included |

## Glycemic load in one line
**GL = GI × available carbohydrate (g) ÷ 100**, where carbohydrate = carbs per 100 g × grams ÷ 100.

Per food serving, GL is **low ≤ 10**, **medium 11–19** and **high ≥ 20**.

Example: 150 g white rice → 28 × 150 ÷ 100 = 42 g carbs → 73 × 42 ÷ 100 = **GL 30.7 (high)**.

## How to run

### 1. Requirements
- Python 3.10 or newer
- [Ollama](https://ollama.com) with the Qwen3 8B model

```bash
pip install -r requirements.txt
ollama pull qwen3:8b
```
Start Ollama by opening the Ollama app, or by running `ollama serve`.
Check that it's running with `curl http://localhost:11434`.

### 2. Run a demo with the real model
```bash
python3 spikecheck_agent.py --demo sandwich
```
Demos: `rice`, `breakfast`, `sandwich`, `missing`, `insulin`, `broken`, `messy`.

### 3. Analyze your own meal
Give every portion in grams (for drinks, 1 ml counts as 1 g):
```bash
python3 spikecheck_agent.py "Lunch: 150 g white rice, 150 g chicken breast and 250 ml orange juice"
```

### 4. Run without Ollama (fake model)
```bash
python3 spikecheck_agent.py --demo sandwich --mock
```
The fake model in `mock_model.py` follows a fixed script, like `mock_model` in Homework 2.
Python still parses, validates, runs tools and checks evidence in exactly the same way.

### 5. Run the tests (no model needed)
```bash
python3 tests.py
```
The 25 tests should end with `All tests passed.`

Every run saves a step-by-step trace to `sample_traces/<demo>_trace.json`.

## How the agent works
```
user's meal
   │
   ▼
Python scope check ── insulin / medication? ──► refuse (the model is never called)
   │
   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 1. Qwen proposes ONE action as JSON  {"action": ..., "argument": ...}│
│ 2. Python PARSES it      (can Python read it?)                       │
│ 3. Python VALIDATES it   (allowed action? portions given by user?)   │
│ 4. Python RUNS the tool  ──► observation sent back to Qwen           │
│    or, if the action is "done":                                      │
│    Python CHECKS THE EVIDENCE ──► accept and stop, or reject + reason│
└──────────────────────────────────────────────────────────────────────┘
   │  repeats until Python accepts "done", or 15 steps are used
   ▼
answer + "VERIFIED BY PYTHON" summary + saved trace
```

### Tools the model chooses between
| Tool | What it does |
|---|---|
| `lookup_food` | GI, carbs per 100 g and serving size for one food, or "not in table" |
| `calculate_gl` | GL per food and for the whole meal; reports unknown foods and missing portions |
| `find_alternatives` | Lower-GI foods in the same category, closest GI first |
| `test_swap` | Recalculates the meal with one food replaced; **passes** only if meal GL drops by at least 20% |
| `ask_user` | Asks the user for missing information, such as a portion |
| `done` | Proposes to finish with status `complete`, `needs_info` or `cannot_complete` |

The agent does not follow a fixed sequence. For example, in the sandwich demo Qwen tested
whole wheat bread, saw it lowered GL by only 16.2%, and **chose to try chapati**, which
passed at 28.6%.

### Python's enforced rules (`agent/checks.py`)
The system prompt only *asks* the model to behave. These checks apply no matter what the model says:
1. **Scope check:** insulin and medication questions are refused before any model call.
2. **Parser:** replies that are not valid JSON are rejected and the model is told the exact form to use.
3. **Validator:** blocks unknown actions and malformed arguments, blocks a **portion the user did not
   give for that food**, and blocks a swap tested on a meal different from the one `calculate_gl` checked.
4. **Stopping rule** ("the model says done, Python checks the evidence"):
   - every number in the answer must appear in a tool result
   - a recommended swap must have **passed** `test_swap`, starting from the verified meal total
   - a high-GL food cannot be ignored unless Python saw that no alternative passes
   - `needs_info` must name the missing food, and `cannot_complete` needs an observed tool error

### Stop reasons
`success`, `needs_info`, `cannot_complete`, `refused`, `model_error`, `budget_exceeded`

## Problem cases
| Demo | Problem | What happens |
|---|---|---|
| `missing` | "some pasta" (no portion) and dragon fruit chips (not in table) | Asks for the portion, refuses to guess, stops with `needs_info` naming the gaps |
| `insulin` | Asks for an insulin dose | Refused by Python before the model is called (`refused`) |
| `broken` | The food table file is missing (tool failure) | Tool reports `TOOL ERROR`; agent stops with `cannot_complete` |
| `messy` (fake model) | Bad JSON, forbidden action, invented portion, invented number, premature `done` | Each mistake is caught and sent back to the model |

## Bugs found by testing with the real model
Testing with real Qwen found two problems the fake-model tests had missed. Both are fixed and covered by new tests:
1. **Portion reused from another food:** for "some pasta and 100 g dragon fruit chips", Qwen sent
   `pasta: 100 g`. The validator now accepts a portion only if the user wrote it next to that food,
   or in an answer to a question about that food.
2. **Swap tested on a changed meal:** Qwen added brown rice to the meal instead of replacing white rice,
   so the comparison started from the wrong total. `test_swap` is now only allowed on exactly the meal
   `calculate_gl` checked.

The traces from before the fixes are kept in `sample_traces/*_BEFORE_FIX.json`.

## Project structure
```
spikecheck_agent.py      the agent loop and command line
mock_model.py            fake model for tests and offline runs
tests.py                 25 offline tests
foods.csv                the food table
agent/
  qwen_model.py          calls Qwen through Ollama (the only file that talks to the model)
  prompt.py              system prompt and demo meals
  checks.py              scope check, parser, validator, stopping rule
  state.py               record of what the tools actually returned
tools/                   one file per tool, each with validate() and run()
  lookup_food.py, calculate_gl.py, find_alternatives.py, test_swap.py, ask_user.py
  food_table.py, meal_math.py, argument_checks.py   shared helpers
sample_traces/           saved runs (real Qwen and fake model)
```

## Data sources and limitations
- GI values are based on the published International Tables of Glycemic Index
  (Atkinson, Foster-Powell & Brand-Miller, *Diabetes Care*, 2008). Available carbohydrate
  (total carbohydrate minus fiber) per 100 g is approximate, rounded from typical USDA
  FoodData Central values. The table is for education, not clinical use.
- Portions must be given in grams; "2 slices" or "a bowl" will make the agent ask.
- Food names are matched exactly or by alias, with no fuzzy matching, so unknown foods are reported rather than guessed.
- Swaps use the table's serving size for the new food unless the user gives a portion.
- GL describes a food, not a person: real blood-sugar responses vary between people.
- Results from the model can differ between runs; Python's checks make sure accepted answers are still backed by tool results.