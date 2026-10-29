import json

from tests.conftest import FakeClient, calls, text

from API.agent import MealAgent
from API.harness import caching, compaction, context, tools
from API.harness.history import History
from API.harness.tokens import Meter
from shared.kitchen import Kitchen


def make_agent(state, script, session_no=1, **kw):
    client = FakeClient(script)
    return MealAgent(state, client, "claude-opus-5-5", "medium", session_no, **kw), client


def test_loop_runs_tools_until_end_turn_and_batches_results(state):
    agent, client = make_agent(state, [
        calls(("save_preference", {"key": "allergies", "value": "nuts"}),
              ("save_preference", {"key": "diet", "value": "vegetarian"})),
        text("saved")])
    record = agent.handle("I am allergic to nuts and vegetarian")
    assert record["reply"] == "saved" and record["calls"] == 2
    assert record["tools"] == ["save_preference", "save_preference"]
    second = client.requests[1]["messages"]
    results = second[-1]["content"]
    assert second[-1]["role"] == "user" and len(results) == 2  # both tool_results in ONE message
    assert Kitchen(state).prefs()["allergies"] == ["nuts"]


def test_tool_errors_go_back_to_the_model_as_is_error(state):
    agent, client = make_agent(state, [
        calls(("add_to_meal_plan", {"day": "thu", "meal": "dinner", "recipe_id": "nope"})), text("sorry")])
    agent.handle("add something")
    result = client.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and result["content"].startswith("error:")


def test_unknown_tool_and_bad_arguments_do_not_crash(state):
    kitchen = Kitchen(state)
    assert tools.dispatch(kitchen, "rm_rf", {})[1] is True
    content, is_error = tools.dispatch(kitchen, "save_preference", {"wrong": 1})
    assert is_error and "bad arguments" in content


def test_tool_output_is_truncated(state):
    kitchen = Kitchen(state)
    kitchen.search_recipes = lambda **kw: {"results": ["x" * 5000]}
    content, _ = tools.dispatch(kitchen, "search_recipes", {})
    assert len(content) < tools.MAX_RESULT_CHARS + 20


def test_history_is_append_only_and_reloads(state):
    agent, _ = make_agent(state, [text("hi")])
    agent.handle("hello")
    path = state / "api_history" / "session-1.jsonl"
    before = path.read_text(encoding="utf-8")
    loaded = History(path).load()
    assert [m["role"] for m in loaded] == ["user", "assistant"]
    agent2, client2 = make_agent(state, [text("again")], session_no=2, resume_from=1)
    agent2.handle("more")
    assert len(client2.requests[0]["messages"]) == 3  # resumed 2 old messages + the new one
    assert path.read_text(encoding="utf-8") == before  # session 2 wrote to its own file; session 1 untouched


def test_new_instance_starts_empty_but_reads_memory_from_disk(state):
    first, _ = make_agent(state, [calls(("save_preference", {"key": "allergies", "value": "nuts"})), text("ok")])
    first.handle("allergic to nuts")
    second, client = make_agent(state, [text("you avoid nuts")])
    second.handle("what do you remember?")
    sent = client.requests[0]["messages"]
    assert len(sent) == 1 and "allergies: nuts" in json.dumps(sent[0], ensure_ascii=False)


def test_context_only_adds_plan_and_pantry_when_relevant(state):
    k = Kitchen(state)
    k.add_to_meal_plan("sun", "dinner", "r01")
    k.update_pantry([{"name": "rice", "qty": 1, "unit": "kg"}])
    assert "plan:" not in context.build(k, "hello")
    assert "plan:" in context.build(k, "show me the plan")
    assert "pantry:" in context.build(k, "מה יש במלאי")


def test_caching_marks_three_breakpoints_without_mutating_history():
    messages = [{"role": "user", "content": "hi"}]
    system, tool_defs, msgs = caching.apply("sys", [{"name": "a"}, {"name": "b"}], messages)
    marked = [system[0], tool_defs[-1], msgs[-1]["content"][-1]]
    assert all(m["cache_control"] == {"type": "ephemeral"} for m in marked)
    assert "cache_control" not in tool_defs[0] and messages == [{"role": "user", "content": "hi"}]


def test_compaction_summarizes_old_turns_and_keeps_pairing(state):
    agent, client = make_agent(state, [text("a1"), text("a2"), text("SUMMARY"), text("a3")], compact_at=50)
    for q in ("q1", "q2", "q3"):
        agent.handle(q)  # q1/q2: too short to cut; q3: previous call used 100 tokens > 50 -> summary call first
    assert agent.messages[0]["content"].startswith("[summary")
    assert [m["role"] for m in agent.messages] == ["user", "user", "assistant", "user", "assistant"]
    assert "SUMMARY" in agent.messages[0]["content"]
    reloaded = History(state / "api_history" / "session-1.jsonl").load()
    assert reloaded == agent.messages  # compaction replays from the append-only file


def test_find_cut_works_when_the_tail_is_only_tool_messages():
    tool_use = {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "x", "input": {}}]}
    result = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}
    messages = [{"role": "user", "content": "q1"}, {"role": "assistant", "content": [{"type": "text", "text": "a1"}]},
                {"role": "user", "content": "q2"}, tool_use, result, tool_use, result,
                {"role": "assistant", "content": [{"type": "text", "text": "a2"}]}]
    cut = compaction.find_cut(messages, keep_last=4)
    assert cut == 2 and messages[cut]["content"] == "q2"  # the kept tail starts at a real user message


def test_meter_costs_cache_tiers_separately():
    from tests.conftest import usage
    meter = Meter("claude-opus-5-5")
    meter.record(usage(i=1_000_000, o=0))
    meter.record(usage(i=0, o=1_000_000, read=1_000_000, write=1_000_000))
    turn = meter.end_turn()
    assert turn["calls"] == 2 and turn["cost_usd"] == 4.0 + 20.0 + 0.2 + 5.0
