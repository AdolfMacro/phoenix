#!/usr/bin/env bash
# Pull the latest phoenix release and re-run the installer.
#
# The installer is reused on purpose: it already knows how to resolve the
# dependencies (distro packages or a private virtualenv), which the old
# updater never did, and it rewrites the launcher in /usr/local/bin.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
installer="$root/installer.sh"

if [ ! -f "$installer" ]; then
    echo "phoenix: installer.sh not found next to the tool" >&2
    exit 1
fi

echo "phoenix: pulling the latest release"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if command -v git >/dev/null 2>&1; then
    git clone --depth 1 --quiet https://github.com/AdolfMacro/phoenix.git "$tmp/repo"
    # Keep the installed virtualenv, if any: it holds the dependencies.
    cp -R "$root/." "$tmp/repo/" 2>/dev/null || true
    rm -rf "$tmp/repo/.venv"
    exec bash "$tmp/repo/installer.sh"
fi

echo "phoenix: git is not installed, running the installer in place"
exec bash "$installer"
