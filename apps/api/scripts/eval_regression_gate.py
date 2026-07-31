"""Offline M7 regression gate using deterministic golden fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from src.eval.service import evaluate_payloads  # noqa: E402

DEFAULT_FIXTURES = APP_ROOT / "tests" / "fixtures" / "golden_examples.json"


def load_goldens(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Golden fixture must contain a JSON array")
    return [dict(item) for item in payload]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args()

    result = evaluate_payloads(load_goldens(args.fixtures))
    print(json.dumps(result.model_dump(), ensure_ascii=False, sort_keys=True))
    return 0 if result.status in ("passed", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
