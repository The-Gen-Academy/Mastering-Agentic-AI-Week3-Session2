"""Exercise MCP v2 and legacy stdio clients against an isolated backend."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import anyio
import httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import mcp_server as server

ROOT = Path(__file__).resolve().parents[1]


class MCPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.data_path = Path(cls.temp.name) / "curriculum.json"
        cls.course = json.loads((ROOT / "data/curriculum.seed.json").read_text())
        cls.past, cls.future = cls.course["weeks"][0]["items"][:2]
        cls.past.update(title="Migration Test Past Session", date="2000-01-01")
        cls.future.update(title="Migration Test Future Session", date="2099-01-01")
        cls.data_path.write_text(json.dumps(cls.course))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.api = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TEST_DATA_PATH=str(cls.data_path), TEST_PORT=str(port))
        cls.backend = subprocess.Popen(
            [
                sys.executable, "-c",
                "import os; from pathlib import Path; import storage, uvicorn; "
                "storage.DATA_PATH = Path(os.environ['TEST_DATA_PATH']); "
                "uvicorn.run('main:app', host='127.0.0.1', "
                "port=int(os.environ['TEST_PORT']), log_level='error')",
            ],
            cwd=ROOT / "backend", env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        cls.addClassCleanup(cls.stop_backend)
        for _ in range(100):
            if cls.backend.poll() is not None:
                raise RuntimeError(cls.backend.stderr.read().decode())
            try:
                if httpx.get(f"{cls.api}/items", timeout=0.2).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.05)
        else:
            raise RuntimeError("Test backend did not start")

    @classmethod
    def stop_backend(cls):
        cls.backend.terminate()
        try:
            cls.backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.backend.kill()
            cls.backend.wait()
        cls.backend.stderr.close()

    def test_stdio_modern_and_legacy(self):
        async def exercise():
            for mode, version in [
                ("auto", "2026-07-28"), ("legacy", "2025-11-25")
            ]:
                with self.subTest(mode=mode):
                    self.data_path.write_text(json.dumps(self.course))
                    params = StdioServerParameters(
                        command=sys.executable,
                        args=[str(ROOT / "mcp_server/mcp_server.py")],
                        env={"COURSE_API_URL": self.api},
                        cwd=self.temp.name,
                    )
                    async with Client(params, mode=mode, read_timeout_seconds=10) as client:
                        self.assertEqual(client.protocol_version, version)
                        listing = await client.list_tools()
                        tools = {tool.name: tool for tool in listing.tools}
                        self.assertEqual(set(tools), {
                            "get_schedule", "get_session_details",
                            "publish_recording", "whats_next",
                        })
                        self.assertTrue(tools["get_schedule"].annotations.read_only_hint)
                        self.assertTrue(tools["publish_recording"].annotations.destructive_hint)
                        for name, args in [
                            ("get_schedule", {"week": 1}),
                            ("get_session_details", {"session": self.past["title"]}),
                            ("whats_next", {}),
                        ]:
                            result = await client.call_tool(name, args)
                            self.assertFalse(result.is_error, result)
                            self.assertTrue(result.content)
                            self.assertIsNotNone(result.structured_content)

                        url = "https://example.com/mcp-migration-test"
                        args = {"session": self.past["title"], "recording_url": url}
                        for _ in range(2):
                            result = await client.call_tool("publish_recording", args)
                            self.assertFalse(result.is_error, result)
                            self.assertIn("Published.", result.content[0].text)
                        item = httpx.get(f"{self.api}/items/{self.past['id']}").json()
                        recordings = [r for r in item["resources"] if r["label"].lower() == "recording"]
                        self.assertEqual(len(recordings), 1)
                        self.assertEqual(recordings[0]["url"], url)

                        before = self.data_path.read_bytes()
                        result = await client.call_tool("publish_recording", {
                            "session": self.future["title"], "recording_url": url,
                        })
                        self.assertIn("hasn't happened yet", result.content[0].text)
                        self.assertEqual(self.data_path.read_bytes(), before)
                        invalid = await client.call_tool("get_schedule", {"week": "invalid"})
                        self.assertTrue(invalid.is_error)
        anyio.run(exercise)

    def test_empty_curriculum(self):
        with patch.object(server, "_fetch_items", return_value=[]):
            self.assertIn("empty", server._resolve(None, "anything"))

    def test_http_failure_has_actionable_error(self):
        response = httpx.Response(503, request=httpx.Request("GET", self.api))
        with self.assertRaisesRegex(ToolError, "HTTP 503"):
            server._check_response(response)

    def test_network_failure_is_visible_to_mcp_client(self):
        async def exercise():
            with patch.object(
                server.httpx.Client, "get", side_effect=httpx.ConnectError("offline")
            ):
                async with Client(server.mcp) as client:
                    result = await client.call_tool("get_schedule", {})
                    self.assertTrue(result.is_error)
                    self.assertIn("Start the FastAPI backend", result.content[0].text)
        anyio.run(exercise)


if __name__ == "__main__":
    unittest.main()
