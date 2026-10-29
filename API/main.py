"""python API/main.py --scenario scenario.json --out results/api.json  (needs ANTHROPIC_API_KEY in the environment)"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402

from API.agent import MealAgent  # noqa: E402
from shared import runner  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="scenario.json")
    parser.add_argument("--out", default="results/api.json")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--state-dir", default=str(ROOT / ".runs" / "api"))
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in your terminal first (never in code or git).")
    client = anthropic.Anthropic()
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))

    def make_agent(number, session):
        resume_from = number - 1 if session.get("resume_history") else None
        return MealAgent(args.state_dir, client, args.model, args.effort, number, resume_from)

    results = runner.run_scenario(scenario, make_agent, args.state_dir, "api", args.model, args.effort,
                                  runner.api_line_counts)
    runner.write_results(results, args.out)


if __name__ == "__main__":
    main()
