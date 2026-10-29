"""The agent loop: call the model while it asks for tools, answer all tool_use blocks in one message."""
from API.harness import caching, tools, trace

MAX_ITERATIONS = 10


def _as_dict(block):
    return block.model_dump(exclude_none=True)


def run_turn(client, *, model, effort, system, messages, history, kitchen, meter, max_tokens=8000):
    """Append assistant/tool messages to `messages` and `history`; return the final text."""
    for _ in range(MAX_ITERATIONS):
        system_blocks, tool_defs, request_messages = caching.apply(system, tools.schemas(), messages)
        response = client.messages.create(
            model=model, max_tokens=max_tokens, system=system_blocks, tools=tool_defs,
            messages=request_messages, thinking={"type": "adaptive"}, output_config={"effort": effort})
        meter.record(response.usage)
        assistant = {"role": "assistant", "content": [_as_dict(b) for b in response.content]}
        messages.append(assistant)
        history.append(assistant)
        trace("loop", f"stop_reason={response.stop_reason}")
        if response.stop_reason == "pause_turn":
            continue
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")
        results = []
        for block in (b for b in response.content if b.type == "tool_use"):
            content, is_error = tools.dispatch(kitchen, block.name, block.input)
            meter.tool(block.name)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content,
                            **({"is_error": True} if is_error else {})})
        result_message = {"role": "user", "content": results}
        messages.append(result_message)
        history.append(result_message)
    return "(stopped: tool loop limit reached)"
