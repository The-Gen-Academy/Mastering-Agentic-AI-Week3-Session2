"""Generate this machine's course-platform registration, preserving other servers."""

import json
import os
from pathlib import Path


def configure(root: Path, uv_bin: str) -> None:
    path = root / ".mcp.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    servers = config.setdefault("mcpServers", {})
    server = servers.setdefault("course-platform", {})
    server.update(command="/bin/bash", args=[str(root / "dev"), "mcp"])
    env = server.setdefault("env", {})
    for key in ("UV_PROJECT", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(key, None)
    env["UV_BIN"] = uv_bin
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n")
    temporary.replace(path)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    configure(root, os.environ["UV_BIN"])
    print(f"Updated {root / '.mcp.json'}")
