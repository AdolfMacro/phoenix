#!/usr/bin/env python3
"""Backwards-compatible entry point for `python3 tools/updater.py`.

The real logic now lives in :mod:`phoenix.updates`; this shim only keeps the
old path working for anyone who scripted against it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phoenix.updates import (  # noqa: E402
    check_remote_version,
    is_installed,
    local_version,
    run_updater,
)

OK = "[ ok ]"
BAD = "[fail]"


def mainUpdater() -> int:  # noqa: N802 - kept for backwards compatibility
    result = check_remote_version()
    if result["error"]:
        print(f"{BAD} {result['error']}")
        return 1
    if not result["outdated"]:
        print(f"{OK} phoenix {result['local']} is up to date")
        return 0
    print(f"[warn] {result['local']} -> published {result['remote']}")
    if not is_installed():
        print(
            f"{BAD} this copy is not installed in /usr/src/phoenix; "
            "re-run installer.sh instead"
        )
        return 1
    if input("update now [y/n] ? ").strip().lower() != "y":
        print("skipped")
        return 0
    ok, output = run_updater()
    print(output)
    return 0 if ok else 1


if __name__ == "__main__":
    print(f"local version: {local_version()}")
    sys.exit(mainUpdater())
