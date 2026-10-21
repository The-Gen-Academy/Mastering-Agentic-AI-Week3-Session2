# GTM Deep Agent

A teaching tutorial of the **Deep Agents** framework (LangChain's batteries-included agent
layer on LangGraph). The driver is the notebook **`gtm_deep_agent.ipynb`**.

**Use case:** a GTM content assistant that drafts a LinkedIn post and a marketing email for
[The Gen Academy](https://thegenacademy.com), using an orchestrator + four specialist
subagents. Draft-only — nothing is ever actually posted or sent.

## Setup (uv)

```bash
uv sync --locked              # install the reviewed dependency set into .venv
cp .env.example .env          # then add your OPENAI_API_KEY (Tavily optional)
```

The notebook targets **Deep Agents 0.7.28**. Open `gtm_deep_agent.ipynb` and select the
project's `.venv` as the kernel. Restart the kernel after upgrading, then run the cells
top to bottom. If keys aren't in `.env`, the notebook prompts for them.

Section 9 displays every proposed publication and prompts for approval, rejection with
feedback, or edited arguments. Press Enter to leave the run paused; rerun that review cell
to continue. Successful simulated tool receipts determine the reported publication status.

## Layout

| Path | What it is |
|---|---|
| `gtm_deep_agent.ipynb` | The tutorial — run/explain cell by cell |
| `grounding/gen_academy.md` | Brand facts the agent is grounded in |
| `skills/linkedin-style/SKILL.md` | LinkedIn voice guide (loaded on demand) |
| `skills/email-style/SKILL.md` | Email voice guide (loaded on demand) |
| `research/`, `drafts/`, `final/` | Created at runtime by the agent (gitignored) |
| `artifacts/` | Internal context-management artifacts (gitignored) |

## Concepts demonstrated

Optional planning (`TodoListMiddleware` / `write_todos`) is explicitly enabled on the
orchestrator. Four custom specialists use isolated context, explicit grounding-file reads,
and campaign requirements supplied in each delegation. Shared disk artifacts carry handoffs;
the orchestrator's todo list is not shared with specialists.

Skills load on demand. `StoreBackend` stores memory across threads using the same store;
`memory=` loads the saved brand-voice note into the orchestrator's prompt in a fresh thread,
and `read_file` supports explicit recall. `InMemoryStore` and `MemorySaver` both lose their
contents on kernel restart or recreation; disk artifacts remain. Use a durable store and
checkpointer for persistence across process restarts.

Filesystem permissions keep grounding and skills read-only and limit writes to generated
outputs, internal artifacts, and memory. Other project files are inaccessible through the
built-in filesystem tools. `recursion_limit` bounds graph steps, not total tokens or spend.

The notebook uses editable text diagrams for the updated architecture, backend, assembly,
state, approval, and memory explanations. Original image assets remain in `images/`.

## Recovering a step-limit stop

The campaign uses `recursion_limit=200`. This counts graph execution steps, including
middleware, rather than model calls or campaign tasks. A normal multi-stage campaign can
exceed the previous limit of 60.

`invoke_with_diagnostics` reports a step-limit stop and returns marked partial progress
from the checkpoint. Inspect the recent activity before continuing: repeated errors or
unproductive revisions should be investigated rather than repeatedly raising the cap.
To resume useful progress, keep the same kernel, agent, checkpointer, and thread:

```python
config = {**config, "recursion_limit": 200}
result = invoke_with_diagnostics(agent, None, config)
```

Do not rerun the campaign-start cell: it generates a new thread and submits the brief again.
Approval interrupts still require the explicit decisions in Section 9. The helper does not
retry automatically or approve publications, and partial results are not treated as a
completed campaign.

## Offline checks

```bash
uv run --locked python -m unittest discover -s tests -v
```

These checks execute the notebook's setup with scripted models in temporary workspaces.
They cover planning isolation, inherited filesystem permissions, memory loading across
threads, approval/rejection/editing, repeated interrupts, and publication receipts.
They also exercise step-limit recovery without repeating completed work or bypassing review.
They make no paid model calls and do not validate generated campaign quality.
