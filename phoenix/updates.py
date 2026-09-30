"""Version discovery and self-update helpers.

Uses :mod:`urllib` from the standard library instead of ``requests`` so the
tool keeps working with nothing but PyQt6 installed, and compares versions
after ``strip()`` so a trailing newline on the remote file can no longer
produce a false "outdated" verdict.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

__all__ = [
    "ROOT",
    "REMOTE_VERSION_URL",
    "INSTALL_PREFIX",
    "version_key",
    "compare_versions",
    "local_version",
    "remote_version",
    "check_remote_version",
    "is_installed",
    "run_updater",
]

REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/AdolfMacro/phoenix/main/VERSION.txt"
)
INSTALL_PREFIX = Path("/usr/src/phoenix")
ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 8


def local_version(path: Optional[Path] = None) -> str:
    """Read the VERSION.txt that ships next to the code."""
    target = path or (ROOT / "VERSION.txt")
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError:
        from . import VERSION

        return VERSION


def remote_version(url: str = REMOTE_VERSION_URL) -> str:
    """Fetch the published VERSION.txt. Raises on any transport failure."""
    from urllib.error import URLError
    from urllib.request import urlopen

    try:
        with urlopen(url, timeout=TIMEOUT) as response:  # noqa: S310 - fixed https URL
            raw = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise ConnectionError(str(getattr(exc, "reason", exc))) from exc
    version = raw.strip()
    if not version:
        raise ConnectionError("the remote VERSION.txt came back empty")
    return version


def is_installed() -> bool:
    """True when the tool lives in the system prefix."""
    return (INSTALL_PREFIX / "VERSION.txt").is_file()


def version_key(version: str) -> tuple[int, ...]:
    """Turn a version string into a comparable tuple.

    Phoenix uses ``MAJOR:MINOR`` (older builds used ``MAJOR.MINOR.PATCH``), so
    the digits are collected rather than split on a fixed separator. Plain
    string comparison would call ``0.0.1:0`` newer than ``0.2:1``.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version or ""))


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0 or 1 for ``left`` versus ``right``."""
    a = list(version_key(left))
    b = list(version_key(right))
    width = max(len(a), len(b))
    a += [0] * (width - len(a))
    b += [0] * (width - len(b))
    return (a > b) - (a < b)


def check_remote_version() -> dict:
    """Compare local and remote VERSION.txt. Never raises."""
    result = {
        "local": local_version(),
        "remote": "",
        "outdated": False,
        "ahead": False,
        "error": "",
    }
    try:
        result["remote"] = remote_version()
    except Exception as exc:
        result["error"] = f"Cannot reach GitHub: {exc}"
        return result
    order = compare_versions(result["local"], result["remote"])
    result["outdated"] = order < 0
    result["ahead"] = order > 0
    return result


def run_updater(script: Optional[Path] = None) -> tuple[bool, str]:
    """Execute the update helper. Returns ``(ok, output)``."""
    target = script or (ROOT / "tools" / "updater.sh")
    if not target.is_file():
        return False, f"updater not found: {target}"
    try:
        completed = subprocess.run(
            ["bash", str(target)],
            cwd=str(target.parent),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode == 0, output or "no output"
