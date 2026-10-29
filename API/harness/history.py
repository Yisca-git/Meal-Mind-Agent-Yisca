"""Conversation history: one append-only JSONL file per session."""
import json
from pathlib import Path

from API.harness import trace


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, message):
        self._write({"type": "message", "message": message})

    def compaction(self, summary, cut):
        """Recorded as an event, so the file stays append-only; load() replays it."""
        self._write({"type": "compaction", "summary": summary, "cut": cut})

    def _write(self, record):
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self):
        messages = []
        if not self.path.exists():
            return messages
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["type"] == "message":
                messages.append(record["message"])
            else:
                messages = [{"role": "user", "content": record["summary"]}] + messages[record["cut"]:]
        trace("history", f"loaded {len(messages)} messages from {self.path.name}")
        return messages
