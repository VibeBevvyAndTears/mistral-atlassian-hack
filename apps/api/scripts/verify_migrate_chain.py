#!/usr/bin/env python3
"""Verify Alembic migration chain + pgvector infra expectation (P2).

Always validates:
- single Alembic head
- linear chain from root to head
- enable_pgvector revision present
- docker-compose.infra.yml uses a pgvector image

Optionally (when DATABASE_URL points at reachable Postgres):
- runs ``alembic upgrade head`` and reports success

Exit 0 on chain/compose OK even if live migrate is skipped (DB down).
Exit 1 on broken chain / missing pgvector revision / wrong compose image.
Exit 2 if --require-live and live migrate fails.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
VERSIONS = APP_ROOT / "alembic" / "versions"
COMPOSE = APP_ROOT / "docker-compose.infra.yml"


def _load_revisions() -> dict[str, str | None]:
    """Map revision -> down_revision."""
    mapping: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev_m = re.search(r'^revision:\s*str\s*=\s*["\']([^"\']+)["\']', text, re.M)
        down_m = re.search(
            r'^down_revision:\s*str\s*\|\s*None\s*=\s*(None|["\']([^"\']+)["\'])',
            text,
            re.M,
        )
        if not rev_m or not down_m:
            continue
        rev = rev_m.group(1)
        down = None if down_m.group(1) == "None" else down_m.group(2)
        mapping[rev] = down
    return mapping


def verify_chain() -> list[str]:
    mapping = _load_revisions()
    if not mapping:
        raise SystemExit("No alembic revisions found")
    children: dict[str | None, list[str]] = {}
    for rev, down in mapping.items():
        children.setdefault(down, []).append(rev)
    roots = children.get(None, [])
    if len(roots) != 1:
        raise SystemExit(f"Expected exactly one root revision, found {roots}")
    heads = [r for r in mapping if r not in {d for d in mapping.values() if d}]
    # heads = revisions that are nobody's down_revision
    pointed = {d for d in mapping.values() if d is not None}
    heads = [r for r in mapping if r not in pointed]
    if len(heads) != 1:
        raise SystemExit(f"Expected single Alembic head, found {heads}")
    # Walk chain length
    order: list[str] = []
    cur: str | None = roots[0]
    seen: set[str] = set()
    while cur is not None:
        if cur in seen:
            raise SystemExit(f"Cycle detected at {cur}")
        seen.add(cur)
        order.append(cur)
        nxt = children.get(cur, [])
        if len(nxt) > 1:
            raise SystemExit(f"Branch at {cur}: {nxt}")
        cur = nxt[0] if nxt else None
    if set(order) != set(mapping):
        raise SystemExit("Orphan revisions outside linear chain")
    if "20260730_000002" not in mapping:
        raise SystemExit("Missing enable_pgvector revision 20260730_000002")
    return order


def verify_compose() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    if "pgvector" not in text:
        raise SystemExit(
            "docker-compose.infra.yml must use a pgvector image (e.g. pgvector/pgvector:pg16)"  # noqa: E501
        )


def try_live_migrate() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, (proc.stdout or proc.stderr or "ok").strip()[-500:]
    return False, (proc.stderr or proc.stdout or "migrate failed").strip()[-500:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Fail if live alembic upgrade head cannot run",
    )
    args = parser.parse_args()

    order = verify_chain()
    verify_compose()
    print(
        {
            "status": "chain_ok",
            "head": order[-1],
            "revisions": len(order),
            "pgvector_revision": "20260730_000002",
            "compose_pgvector": True,
        }
    )
    live_ok, detail = try_live_migrate()
    print({"live_migrate": live_ok, "detail": detail})
    if args.require_live and not live_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
