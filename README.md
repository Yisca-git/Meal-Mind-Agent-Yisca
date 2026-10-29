# Meal-Mind

A meal and shopping planner agent, built twice on the same tools and data and then measured:

- `API/` — the raw Anthropic Messages API. The whole harness (loop, tools, history, memory, context, compaction, caching, token metering) is hand-written in `API/harness/`, one file per responsibility.
- `SDK/` — the Claude Agent SDK. Claude Code runs the harness; this version only configures it. Every line that replaces a harness file is tagged `# replaces: <name>`.
- `shared/` — the domain code both versions use: 8 tools (7 local, 1 external via TheMealDB), recipes, allergen/diet safety checks, the scenario runner and the pass/fail checks.

The agent remembers allergies, diet and servings between sessions, plans dinners, builds a shopping list minus the pantry, and refuses requests that contradict saved preferences (for example a pistachio cake with a nut allergy).

## Results

Same scenario (7 turns, 2 sessions, 8 state-based checks), same model (`claude-opus-5-5`, effort `medium`), one run each:

| | API | SDK |
|---|---|---|
| checks passed | 8/8 | 8/8 |
| model calls | 22 | 28 |
| cache hit | 89.0% | 93.5% |
| time | 63.5 s | 150 s |
| harness lines | 206 | 27 |

The full comparison, with caveats, is in [REPORT.md](REPORT.md) (written in Hebrew).

## Setup

Python 3.13.

```
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```
# offline tests (no key needed)
.venv\Scripts\python -m pytest tests -q

# API version: needs ANTHROPIC_API_KEY set in the terminal only (never in code or git)
.venv\Scripts\python API\main.py --scenario scenario.json --out results\api.json

# SDK version: runs on your Claude Code login; ANTHROPIC_API_KEY is ignored for this process
.venv\Scripts\python SDK\main.py --scenario scenario.json --out results\sdk.json
```

Each run starts from a clean state directory (`.runs/`, git-ignored). Library versions are pinned in `requirements.txt`.
