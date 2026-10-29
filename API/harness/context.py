"""Context engineering: decide what extra information rides along with each user turn."""
from API.harness import memory, trace

PLAN_WORDS = ("תכנית", "תוכנית", "תכנון", "שבוע", "ארוחה", "ארוחות", "plan", "menu", "week")
SHOP_WORDS = ("קניות", "רשימה", "מלאי", "קניתי", "shopping", "pantry", "list")


def build(kitchen, user_text):
    text = user_text.lower()
    lines = []
    mem = memory.essentials(kitchen)
    if mem:
        lines.append(f"memory: {mem}")
    lines += [f"note: {n}" for n in memory.relevant_notes(kitchen, user_text)]
    if any(w in text for w in PLAN_WORDS):
        plan = [f"{p['day']}/{p['meal']}={p['name']}" for p in kitchen.plan()]
        if plan:
            lines.append("plan: " + "; ".join(plan))
    if any(w in text for w in SHOP_WORDS):
        pantry = kitchen.check_pantry()["pantry"]
        if pantry:
            lines.append("pantry: " + ", ".join(pantry))
    block = "\n".join(lines)
    trace("context", f"injected {len(lines)} lines ({len(block)} chars) into the turn")
    return block
