#!/usr/bin/env python3
"""Phoenix - PNG steganography with a fullscreen terminal GUI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phoenix import VERSION  # noqa: E402


def _version() -> str:
    target = Path(__file__).resolve().parent / "VERSION.txt"
    try:
        return target.read_text(encoding="utf-8").strip() or VERSION
    except OSError:
        return VERSION


def main() -> int:
    version = _version()
    argv = sys.argv[1:]

    if "-h" in argv or "--help" in argv:
        print(
            "phoenix - hide data inside PNG images\n\n"
            "usage: phoenix [option]\n\n"
            "  -h, --help      show this message\n"
            "  -v, --version   print the version\n"
            "      --check     compare against the published version, then exit\n\n"
            "Without options the fullscreen GUI opens.\n"
            "In the GUI: F11 toggles fullscreen, ESC leaves it, 1-5 pick a page,\n"
            "CTRL+Q quits."
        )
        return 0

    if "-v" in argv or "--version" in argv:
        print(f"phoenix {version}")
        return 0

    if "--check" in argv:
        from phoenix.updates import check_remote_version

        result = check_remote_version()
        if result["error"]:
            print(f"phoenix {version}\n{result['error']}")
            return 1
        if result["outdated"]:
            state = f"update available: {result['remote']}"
        elif result["ahead"]:
            state = (
                f"ahead of the published build ({result['remote']} on GitHub)"
            )
        else:
            state = "up to date"
        print(f"phoenix {version} -> published {result['remote']} ({state})")
        return 0

    try:
        from phoenix.gui import launch
    except ImportError as exc:
        print(
            "Phoenix needs PyQt6 for its interface.\n"
            f"  import failed: {exc}\n\n"
            "Install it with:\n"
            "  pip install PyQt6\n"
            "or run the full installer:\n"
            "  bash installer.sh",
            file=sys.stderr,
        )
        return 1

    return launch(version)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
