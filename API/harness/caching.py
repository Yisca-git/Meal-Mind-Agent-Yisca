import copy

from API.harness import trace

EPHEMERAL = {"type": "ephemeral"}


def apply(system_text, tools, messages):
    """Return request copies with 3 cache breakpoints: last tool, system, and the newest message.

    Stored history is never mutated, so old breakpoints do not pile up past the limit of 4.
    """
    system = [{"type": "text", "text": system_text, "cache_control": EPHEMERAL}]
    tool_defs = [dict(t) for t in tools]
    tool_defs[-1]["cache_control"] = EPHEMERAL
    msgs = list(messages)
    last = copy.deepcopy(msgs[-1])
    if isinstance(last["content"], str):
        last["content"] = [{"type": "text", "text": last["content"]}]
    last["content"][-1]["cache_control"] = EPHEMERAL
    msgs[-1] = last
    trace("caching", "breakpoints on tools, system and last message")
    return system, tool_defs, msgs
