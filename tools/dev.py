"""Single local startup command; preserves existing services and credentials."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import socket
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    os.chdir(ROOT)
    from implementation.manage import configure

    configure()
    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python.exists():
        subprocess.run(["uv", "sync", "--frozen"], check=True)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not (ROOT / "node_modules/next").exists():
        subprocess.run([npm, "ci"], check=True)
    from services.api.config import load_env

    load_env()
    port = urlparse(os.environ.get("APP_ORIGIN", "http://127.0.0.1:3007")).port or 3007
    for candidate_port in (8000, port):
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", candidate_port))
        except OSError:
            print(
                f"Port {candidate_port} is already in use. Stop the previous app instance or choose an unused port; no existing process was stopped."
            )
            return 1
    subprocess.run(["docker", "compose", "-f", "compose.dev.yaml", "up", "-d", "--wait"], check=True)
    subprocess.run([str(python), "-m", "implementation.manage", "migrate"], check=True)
    children = []
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    exit_code = 0
    try:
        children.append(
            subprocess.Popen(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "services.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                creationflags=flags,
            )
        )
        children.append(subprocess.Popen([str(python), "-m", "services.worker.main"], creationflags=flags))
        children.append(
            subprocess.Popen(
                [npm, "run", "dev", "--workspace", "apps/web", "--", "--port", str(port)],
                env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
                creationflags=flags,
            )
        )
        print(
            f"Open http://127.0.0.1:{port} . Ctrl+C stops the owned app processes; PostgreSQL data persists.",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        exit_code = next(child.returncode for child in children if child.poll() is not None) or 1
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
