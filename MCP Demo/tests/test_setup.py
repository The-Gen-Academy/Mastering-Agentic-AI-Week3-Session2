"""Regression checks for stale activation and moved project folders."""

import json
from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.configure_mcp import configure

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def test_moved_project_rebuilds_environment_despite_stale_shell_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary).resolve() / "Original Demo"
            original.mkdir()
            for name in ("dev", ".python-version", "pyproject.toml", "uv.lock"):
                shutil.copy2(ROOT / name, original / name)
            code = "import sys, importlib.metadata as m; print(sys.prefix); print(m.version('mcp'))"
            env = dict(os.environ, UV_OFFLINE="1")
            env.pop("UV_PYTHON", None)
            first = subprocess.run(
                ["/bin/bash", str(original / "dev"), "python", "-c", code],
                cwd="/", env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            relocated = Path(temporary).resolve() / "Moved Demo"
            original.rename(relocated)
            foreign = Path(temporary) / "unrelated-environment"
            foreign.mkdir()
            sentinel = foreign / "do-not-change"
            sentinel.write_text("preserve")
            env.update(
                VIRTUAL_ENV=str(original / ".venv"),
                UV_PROJECT=str(original),
                UV_PROJECT_ENVIRONMENT=str(foreign),
                PYTHONHOME=str(original),
                PYTHONPATH=str(original),
            )
            second = subprocess.run(
                ["/bin/bash", str(relocated / "dev"), "python", "-c", code],
                cwd="/", env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.splitlines(), [str(relocated / ".venv"), version("mcp")])
            self.assertNotIn("does not match", second.stderr)
            self.assertEqual(sentinel.read_text(), "preserve")
            self.assertEqual(
                (relocated / ".venv/.project-root").read_text().strip(), str(relocated)
            )
            activation = (relocated / ".venv/bin/activate").read_text()
            self.assertNotIn(str(original), activation)
            activated = subprocess.run(
                ["/bin/bash", "-c", 'source "$1"; printf "%s" "$VIRTUAL_ENV_PROMPT"',
                 "check-prompt", str(relocated / ".venv/bin/activate")],
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(activated.returncode, 0, activated.stderr)
            self.assertEqual(activated.stdout, "mcp-course-demo")
            launcher = subprocess.run(
                [str(relocated / ".venv/bin/uvicorn"), "--version"],
                text=True, capture_output=True, timeout=10,
                env={k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH")},
            )
            self.assertEqual(launcher.returncode, 0, launcher.stderr)

    def test_registration_preserves_other_servers_and_custom_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "mcpServers": {
                    "other": {"command": "keep-me"},
                    "course-platform": {
                        "command": "uv",
                        "env": {"UV_PROJECT": "/old/path", "COURSE_API_URL": "http://localhost:9000"},
                    },
                }
            }
            (root / ".mcp.json").write_text(json.dumps(config))
            configure(root, "/example/bin/uv")
            once = (root / ".mcp.json").read_text()
            configure(root, "/example/bin/uv")
            self.assertEqual(once, (root / ".mcp.json").read_text())
            servers = json.loads(once)["mcpServers"]
            self.assertEqual(servers["other"], config["mcpServers"]["other"])
            self.assertEqual(servers["course-platform"]["args"], [str(root / "dev"), "mcp"])
            self.assertEqual(servers["course-platform"]["env"], {
                "UV_BIN": "/example/bin/uv", "COURSE_API_URL": "http://localhost:9000",
            })
