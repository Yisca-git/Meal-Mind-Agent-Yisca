# Meal-Mind: one agent, two harnesses

> **Status:** both versions ran the same scenario (`results/api.json`, `results/sdk.json`), and 23 offline tests pass. Every number below comes from the result files. Each version was run once, so there is no variance measurement.

## The agent
A meal and shopping planner. 8 tools in `shared/` (seven local, one external: TheMealDB), preferences stored on disk (allergies, diet, number of diners), and a scenario that includes a contradiction (a nut allergy versus a request for a pistachio cake).
Model: `claude-opus-5-5`, effort `medium`, in both versions. Libraries are pinned in `requirements.txt` (`anthropic==2.3.0`, `claude-agent-sdk==0.2.174`).

## Results (API vs SDK)

| Metric | API | SDK |
|---|---|---|
| input tokens (uncached) | 58 | 52 |
| cache read | 56,745 | 72,824 |
| cache write | 6,948 | 5,022 |
| output | 4,162 | 4,093 |
| total input processed (incl. cache) | 63,751 | 77,898 |
| cache hit rate | 89.0% | 93.5% |
| model calls | 22 | 28 |
| cost (USD) | 0.130 (estimated from tokens) | 0.137 (reported); 0.122 estimated from tokens |
| time | 63.5 s | 150 s |
| checks passed (of 8) | 8/8 | 8/8 |

Measurement notes:
- In the API version, cost is computed by my own `Meter` from a price list (cache write at 1.25× input, my assumption). There is no reported figure to compare it with.
- In the SDK, `usage` and `num_turns` are per query, while `total_cost_usd` is a running total per connection, so the per-turn cost is a difference. The first SDK run wrongly assumed `usage` was cumulative too; negative values exposed it, and it was fixed and re-run.
- The gap between the SDK's reported cost (0.137) and my estimate (0.122), about 12%, is unexplained.
- Cost has to be compared like for like. With the same estimate formula: API 0.130 vs SDK 0.122, so the SDK is 6% cheaper. With the SDK's reported figure: 0.137 vs 0.130, so the SDK is 6% more expensive. Either way the difference is small, and a single run cannot establish a direction.

Observations from the runs:
- **SDK:** in turn 3 the model called `lookup_external_recipe` 5 times, and in turn 7 it also searched the web for a recipe even though the request was going to be blocked. It refused to add the pistachio cake and offered nut-free alternatives.
- **API:** in turn 3 there were 3 calls to `lookup_external_recipe`. In turn 7 the agent refused to add the cake, searched for alternatives (one local and two external searches) and found no suitable cake.
- **API, turn 6:** the model wrote that "tomatoes 200 g" still appearing on the list after the pantry gained 1 kg was "probably a bug". It is not. The plan needs 1.2 kg, the pantry holds 1 kg, and exactly 200 g is missing. The model explained it wrongly; the tool calculated correctly.

## Lines of code per harness part (measured, excluding blank lines and comments)

| Part | API (`API/harness/`) | SDK (lines tagged `# replaces:`) |
|---|---|---|
| loop | 31 | 2 |
| tools | 23 | 13 |
| history | 28 | 1 |
| memory | 17 | 5 |
| context | 22 | 1 |
| compaction | 39 | 0 (automatic) |
| caching | 18 | 0 (automatic) |
| tokens | 28 | 5 |
| **Total** | **206** | **27** |

Note: the SDK side also keeps `SDK/agent.py`, `SDK/main.py` and the shared code in `shared/`. They are not counted here because they do not replace a harness file. The SDK count is made of lines I tagged by hand with `# replaces:`, so it is less objective than the API count, which counts whole files.

## Where the SDK used more tokens and where fewer
- **More input processed:** 77,898 vs 63,751, about 22% more. Almost all of it is extra cache read (72,824 vs 56,745). Output is nearly identical (4,093 vs 4,162), so the answers themselves are not longer.
- **Why, according to the data:** the SDK made 28 model calls vs 22, and every call resends the whole context (read from cache). Six extra calls explain most of the gap. The call gap comes mainly from turn 3, where the model searched 5 times instead of 3. I did not check what exactly Claude Code adds to the prompt, so that part is an untested hypothesis.
- **Less cache write in the SDK:** 5,022 vs 6,948. In the SDK the prefix is stable across turns and stays cached. In the API, the per-turn injection (a memory line, and sometimes plan or pantry) creates new messages that get written to the cache.
- **Cache hit rate:** both versions are at 89% or higher. My earlier hypothesis, that the API prefix was too short to cache, was refuted: 1,488 tokens were already read from the cache in turn 1.
- **Time:** 63.5 s for the API vs 150 s for the SDK, a factor of 2.4. I did not measure the cause. Plausible candidates are Claude Code's extra work per call and the 6 extra calls, but I did not isolate them.

## What control I had in the API and lost in the SDK
- **Per-turn context:** in the API, `context.py` decides exactly what goes in, and adds the plan or pantry only when the message is relevant. The SDK has no such hook. It has CLAUDE.md and tools, and the model retrieves what it needs itself.
- **Tool output:** in the API I truncate to 1500 characters. In the SDK, truncation is Claude Code's.
- **Cache breakpoints and compaction:** set manually in the API (3 breakpoints, compaction by threshold). Automatic in the SDK, and not tunable from here. In the main run compaction did not trigger in either version, because the scenario is short (the prompt peaks around 4,000 tokens). A separate low-threshold run is described in "Compaction run" below.
- **Memory:** in the SDK it is a CLAUDE.md file rewritten after `save_preference`. In the API it is selected by relevance and injected into the message.
- **What I did not lose:** both implementations passed 8/8 on the same scenario, including the refusal on the contradiction. The check that blocks a conflict with saved preferences lives in `shared/kitchen.py`, so the protection does not depend on the harness.

## Compaction run (API only, `results/api_compaction.json`)
To see `compaction.py` work in practice, I ran the API version with `--compact-at 3500`. The main comparison run kept the default threshold (60,000), so its conditions match the SDK's.
- **Compaction fired at the start of turn 4:** `summarizing 12 messages (prompt is 3628 tokens)`. The prompt of the next call dropped to about 2,900 tokens, and all 8 checks passed.
- **Cost went up, not down:** turn 4 cost $0.040 vs about $0.021 in the main run, and the total was $0.136 vs $0.130. The reason: the summary is an extra model call (about 1,100 uncached input tokens and 470 output tokens), and the cache is broken because the start of the conversation changed. The cache hit rate fell from 89.0% to 84.5%.
- **Conclusion:** in a short conversation compaction does not pay off. It exists for long conversations, where the saving on every call after compaction exceeds the cost of the summary. This is a single run, so the small difference in total cost is not significant, but the direction in turn 4 is clear.
- **A bug the run exposed:** `find_cut` looked for a real user message only within the last 4 messages. After a turn with tools, all of those are tool messages, so compaction would always have been skipped. It is fixed, and an offline test was added (23 in total). Also, the trace line in `tokens.py` printed per-turn running sums instead of per-call usage, and that was fixed too. The result files were not affected. The main run `api.json` was made before the fix, but compaction did not trigger in it, so it was not affected.

## Which version I would choose
**The SDK by default, for an agent like this.** It passed the same 8 checks with 27 lines against 206, without implementing the loop, caching and compaction myself. Its cost was roughly equal to the API's (a difference of about 6%, in an unstable direction), and the quality did not look worse.

**The API is better when time or control matters.** It was 2.4 times faster in my run, and it lets me decide exactly what goes into each query, what gets truncated and when to compact. If the agent grows to long conversations or to usage volumes where every token counts, that control pays off. This scenario is short, so I did not prove it.

Limitations of the comparison: one run per version, a non-deterministic model (for example 5 searches vs 3), an API cost computed from my own price assumption, and an unexplained cost gap in the SDK.

## Running
```
# API (requires ANTHROPIC_API_KEY as an environment variable in the terminal only)
.venv\Scripts\python API\main.py --scenario scenario.json --out results\api.json
# SDK (uses the Claude Code login; the key is ignored for this process)
.venv\Scripts\python SDK\main.py --scenario scenario.json --out results\sdk.json
# Offline tests
.venv\Scripts\python -m pytest tests -q
```
