"""The shared kitchen tools exposed to Claude Code as an in-process MCP server."""
from claude_agent_sdk import create_sdk_mcp_server, tool

from shared.kitchen import ToolError, compact, render_memory_md
from shared.tool_specs import TOOL_SPECS


def build_server(kitchen, workspace):  # replaces: tools
    return create_sdk_mcp_server("meal", tools=[_wrap(kitchen, workspace, s) for s in TOOL_SPECS])  # replaces: tools


def _wrap(kitchen, workspace, spec):  # replaces: tools
    @tool(spec["name"], spec["description"], spec["input_schema"])  # replaces: tools
    async def run(args):  # replaces: tools
        try:  # replaces: tools
            text, error = compact(getattr(kitchen, spec["name"])(**args)), False  # replaces: tools
        except (ToolError, TypeError) as exc:  # replaces: tools
            text, error = f"error: {exc}", True  # replaces: tools
        if spec["name"] == "save_preference" and not error:  # replaces: memory
            (workspace / "CLAUDE.md").write_text(render_memory_md(kitchen.prefs()), encoding="utf-8")  # replaces: memory
        return {"content": [{"type": "text", "text": text}], "is_error": error}  # replaces: tools
    return run  # replaces: tools
