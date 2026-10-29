"""Meal-Mind on the Claude Agent SDK: Claude Code runs the harness, this file only configures it."""
import asyncio
import time
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, ToolUseBlock)

from SDK.tools import build_server
from shared.kitchen import Kitchen, render_memory_md
from shared.pricing import cost_usd
from shared.tool_specs import SYSTEM_PROMPT, TOOL_SPECS

TOKEN_KEYS = {"input": "input_tokens", "cache_read": "cache_read_input_tokens",
              "cache_write": "cache_creation_input_tokens", "output": "output_tokens"}


class SDKMealAgent:
    def __init__(self, state_dir, model, effort, resume=None):
        self.model = model
        self.kitchen = Kitchen(state_dir)
        self.workspace = Path(state_dir) / "sdk_workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.kitchen.prefs():  # replaces: memory
            (self.workspace / "CLAUDE.md").write_text(render_memory_md(self.kitchen.prefs()), encoding="utf-8")  # replaces: memory
        options = ClaudeAgentOptions(
            model=model, effort=effort,
            system_prompt=SYSTEM_PROMPT,  # replaces: context
            cwd=str(self.workspace),
            setting_sources=["project"],  # replaces: memory
            resume=resume,  # replaces: history
            tools=[],  # built-in Claude Code tools off
            allowed_tools=[f"mcp__meal__{s['name']}" for s in TOOL_SPECS],  # replaces: tools
            mcp_servers={"meal": build_server(self.kitchen, self.workspace)},  # replaces: tools
            strict_mcp_config=True, max_turns=12)
        self.client = ClaudeSDKClient(options)
        self.loop = asyncio.new_event_loop()
        self.session_id = None
        self.prev_cost = 0.0  # total_cost_usd is a running total per connection
        self.loop.run_until_complete(self.client.connect())

    def handle(self, text):
        return self.loop.run_until_complete(self._ask(text))

    async def _ask(self, text):
        started, tools = time.time(), []
        await self.client.query(text)  # replaces: loop
        async for message in self.client.receive_response():  # replaces: loop
            if isinstance(message, AssistantMessage):
                tools += [b.name.removeprefix("mcp__meal__") for b in message.content if isinstance(b, ToolUseBlock)]
            elif isinstance(message, ResultMessage):
                result = message
        usage = result.usage or {}  # replaces: tokens
        tokens = {k: usage.get(v, 0) or 0 for k, v in TOKEN_KEYS.items()}  # replaces: tokens (usage and num_turns are per query)
        cost = (result.total_cost_usd or 0.0) - self.prev_cost  # replaces: tokens (total_cost_usd is a running total)
        self.prev_cost = result.total_cost_usd or 0.0  # replaces: tokens
        self.session_id = result.session_id
        return {"reply": result.result or "", "tokens": tokens, "calls": result.num_turns, "tools": tools,
                "cost_usd": round(cost, 5), "cost_usd_estimate": round(cost_usd(self.model, tokens), 5),
                "seconds": round(time.time() - started, 2),
                "sdk_raw": {"usage": usage, "total_cost_usd": result.total_cost_usd, "num_turns": result.num_turns}}

    def close(self):
        self.loop.run_until_complete(self.client.disconnect())
        self.loop.close()
