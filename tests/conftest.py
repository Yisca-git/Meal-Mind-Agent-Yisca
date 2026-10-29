import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from anthropic.types import TextBlock, ToolUseBlock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def usage(i=100, o=20, read=0, write=0):
    return SimpleNamespace(input_tokens=i, output_tokens=o, cache_read_input_tokens=read,
                           cache_creation_input_tokens=write)


def text(t, **u):
    return SimpleNamespace(content=[TextBlock(type="text", text=t)], stop_reason="end_turn", usage=usage(**u))


def calls(*specs, **u):
    """One assistant message with several parallel tool calls: (name, input)."""
    blocks = [ToolUseBlock(type="tool_use", id=f"toolu_{n}", name=name, input=args)
              for n, (name, args) in enumerate(specs)]
    return SimpleNamespace(content=blocks, stop_reason="tool_use", usage=usage(**u))


class FakeClient:
    """Stands in for anthropic.Anthropic(): replays scripted responses and records every request."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.script.pop(0)


@pytest.fixture
def state(tmp_path):
    return tmp_path / "state"
