"""Meal-Mind on the raw Messages API: wires the harness modules together."""
from pathlib import Path

from API.harness import compaction, context, trace
from API.harness.history import History
from API.harness.loop import run_turn
from API.harness.tokens import Meter
from shared.kitchen import Kitchen
from shared.tool_specs import SYSTEM_PROMPT


class MealAgent:
    def __init__(self, state_dir, client, model, effort, session_no, resume_from=None, compact_at=60000):
        self.client, self.model, self.effort, self.compact_at = client, model, effort, compact_at
        self.kitchen = Kitchen(state_dir)
        self.history = History(Path(state_dir) / "api_history" / f"session-{session_no}.jsonl")
        self.meter = Meter(model)
        # A new instance starts with an empty conversation; only explicit resume reloads old messages.
        self.messages = History(Path(state_dir) / "api_history" / f"session-{resume_from}.jsonl").load() \
            if resume_from else []
        trace("history", f"session {session_no} started with {len(self.messages)} messages")

    def handle(self, user_text):
        self.meter.start_turn()
        self.messages = compaction.maybe_compact(self.client, self.model, self.messages, self.history,
                                                 self.meter, self.compact_at)
        extra = context.build(self.kitchen, user_text)
        message = {"role": "user", "content": f"[context]\n{extra}\n[/context]\n{user_text}" if extra else user_text}
        self.messages.append(message)
        self.history.append(message)
        reply = run_turn(self.client, model=self.model, effort=self.effort, system=SYSTEM_PROMPT,
                         messages=self.messages, history=self.history, kitchen=self.kitchen, meter=self.meter)
        return {"reply": reply, **self.meter.end_turn()}

    def close(self):
        pass
