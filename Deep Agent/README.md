# GTM Deep Agent

A teaching tutorial of the **Deep Agents** framework (LangChain's batteries-included agent
layer on LangGraph). The driver is the notebook **`gtm_deep_agent.ipynb`**.

**Use case:** a GTM content assistant that drafts a LinkedIn post and a marketing email for
[The Gen Academy](https://thegenacademy.com), using an orchestrator + four specialist
subagents. Draft-only — nothing is ever actually posted or sent.

## Setup (uv)

```bash
uv sync                       # install dependencies into .venv
cp .env.example .env          # then add your OPENAI_API_KEY (Tavily optional)
```

Open `gtm_deep_agent.ipynb` and select the project's `.venv` as the kernel, then run the
cells top to bottom. (If keys aren't in `.env`, the notebook prompts for them.)

## Layout

| Path | What it is |
|---|---|
| `gtm_deep_agent.ipynb` | The tutorial — run/explain cell by cell |
| `grounding/gen_academy.md` | Brand facts the agent is grounded in |
| `skills/linkedin-style/SKILL.md` | LinkedIn voice guide (loaded on demand) |
| `skills/email-style/SKILL.md` | Email voice guide (loaded on demand) |
| `research/`, `drafts/`, `final/` | Created at runtime by the agent (gitignored) |

## Concepts demonstrated

Planning (`write_todos`) · subagent delegation (`task`) with isolated context · shared
filesystem state · skills (progressive disclosure) · cross-session memory via a `Store` ·
human-in-the-loop approval · `recursion_limit` as the runaway-loop backstop.
