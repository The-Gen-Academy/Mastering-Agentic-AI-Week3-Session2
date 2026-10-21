"""Course Platform MCP server.

The intent layer over the course platform's CRUD API. Deliberately NOT a
1:1 mapping of the REST endpoints — each tool is named for a sentence a
human would actually say, accepts human references instead of IDs, returns
formatted summaries instead of raw JSON, and encodes domain rules the API
doesn't know about.

Tools:
  1. get_schedule(week?)                      "What's happening in Week 2?"
  2. get_session_details(session)             "Get me the slides link for the NVIDIA lecture"
  3. publish_recording(session, recording_url) "The recording for Live Session 1 is up"
  4. whats_next()                             "What should I focus on?"

Transport: stdio (launched by Claude Code via .mcp.json).
"""

from contextlib import contextmanager
from datetime import datetime, time
from difflib import SequenceMatcher
import os
from typing import Iterator

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

API = os.environ.get("COURSE_API_URL", "http://localhost:8000")

mcp = MCPServer("course-platform", version="0.1.0")

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


# ---------------------------------------------------------------------------
# Helpers: API access, name resolution, formatting
# ---------------------------------------------------------------------------


@contextmanager
def _api() -> Iterator[httpx.Client]:
    try:
        with httpx.Client(
            base_url=API, timeout=10.0, event_hooks={"response": [_check_response]}
        ) as client:
            yield client
    except httpx.RequestError as exc:
        raise ToolError(
            "Cannot reach the course API. Start the FastAPI backend and check "
            "COURSE_API_URL (default: http://localhost:8000)."
        ) from exc


def _check_response(response: httpx.Response) -> None:
    """Expose actionable HTTP failures through the v2 tool error boundary."""
    if response.is_error:
        raise ToolError(
            f"The course API returned HTTP {response.status_code}. "
            "Check that the backend is running and the requested item still exists."
        )


def _fetch_items(client: httpx.Client) -> list[dict]:
    return client.get("/items").json()


_STOPWORDS = {"the", "a", "an", "one", "for", "of", "on", "to"}


def _norm_tokens(s: str) -> list[str]:
    """Lowercase, strip punctuation, drop filler words."""
    for ch in "-:,[]()":
        s = s.replace(ch, " ")
    return [tok for tok in s.lower().split() if tok not in _STOPWORDS]


def _digit_pairs(tokens: list[str]) -> set[tuple[str, str]]:
    """Positional (word, number) pairs: 'session 1 week 2' -> {(session,1),(week,2)}.

    Set-membership of digits isn't enough — 'Live Session 2 - Week 1' contains
    both digits, so only the pairing distinguishes it from 'Live Session 1 - Week 2'.
    """
    return {
        (tokens[i - 1], tok)
        for i, tok in enumerate(tokens)
        if tok.isdigit() and i > 0
    }


def _score(query: str, title: str) -> float:
    """Similarity between a human reference and an item title."""
    q_tokens, t_tokens = _norm_tokens(query), _norm_tokens(title)
    nq, nt = " ".join(q_tokens), " ".join(t_tokens)

    if nq == nt:
        return 1.0
    score = SequenceMatcher(None, nq, nt).ratio()
    if nq and nq in nt:
        score = max(score, 0.85)

    # Token overlap: "nvidia lecture" should hit
    # "Optional: Chris Alexiuk - NVIDIA - Guest Lecture".
    q_set = {tok for tok in q_tokens if len(tok) > 2 or tok.isdigit()}
    t_set = {tok for tok in t_tokens if len(tok) > 2 or tok.isdigit()}
    if q_set:
        score = max(score, len(q_set & t_set) / len(q_set) * 0.9)

    # Mismatched (word, number) pairs are near-disqualifying: "session 1"
    # must not resolve to a title that only has "session 2".
    q_pairs = _digit_pairs(q_tokens)
    if q_pairs and not q_pairs <= _digit_pairs(t_tokens):
        score *= 0.6
    return score


def _resolve(client: httpx.Client, session: str) -> dict | str:
    """Resolve a human reference to one item.

    Returns the item dict on success, or a conversational error/disambiguation
    string the model can act on.
    """
    items = _fetch_items(client)
    if not items:
        return "The curriculum is empty; there are no sessions to look up."
    scored = sorted(
        ((_score(session, item["title"]), item) for item in items),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best = scored[0]

    if best_score < 0.4:
        titles = "\n".join(f"  - {item['title']}" for item in items)
        return (
            f"I couldn't find anything in the curriculum matching \"{session}\". "
            f"Here is everything on the schedule:\n{titles}"
        )

    # Ambiguous if the runner-up is nearly as good a match — but an
    # (effectively) exact match is never ambiguous.
    runner_score, runner = scored[1] if len(scored) > 1 else (0.0, None)
    if (
        best_score < 0.95
        and runner is not None
        and best_score - runner_score < 0.1
        and runner_score >= 0.4
    ):
        return (
            f"\"{session}\" could refer to more than one thing — did you mean "
            f"\"{best['title']}\" or \"{runner['title']}\"? Please be a bit more specific."
        )

    return best


def _fmt_date(iso_date: str | None) -> str:
    if not iso_date:
        return "undated"
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%a, %b %-d")


def _fmt_time_range(item: dict) -> str:
    if not item.get("start_time"):
        return ""
    return f"{item['start_time']}–{item['end_time']} ({item['timezone']})"


def _fmt_resource(res: dict) -> str:
    if res["kind"] == "text":
        return f"{res['label']}: {res['text']}"
    if res["url"]:
        return f"{res['label']}: {res['url']}"
    return f"{res['label']}: (not published yet)"


def _item_line(item: dict) -> str:
    parts = [f"**{item['title']}**"]
    if item.get("date"):
        when = _fmt_date(item["date"])
        times = _fmt_time_range(item)
        parts.append(f"— {when}" + (f", {times}" if times else ""))
    if item.get("optional"):
        parts.append("[optional]")
    if item.get("completed"):
        parts.append("[done ✓]")
    return " ".join(parts)


def _session_end(item: dict) -> datetime:
    """Best-effort end-of-session timestamp for past/future checks."""
    d = datetime.strptime(item["date"], "%Y-%m-%d").date()
    if item.get("end_time"):
        h, m = item["end_time"].split(":")
        return datetime.combine(d, time(int(h), int(m)))
    return datetime.combine(d, time(23, 59))


# ---------------------------------------------------------------------------
# Tool 1 — orientation / browse
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def get_schedule(week: int | None = None) -> str:
    """Show the course schedule as a chronological digest.

    Use this when the user wants an overview: "what's happening this week",
    "show me week 2", "what's on the curriculum". Pass a week number to
    narrow to one week; omit it for the full course.
    """
    with _api() as client:
        course = client.get("/curriculum").json()

    weeks = course["weeks"]
    if week is not None:
        weeks = [w for w in weeks if w["number"] == week]
        if not weeks:
            available = ", ".join(str(w["number"]) for w in course["weeks"])
            return f"There is no Week {week} in this course. Available weeks: {available}."

    lines = [f"# {course['title']}"]
    for w in weeks:
        lines.append(
            f"\n## Week {w['number']}: {w['title']} "
            f"({_fmt_date(w['start_date'])} – {_fmt_date(w['end_date'])})"
        )
        dated = sorted(
            (i for i in w["items"] if i.get("date")), key=lambda i: (i["date"], i.get("start_time") or "")
        )
        undated = [i for i in w["items"] if not i.get("date")]
        for item in dated + undated:
            lines.append(f"- {_item_line(item)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2 — fetch details / links for one session
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def get_session_details(session: str) -> str:
    """Get full details for one curriculum item: timing and all its
    resources (recording, slides, notes) with their links.

    Use this when the user asks about a specific session by name — e.g.
    "when is the NVIDIA guest lecture?", "get me the slides link for Live
    Session 1". Accepts informal references; you don't need an exact title.
    """
    with _api() as client:
        result = _resolve(client, session)
    if isinstance(result, str):
        return result
    item = result

    lines = [_item_line(item)]
    if item["resources"]:
        lines.append("\nResources:")
        lines.extend(f"- {_fmt_resource(res)}" for res in item["resources"])
    else:
        lines.append("\nNo resources have been added to this item yet.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3 — guarded write: publish a recording
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def publish_recording(session: str, recording_url: str) -> str:
    """Publish the recording URL for a session that has already taken place.

    Use this when the user says a recording is ready — e.g. "the recording
    for Live Session 1 is up, here's the link". Replaces the session's
    'Recording' placeholder if one exists, otherwise adds a new Recording
    resource. Refuses sessions that haven't happened yet.
    """
    with _api() as client:
        result = _resolve(client, session)
        if isinstance(result, str):
            return result
        item = result

        if not item.get("date"):
            return (
                f"\"{item['title']}\" is a {item['type'].replace('_', ' ')} without a "
                "scheduled date, so it can't have a session recording. Did you mean one "
                "of the live sessions?"
            )

        if _session_end(item) > datetime.now():
            return (
                f"\"{item['title']}\" is scheduled for {_fmt_date(item['date'])} — it "
                "hasn't happened yet, so there's no recording to publish. Did you mean "
                "a session that already took place?"
            )

        existing = next(
            (r for r in item["resources"] if r["label"].lower() == "recording"), None
        )
        if existing:
            client.patch(
                f"/items/{item['id']}/resources/{existing['id']}",
                json={"url": recording_url},
            ).raise_for_status()
            action = "Updated the existing Recording link"
        else:
            client.post(
                f"/items/{item['id']}/resources",
                json={"label": "Recording", "kind": "link", "url": recording_url},
            ).raise_for_status()
            action = "Added a Recording link"

    return f"Published. {action} on \"{item['title']}\": {recording_url}"


# ---------------------------------------------------------------------------
# Tool 4 — pure intent composition: what should I do?
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def whats_next() -> str:
    """Tell the student what to focus on right now: anything they've missed,
    what's happening today, and what's coming up — required work first.

    Use this for questions like "what should I be doing?", "what's next?",
    "am I behind?". No arguments needed; it works from today's date and the
    student's completion state.
    """
    now = datetime.now()
    today = now.date()

    with _api() as client:
        items = _fetch_items(client)

    past_due, today_items, upcoming, anytime = [], [], [], []
    for item in items:
        if item["completed"]:
            continue
        if not item.get("date"):
            anytime.append(item)
            continue
        d = datetime.strptime(item["date"], "%Y-%m-%d").date()
        if d == today and _session_end(item) > now:
            today_items.append(item)
        elif _session_end(item) <= now:
            past_due.append(item)
        else:
            upcoming.append(item)

    upcoming.sort(key=lambda i: (i["date"], i.get("start_time") or ""))
    required_upcoming = [i for i in upcoming if not i["optional"]]
    optional_upcoming = [i for i in upcoming if i["optional"]]

    lines = [f"As of {now.strftime('%a, %b %-d %H:%M')}:"]

    if today_items:
        lines.append("\n**Happening today:**")
        lines.extend(f"- {_item_line(i)}" for i in today_items)

    catch_up = [i for i in past_due if not i["optional"]]
    if catch_up:
        lines.append("\n**To catch up on (already happened, not marked done):**")
        for i in catch_up:
            rec = next(
                (r for r in i["resources"] if r["label"].lower() == "recording" and r.get("url")),
                None,
            )
            note = f" — recording available: {rec['url']}" if rec else " — no recording published yet"
            lines.append(f"- {_item_line(i)}{note}")

    if required_upcoming:
        lines.append("\n**Coming up (required):**")
        lines.extend(f"- {_item_line(i)}" for i in required_upcoming[:5])

    if optional_upcoming:
        lines.append("\n**Coming up (optional):**")
        lines.extend(f"- {_item_line(i)}" for i in optional_upcoming[:5])

    if anytime:
        lines.append("\n**Self-paced (do anytime):**")
        lines.extend(f"- {_item_line(i)}" for i in anytime)

    if len(lines) == 1:
        lines.append("You're all caught up — nothing pending. 🎉")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
