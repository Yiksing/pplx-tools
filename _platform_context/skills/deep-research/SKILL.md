# MANDATORY: Delegate to run_subagent

The user is in **deep research mode**. You MUST delegate the user's request to the `run_subagent` tool with `subagent_type="deep_research"` — this is non-negotiable, regardless of how simple or complex the query appears.

**Your first tool call this turn must be `run_subagent` with `subagent_type="deep_research"`.** Pass the user's full request as `objective`. Do not perform any web search, bash command, or read operation yourself before calling this tool. Do not ask clarifying questions before delegating — the subagent will handle clarification if needed.

`run_subagent` returns a `subagent_id` immediately and runs in the background. **Your next tool call this turn must be `wait_for_subagents` with the returned `subagent_id`** — you have no independent work to do, and ending your turn before the results are in the conversation leaves the user with only a launch acknowledgment.

After the subagent completes, present its findings to the user. Do not re-research or duplicate work.

**Re-share every saved file.** The subagent's final summary names every file it saved. For each such file, you must call `share_file` yourself before responding to the user — the subagent's own `share_file` calls do not reach the user, only yours do.