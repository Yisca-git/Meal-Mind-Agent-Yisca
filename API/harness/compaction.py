"""Context window: summarize everything but the newest turns once the prompt passes a threshold."""
from API.harness import trace


def _is_user_text(message):
    content = message["content"]
    return message["role"] == "user" and (
        isinstance(content, str) or any(b.get("type") == "text" for b in content))


def find_cut(messages, keep_last):
    """Index where the kept tail starts: a real user message, so tool_use/tool_result pairs stay together."""
    for i in range(max(len(messages) - keep_last, 1), len(messages)):
        if _is_user_text(messages[i]):
            return i
    return 0


def render(messages):
    lines = []
    for m in messages:
        blocks = [{"type": "text", "text": m["content"]}] if isinstance(m["content"], str) else m["content"]
        for b in blocks:
            if b["type"] == "text":
                lines.append(f"{m['role']}: {b['text']}")
            elif b["type"] == "tool_use":
                lines.append(f"tool call {b['name']}({b['input']})")
            elif b["type"] == "tool_result":
                lines.append(f"tool result: {str(b['content'])[:300]}")
    return "\n".join(lines)


def maybe_compact(client, model, messages, history, meter, threshold, keep_last=4):
    if meter.last_prompt_tokens < threshold:
        return messages
    cut = find_cut(messages, keep_last)
    if cut == 0:
        return messages
    response = client.messages.create(
        model=model, max_tokens=800, output_config={"effort": "low"},
        system="Summarize this meal-planning conversation for your own later use: preferences, decisions, "
               "plan and pantry changes, open questions. Be brief and factual.",
        messages=[{"role": "user", "content": render(messages[:cut])}])
    meter.record(response.usage)
    summary = "[summary of earlier conversation]\n" + "".join(b.text for b in response.content if b.type == "text")
    history.compaction(summary, cut)
    trace("compaction", f"summarized {cut} messages (prompt was {meter.last_prompt_tokens} tokens)")
    return [{"role": "user", "content": summary}] + messages[cut:]
