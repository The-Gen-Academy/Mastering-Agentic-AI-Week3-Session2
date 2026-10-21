"""Offline checks against the notebook's real setup, with scripted model responses.

Run: uv run --locked python -m unittest discover -s tests -v
No model API calls, credentials, or writes to the demo workspace are needed.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
from pydantic import PrivateAttr


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = json.loads((ROOT / "gtm_deep_agent.ipynb").read_text())
SOURCES = {cell["id"]: "".join(cell["source"]) for cell in NOTEBOOK["cells"]}


class ScriptedModel(FakeMessagesListChatModel):
    _seen_messages: list = PrivateAttr(default_factory=list)
    _seen_tools: list = PrivateAttr(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self._seen_tools.append([getattr(tool, "name", None) for tool in tools])
        return self

    def _generate(self, messages, **kwargs):
        self._seen_messages.append(list(messages))
        return super()._generate(messages, **kwargs)


def call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def tool_turn(*calls):
    return AIMessage(content="", tool_calls=list(calls))


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        for directory in ("grounding", "skills"):
            shutil.copytree(ROOT / directory, self.work / directory)
        # A sentinel verifies that forbidden writes/deletes cannot alter source files.
        (self.work / "README.md").write_text("SOURCE FILE")
        (self.work / ".env").write_text("PRIVATE TEST FIXTURE")
        self.enterContext(contextlib.chdir(self.work))
        self.enterContext(patch.dict(os.environ, {
            "TAVILY_API_KEY": "",
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
        }))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def build(self, responses, child=None):
        model = ScriptedModel(responses=responses)
        ns = {
            "os": os,
            "Path": Path,
            "MODEL": model,
            "GROUNDING": (self.work / "grounding/gen_academy.md").read_text(),
        }
        for cell_id in ("eaa7050e", "d89713fd", "4e4e1297"):
            exec(compile(SOURCES[cell_id], f"notebook:{cell_id}", "exec"), ns)
        if child is not None:
            ns["research_subagent"]["model"] = child
        for cell_id in ("838717c0", "58c47ced", "campaign-execution-helpers"):
            exec(compile(SOURCES[cell_id], f"notebook:{cell_id}", "exec"), ns)
        return ns, model

    def invoke(self, ns, thread="test"):
        config = {"configurable": {"thread_id": thread}, "recursion_limit": 60}
        result = ns["agent"].invoke(
            {"messages": [{"role": "user", "content": "Test campaign."}]}, config=config
        )
        return result, config

    def resume(self, ns, result, config, decisions):
        interrupt = result["__interrupt__"][0]
        return ns["agent"].invoke(
            Command(resume={interrupt.id: {"decisions": decisions}}), config=config
        )

    def test_code_cells_compile_and_local_assets_exist(self):
        for cell in NOTEBOOK["cells"]:
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), cell["id"], "exec")
        import re
        for path in re.findall(r"\]\(\./([^)]*)\)", json.dumps(NOTEBOOK)):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_batch_approval_and_rejection_count_only_executed_receipts(self):
        ns, _ = self.build([
            tool_turn(
                call("publish_post", {"channel": "linkedin", "content": "Post"}, "li"),
                call("publish_post", {"channel": "email", "content": "Email"}, "email"),
            ),
            AIMessage(content="LinkedIn approved; email rejected."),
        ])
        result, config = self.invoke(ns)
        self.assertEqual(len(result["__interrupt__"][0].value["action_requests"]), 2)
        self.assertEqual(ns["successful_publications"](result["messages"]), [])
        answers = iter(["a", "r", "Stop; do not publish email."])
        answer = ns["review_interrupt"](
            result["__interrupt__"][0].value, ask=lambda prompt: next(answers)
        )
        result = self.resume(ns, result, config, answer["decisions"])
        self.assertFalse(result.get("__interrupt__"))
        self.assertEqual(ns["successful_publications"](result["messages"]), ["linkedin"])

    def test_edited_channel_is_reported_from_actual_execution(self):
        ns, _ = self.build([
            tool_turn(call("publish_post", {"channel": "linkedin", "content": "Original"}, "edit")),
            AIMessage(content="Published the human's edited content."),
        ])
        result, config = self.invoke(ns)
        answers = iter(["e", '{"channel": "email", "content": "Human-approved email"}'])
        response = ns["review_interrupt"](
            result["__interrupt__"][0].value, ask=lambda prompt: next(answers)
        )
        result = self.resume(ns, result, config, response["decisions"])
        self.assertEqual(ns["successful_publications"](result["messages"]), ["email"])
        receipt = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.artifact)
        self.assertIn("email", receipt.content)

    def test_sequential_interrupts_each_require_input_and_pause_keeps_checkpoint(self):
        ns, _ = self.build([
            tool_turn(call("publish_post", {"channel": "linkedin", "content": "Post"}, "li")),
            tool_turn(call("publish_post", {"channel": "email", "content": "Email"}, "email")),
            AIMessage(content="Both completed."),
        ])
        result, config = self.invoke(ns)
        interrupted_id = result["__interrupt__"][0].id
        self.assertIsNone(ns["review_interrupt"](
            result["__interrupt__"][0].value, ask=lambda prompt: ""
        ))
        self.assertEqual(ns["agent"].get_state(config).interrupts[0].id, interrupted_id)
        result = self.resume(ns, result, config, [{"type": "approve"}])
        self.assertTrue(result.get("__interrupt__"))
        self.assertEqual(ns["successful_publications"](result["messages"]), ["linkedin"])
        response = ns["review_interrupt"](
            result["__interrupt__"][0].value, ask=lambda prompt: "approve"
        )
        result = self.resume(ns, result, config, response["decisions"])
        self.assertEqual(ns["successful_publications"](result["messages"]), ["linkedin", "email"])

    def test_invalid_edit_and_blank_rejection_do_not_resume(self):
        ns, _ = self.build([
            tool_turn(call("publish_post", {"channel": "email", "content": "Email"}, "email")),
            AIMessage(content="Done."),
        ])
        result, config = self.invoke(ns)
        answers = iter(["e", '{"channel": "unsupported", "content": "x"}', "r", "", "p"])
        response = ns["review_interrupt"](
            result["__interrupt__"][0].value, ask=lambda prompt: next(answers)
        )
        self.assertIsNone(response)
        self.assertTrue(ns["agent"].get_state(config).interrupts)
        self.assertEqual(ns["successful_publications"](result["messages"]), [])

    def test_failed_tool_is_not_counted_as_published(self):
        ns, _ = self.build([
            tool_turn(call("publish_post", {"channel": "email", "content": "Email"}, "email")),
            AIMessage(content="Done."),
        ])
        messages = [
            tool_turn(call("publish_post", {"channel": "email", "content": "Email"}, "email")),
            ToolMessage(content="Failed", tool_call_id="email", status="error"),
            ToolMessage(
                content="Unmatched receipt", tool_call_id="unknown",
                artifact={"channel": "email", "simulated": True, "status": "published"},
            ),
        ]
        self.assertEqual(ns["successful_publications"](messages), [])

    def test_permissions_allow_outputs_but_protect_sources_and_secrets(self):
        original = (self.work / "grounding/gen_academy.md").read_text()
        ns, _ = self.build([
            tool_turn(call("write_file", {"file_path": "/grounding/gen_academy.md", "content": "BAD"}, "g")),
            tool_turn(call("write_file", {"file_path": "/skills/linkedin-style/SKILL.md", "content": "BAD"}, "s")),
            tool_turn(call("write_file", {"file_path": "/README.md", "content": "BAD"}, "r")),
            tool_turn(call("read_file", {"file_path": "/.env"}, "env")),
            tool_turn(call("write_file", {"file_path": "/.env", "content": "BAD"}, "env-write")),
            tool_turn(call("delete", {"file_path": "/grounding"}, "delete")),
            tool_turn(call("write_file", {"file_path": "/drafts/check.md", "content": "first"}, "w1")),
            tool_turn(call("write_file", {"file_path": "/drafts/check.md", "content": "revised"}, "w2")),
            AIMessage(content="Done."),
        ])
        result, _ = self.invoke(ns)
        self.assertEqual((self.work / "grounding/gen_academy.md").read_text(), original)
        self.assertEqual((self.work / "README.md").read_text(), "SOURCE FILE")
        self.assertNotEqual((self.work / "skills/linkedin-style/SKILL.md").read_text(), "BAD")
        self.assertEqual((self.work / "drafts/check.md").read_text(), "revised")
        returned = {m.tool_call_id: str(m.content) for m in result["messages"] if isinstance(m, ToolMessage)}
        for call_id in ("g", "s", "r", "env", "env-write", "delete"):
            self.assertIn("denied", returned[call_id].lower(), returned[call_id])
        self.assertNotIn("PRIVATE TEST FIXTURE", returned["env"])
        self.assertEqual((self.work / ".env").read_text(), "PRIVATE TEST FIXTURE")

    def test_subagent_inherits_permissions_but_not_parent_todos(self):
        child = ScriptedModel(responses=[
            tool_turn(call("read_file", {"file_path": "/grounding/gen_academy.md"}, "ground")),
            tool_turn(call("write_file", {"file_path": "/grounding/gen_academy.md", "content": "BAD"}, "bad")),
            AIMessage(content="Read approved facts; could not overwrite them."),
        ])
        ns, main = self.build([
            tool_turn(call("write_todos", {"todos": [{"content": "PRIVATE_PARENT_PLAN", "status": "in_progress"}]}, "plan")),
            tool_turn(call("task", {
                "subagent_type": "researcher",
                "description": "Campaign: engineers; enrollment; six-week angle. Read /grounding/gen_academy.md."
            }, "research")),
            AIMessage(content="Done."),
        ], child=child)
        result, _ = self.invoke(ns)
        self.assertIn("write_todos", main._seen_tools[0])
        self.assertNotIn("write_todos", child._seen_tools[0])
        self.assertEqual(result["todos"][0]["content"], "PRIVATE_PARENT_PLAN")
        first_child_context = str(child._seen_messages[0])
        self.assertNotIn("PRIVATE_PARENT_PLAN", first_child_context)
        self.assertIn("/grounding/gen_academy.md", first_child_context)
        self.assertIn("denied", str(child._seen_messages[-1]).lower())
        self.assertNotEqual((self.work / "grounding/gen_academy.md").read_text(), "BAD")

    def test_store_memory_loads_in_new_thread_and_new_store_starts_empty(self):
        note = "Distinctive test brand voice: practical and precise."
        ns, model = self.build([
            tool_turn(call("write_file", {"file_path": "/memories/brand_voice.md", "content": note}, "memory")),
            AIMessage(content="Saved."),
            AIMessage(content="Recalled."),
        ])
        self.invoke(ns, "writer")
        self.invoke(ns, "reader")
        self.assertIn(note, str(model._seen_messages[-1]))
        self.assertFalse((self.work / "memories/brand_voice.md").exists())
        new_ns, new_model = self.build([AIMessage(content="No saved note.")])
        self.invoke(new_ns, "fresh-store")
        self.assertNotIn(note, str(new_model._seen_messages[0]))

    def test_long_run_recovers_same_thread_without_repeating_completed_work(self):
        ns, model = self.build([
            tool_turn(call("write_file", {"file_path": "/drafts/check.md", "content": "Saved work"}, "saved")),
            *[
                tool_turn(call("read_file", {"file_path": "/grounding/gen_academy.md"}, f"read-{i}"))
                for i in range(16)
            ],
            tool_turn(call("publish_post", {"channel": "linkedin", "content": "Draft"}, "publish")),
            AIMessage(content="Completed."),
        ])
        config = {"configurable": {"thread_id": "long-run"}, "recursion_limit": 60}
        partial = ns["invoke_with_diagnostics"](
            ns["agent"], {"messages": [{"role": "user", "content": "Campaign"}]}, config
        )
        self.assertTrue(partial["__step_limit_reached__"])
        self.assertTrue(partial["__next_nodes__"])
        self.assertEqual((self.work / "drafts/check.md").read_text(), "Saved work")
        config = {**config, "recursion_limit": 200}
        pending = ns["invoke_with_diagnostics"](ns["agent"], None, config)
        self.assertFalse(pending.get("__step_limit_reached__"))
        self.assertTrue(pending.get("__interrupt__"))
        self.assertEqual(ns["successful_publications"](pending["messages"]), [])
        self.assertEqual(sum(m.type == "human" for m in pending["messages"]), 1)
        self.assertEqual(sum(
            isinstance(m, ToolMessage) and m.tool_call_id == "saved"
            for m in pending["messages"]
        ), 1)
        intr = pending["__interrupt__"][0]
        completed = ns["invoke_with_diagnostics"](
            ns["agent"], Command(resume={intr.id: {"decisions": [{"type": "approve"}]}}), config
        )
        self.assertEqual(ns["successful_publications"](completed["messages"]), ["linkedin"])

    def test_step_limit_does_not_trigger_automatic_retry_or_claim_completion(self):
        ns, _ = self.build([
            tool_turn(call("read_file", {"file_path": "/grounding/gen_academy.md"}, f"read-{i}"))
            for i in range(30)
        ])
        config = {"configurable": {"thread_id": "capped"}, "recursion_limit": 10}
        partial = ns["invoke_with_diagnostics"](
            ns["agent"], {"messages": [{"role": "user", "content": "Campaign"}]}, config
        )
        self.assertTrue(partial["__step_limit_reached__"])
        self.assertEqual(ns["agent"].get_state(config).metadata["step"], 10)
        ns.update(result=partial, config=config)
        exec(compile(SOURCES["review-publish-gate"], "notebook:review-publish-gate", "exec"), ns)
        self.assertEqual(ns["agent"].get_state(config).metadata["step"], 10)
        self.assertIn("Campaign execution is incomplete", self.output.getvalue())
        self.assertNotIn("===== FINAL RESPONSE =====", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
