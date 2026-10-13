from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip())


load_env()
DATA = Path(os.environ.get("LV_DATA_DIR", str(ROOT / "data")))
ORIGIN = os.environ.get("APP_ORIGIN", "http://127.0.0.1:3000")
