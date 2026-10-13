"""Plan command dispatcher with exact command/output/exit and source-hash evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def source_hash() -> str:
    digest = hashlib.sha256()
    for folder in ("packages", "services", "implementation", "apps/web", "migrations", "ops"):
        for path in sorted((ROOT / folder).rglob("*")):
            if (
                path.is_file()
                and not any(x in path.parts for x in (".next", "node_modules", "__pycache__"))
                and path.suffix in (".py", ".ts", ".tsx", ".css", ".json")
            ):
                digest.update(str(path.relative_to(ROOT)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def record_command(command: list[str], name: str, timeout: int = 1800) -> dict:
    at = datetime.now(timezone.utc).isoformat()
    folder = ROOT / "evidence/build/logs"
    folder.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "LV_ACCEPTANCE_COMMAND": json.dumps([sys.executable, "-m", "implementation.acceptance_adapter"]),
        },
    )
    output = result.stdout + "\n" + result.stderr
    run_id = at.replace(":", "").replace("+", "_").replace(".", "_")
    path = folder / (name + "-" + run_id + ".txt")
    path.write_text(output, encoding="utf-8")
    evidence = {
        "run_at": at,
        "command": command,
        "exit_code": result.returncode,
        "status": "passed" if result.returncode == 0 else "failed",
        "artifact_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "software_sha256": source_hash(),
    }
    (folder / (name + ".json")).write_text(json.dumps(evidence, indent=2))
    acceptance = ROOT / "evidence/acceptance-latest.json"
    if acceptance.exists():
        (folder / (name + "-" + run_id + "-acceptance.json")).write_bytes(acceptance.read_bytes())
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(output, flush=True)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    args = parser.parse_args()
    mappings = json.loads((ROOT / "tests/acceptance/checks.json").read_text())["mapping"]
    if args.name not in mappings:
        print("FAIL unknown or missing check")
        return 1
    reports = []
    for suite in mappings[args.name]:
        reports.append(
            record_command(
                [sys.executable, str(ROOT / "tests/acceptance/run.py"), "--suite", suite],
                args.name + "-" + suite,
            )
        )
    (ROOT / "evidence/build" / ("check-" + args.name + ".json")).write_text(json.dumps(reports, indent=2))
    return int(any(r["exit_code"] for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
