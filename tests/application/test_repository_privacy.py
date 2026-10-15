import subprocess
from pathlib import Path

import pytest

from tests.application import support as s


def _spellings(path: Path) -> set[str]:
    # Native, forward-slash and JSON-escaped forms, as they appear in captured command output.
    native = str(path)
    return {native, path.as_posix(), native.replace("\\", "\\\\")}


def test_committed_files_hold_no_local_absolute_paths():
    """The repository is public: evidence and logs must say <repo>/<home>, not this machine's paths."""
    try:
        listed = subprocess.run(
            ["git", "-C", str(s.ROOT), "ls-files", "-z"], capture_output=True, check=True
        ).stdout.decode()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    # Short roots such as /app (containers) are too generic to be identifying.
    needles = {
        p.lower() for base in (s.ROOT, Path.home()) if len(base.resolve().parts) >= 3 for p in _spellings(base.resolve())
    }
    leaks = []
    for name in filter(None, listed.split("\0")):
        path = s.ROOT / name
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", "ignore").lower()
        leaks += [f"{name}: {n}" for n in needles if n in text]
    assert not leaks, "absolute local paths committed:\n" + "\n".join(leaks[:20])
