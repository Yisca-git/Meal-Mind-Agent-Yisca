"""Tool schemas for the API and dispatch of tool_use blocks to the shared kitchen code."""
from API.harness import trace
from shared.kitchen import ToolError, compact
from shared.tool_specs import TOOL_SPECS

MAX_RESULT_CHARS = 1500
NAMES = {t["name"] for t in TOOL_SPECS}


def schemas():
    return TOOL_SPECS


def dispatch(kitchen, name, args):
    """Run one tool. Returns (content, is_error); errors go back to the model instead of crashing the loop."""
    if name not in NAMES:
        return f"error: unknown tool {name}", True
    try:
        content = compact(getattr(kitchen, name)(**args))
        is_error = False
    except ToolError as exc:
        content, is_error = f"error: {exc}", True
    except TypeError as exc:
        content, is_error = f"error: bad arguments ({exc})", True
    if len(content) > MAX_RESULT_CHARS:
        content = content[:MAX_RESULT_CHARS] + "...[truncated]"
    trace("tools", f"{name}({args}) -> {'ERROR ' if is_error else ''}{len(content)} chars")
    return content, is_error
