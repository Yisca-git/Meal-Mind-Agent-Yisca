"""python SDK/main.py --scenario scenario.json --out results/sdk.json  (runs on your Claude Code login)"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from SDK.agent import SDKMealAgent  # noqa: E402
from shared import runner  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="scenario.json")
    parser.add_argument("--out", default="results/sdk.json")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--state-dir", default=str(ROOT / ".runs" / "sdk"))
    args = parser.parse_args()
    if os.environ.pop("ANTHROPIC_API_KEY", None):  # only for this process: bill the login, not the key
        print("ANTHROPIC_API_KEY ignored for this run so usage is billed to your Claude Code login")
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    previous = []  # finished agents keep their session_id, so a session can opt in to resume

    def make_agent(number, session):
        resume = previous[-1].session_id if previous and session.get("resume_history") else None
        previous.append(SDKMealAgent(args.state_dir, args.model, args.effort, resume))
        return previous[-1]

    results = runner.run_scenario(scenario, make_agent, args.state_dir, "sdk",
                                  args.model, args.effort, runner.sdk_line_counts)
    runner.write_results(results, args.out)


if __name__ == "__main__":
    main()
