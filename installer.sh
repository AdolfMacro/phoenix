#!/usr/bin/env bash
# Phoenix installer (Linux). Run as a normal user; sudo is requested per step.
#
# Dependency handling (PEP 668 aware): the installer never touches the system
# interpreter. It picks, in order:
#   1. an existing interpreter that already has cryptography + PyQt6
#   2. distro packages, when a package manager is available
#   3. a private virtualenv at $PREFIX/.venv
#
# Override with:
#   PHOENIX_PYTHON=/path/to/python bash installer.sh   (use this interpreter)
#   PHOENIX_DEPS=venv|system|distro bash installer.sh  (force a strategy)
set -euo pipefail

PREFIX="${PHOENIX_PREFIX:-/usr/src/phoenix}"
BINDIR="${PHOENIX_BINDIR:-/usr/local/bin}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$PREFIX/.venv"
STRATEGY="${PHOENIX_DEPS:-auto}"
VERSION="dev"

RED=$'\033[31m'; DIM=$'\033[2m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
[ -t 1 ] || { RED=""; DIM=""; BOLD=""; OFF=""; }

say()  { printf '%s\n' "$*"; }
step() { printf '\n%s==>%s %s%s%s\n' "$DIM" "$OFF" "$BOLD" "$*" "$OFF"; }
warn() { printf '%swarning:%s %s\n' "$RED" "$OFF" "$*" >&2; }
die()  { printf '%serror:%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }

have_deps() {
    "$1" -c 'import cryptography, PyQt6.QtWidgets' >/dev/null 2>&1
}

venv_python() { [ -x "$VENV/bin/python" ] && printf '%s' "$VENV/bin/python"; }

# Absolute path of an interpreter, so the generated launcher does not depend
# on whatever PATH the user happens to have later.
resolve_python() {
    "$1" -c 'import sys; print(sys.executable or sys.argv[0])'
}

detect_distro_pkg() {
    # Echo the distro packages that satisfy the dependencies, if any.
    if command -v apt-get >/dev/null; then
        printf 'apt-get install -y python3-cryptography python3-pyqt6'
    elif command -v dnf >/dev/null; then
        printf 'dnf install -y python3-cryptography python3-pyqt6'
    elif command -v pacman >/dev/null; then
        printf 'pacman -S --needed --noconfirm python-cryptography python-pyqt6'
    elif command -v zypper >/dev/null; then
        printf 'zypper --non-interactive install python3-cryptography python3-pyQt6'
    fi
}

banner() {
    printf '%s\n' "
   ___          _        _ _
  |_ _|_ __  __| |_ __ _| | | __ _ __
   | || ' \\/ _|  _/ _\` | | |/ _\` '  \\
   | || | | \\__ \\ || (_| | | | (_| |
  |___|_| |_|___/\\__\\__,_|_|_|\\___|_|

 Installer for phoenix ${VERSION}
"
}

# --------------------------------------------------------------- preflight ---
step "checking python"
BASE_PYTHON="${PHOENIX_PYTHON:-python3}"
command -v "$BASE_PYTHON" >/dev/null 2>&1 || die "python3 not found on PATH"
"$BASE_PYTHON" - <<'PY' || die "python3 >= 3.9 is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
VERSION="$("$BASE_PYTHON" "$HERE/main.py" --version 2>/dev/null | awk '{print $2}' || echo dev)"

banner
say "${DIM}  strategy hint: deps=${STRATEGY} prefix=${PREFIX}${OFF}"
say "    interpreter : $(resolve_python "$BASE_PYTHON") ($("$BASE_PYTHON" -V 2>&1))"
say "    version     : $VERSION"

# The launcher needs the prefix to exist before a venv can be placed in it.
sudo mkdir -p "$PREFIX"

# ------------------------------------------------------------ dependencies ---
step "resolving dependencies"
LAUNCH_PYTHON=""
case "$STRATEGY" in
    auto|system|venv|distro) ;;
    *) die "unknown PHOENIX_DEPS='$STRATEGY' (expected auto, venv, system or distro)" ;;
esac

# 1. an interpreter that already satisfies us
if [ -z "$LAUNCH_PYTHON" ]; then
    if [ -n "${PHOENIX_PYTHON:-}" ] && have_deps "$BASE_PYTHON"; then
        LAUNCH_PYTHON="$(resolve_python "$BASE_PYTHON")"
        say "    using ${DIM}$LAUNCH_PYTHON${OFF} (already has them)"
    elif [ "$STRATEGY" != "system" ] && have_deps "$(venv_python || true)"; then
        LAUNCH_PYTHON="$VENV/bin/python"
        say "    reusing the existing virtualenv"
    elif [ "$STRATEGY" != "venv" ] && have_deps "$BASE_PYTHON"; then
        LAUNCH_PYTHON="$(resolve_python "$BASE_PYTHON")"
        say "    using ${DIM}$LAUNCH_PYTHON${OFF} (already has them)"
    fi
fi

# 2. distro packages
if [ -z "$LAUNCH_PYTHON" ] && [ "$STRATEGY" != "venv" ]; then
    PKG_CMD="$(detect_distro_pkg || true)"
    if [ -n "$PKG_CMD" ] && [ "$STRATEGY" = "distro" -o "$STRATEGY" = "auto" ]; then
        say "    installing distro packages: $PKG_CMD"
        if sudo $PKG_CMD && have_deps "$BASE_PYTHON"; then
            LAUNCH_PYTHON="$(resolve_python "$BASE_PYTHON")"
            say "    distro packages satisfied the dependencies"
        else
            warn "distro package install failed, falling back to a virtualenv"
        fi
    fi
fi

# 3. private virtualenv
if [ -z "$LAUNCH_PYTHON" ]; then
    say "    creating a private virtualenv at $VENV"
    "$BASE_PYTHON" -m venv --upgrade-deps "$VENV" 2>/dev/null \
        || "$BASE_PYTHON" -m venv "$VENV" \
        || die "could not create a virtualenv.
     On Debian/Ubuntu install it with:  sudo apt install python3-venv
     Then re-run:  bash installer.sh"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip \
        || warn "could not upgrade pip inside the virtualenv, continuing"
    if ! "$VENV/bin/python" -m pip install --quiet --upgrade cryptography PyQt6; then
        die "pip failed inside the virtualenv.
     If you are offline, install the packages another way and re-run with
     PHOENIX_DEPS=system, or point PHOENIX_PYTHON at an interpreter that
     already has cryptography and PyQt6."
    fi
    LAUNCH_PYTHON="$VENV/bin/python"
    say "    virtualenv ready"
fi

say "    launcher python: $LAUNCH_PYTHON"

# ---------------------------------------------------------------- install ---
step "installing into $PREFIX"
sudo mkdir -p "$PREFIX"
# Copy the tree without the VCS metadata, caches, or a virtualenv that may
# already live inside the prefix.
sudo tar -C "$HERE" \
    --exclude=.git --exclude=.venv --exclude=__pycache__ \
    --exclude='*.pyc' --exclude='.venv/lib' \
    -cf - . | sudo tar -C "$PREFIX" -xf -
sudo chmod +x "$PREFIX/tools/updater.sh" "$PREFIX/main.py" 2>/dev/null || true

step "verifying the install"
if ! "$LAUNCH_PYTHON" "$PREFIX/main.py" --version >/dev/null 2>&1; then
    die "the installed copy does not run. Try:  $LAUNCH_PYTHON $PREFIX/main.py --help"
fi
sudo rm -rf "$PREFIX/__pycache__" "$PREFIX/tools/__pycache__" 2>/dev/null || true

step "creating $BINDIR/phoenix"
sudo mkdir -p "$BINDIR"
sudo tee "$BINDIR/phoenix" >/dev/null <<EOF
#!/bin/sh
# Phoenix launcher - generated by installer.sh
exec "$LAUNCH_PYTHON" "$PREFIX/main.py" "\$@"
EOF
sudo chmod +x "$BINDIR/phoenix"

say "    entry point: $("$BINDIR/phoenix" --version 2>/dev/null || echo 'run: phoenix --version')"

banner
cat <<EOF

 Installation complete.

 Launch it with:   phoenix
 In-app help:      phoenix --help
 Version check:    phoenix --check

 Press F11 for fullscreen, ESC to leave it, CTRL+Q to quit.

 Interpreter: $LAUNCH_PYTHON

EOF
