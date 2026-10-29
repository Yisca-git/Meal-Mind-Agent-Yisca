import time

from API.harness import trace
from shared.pricing import cost_usd


class Meter:
    """Usage and cost per turn, summed over every model call in the turn."""

    def __init__(self, model):
        self.model = model
        self.last_prompt_tokens = 0
        self.start_turn()

    def start_turn(self):
        self.t = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
        self.calls, self.tools, self.started = 0, [], time.time()

    def record(self, usage):
        self.t["input"] += usage.input_tokens or 0
        self.t["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.t["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.t["output"] += usage.output_tokens or 0
        self.calls += 1
        self.last_prompt_tokens = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        trace("tokens", f"call {self.calls}: {self.t}")

    def tool(self, name):
        self.tools.append(name)

    def end_turn(self):
        cost = cost_usd(self.model, self.t)
        trace("tokens", f"turn cost ${cost:.4f} over {self.calls} calls")
        return {"tokens": dict(self.t), "calls": self.calls, "tools": list(self.tools),
                "cost_usd": round(cost, 5), "seconds": round(time.time() - self.started, 2)}
