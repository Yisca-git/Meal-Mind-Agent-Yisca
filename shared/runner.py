"""Scenario runner and results writer, identical for both harnesses so the comparison is fair."""
import json
import re
import shutil
from pathlib import Path

from shared import checks

ROOT = Path(__file__).resolve().parent.parent


def count_lines(path):
    """Non-blank, non-comment lines."""
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.strip().startswith("#"))


def api_line_counts():
    harness = ROOT / "API" / "harness"
    counts = {p.stem: count_lines(p) for p in sorted(harness.glob("*.py")) if p.stem != "__init__"}
    counts["total"] = sum(counts.values())
    return counts


def sdk_line_counts():
    """SDK lines are attributed by their `# replaces: <name>` tag."""
    counts = {}
    for path in (ROOT / "SDK").glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            tag = re.search(r"#\s*replaces:\s*([\w.]+)", line)
            if tag and line.strip() and not line.strip().startswith("#"):
                counts[tag.group(1)] = counts.get(tag.group(1), 0) + 1
    counts["total"] = sum(counts.values())
    return counts


def run_scenario(scenario, make_agent, state_dir, label, model, effort, line_counts):
    state_dir = Path(state_dir)
    shutil.rmtree(state_dir, ignore_errors=True)  # every run starts clean
    state_dir.mkdir(parents=True)
    turns = []
    for number, session in enumerate(scenario["sessions"], 1):
        agent = make_agent(number, session)  # a brand-new agent instance; state comes from disk
        try:
            for prompt in session["turns"]:
                record = agent.handle(prompt)
                turns.append({"session": number, "turn": len(turns) + 1, "prompt": prompt, **record})
        finally:
            agent.close()
    results = [{"id": c["id"], "desc": c["desc"], "passed": bool(checks.evaluate(c, state_dir, turns))}
               for c in scenario["checks"]]
    tokens = {k: sum(t["tokens"][k] for t in turns) for k in ("input", "cache_read", "cache_write", "output")}
    prompt_total = tokens["input"] + tokens["cache_read"] + tokens["cache_write"]
    return {
        "label": label, "model": model, "effort": effort, "turns": turns,
        "totals": {**tokens, "calls": sum(t["calls"] for t in turns),
                   "cost_usd": round(sum(t["cost_usd"] for t in turns), 4),
                   "seconds": round(sum(t["seconds"] for t in turns), 1),
                   "cache_hit_pct": round(100 * tokens["cache_read"] / prompt_total, 1) if prompt_total else 0.0},
        "checks": results, "checks_passed": f"{sum(c['passed'] for c in results)}/{len(results)}",
        "harness_lines": line_counts(),
    }


def write_results(results, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{results['label']}: checks {results['checks_passed']}, cost ${results['totals']['cost_usd']}, "
          f"calls {results['totals']['calls']} -> {out}")
    for c in results["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['desc']}")
