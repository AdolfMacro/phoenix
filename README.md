<p align="center">
  <img width="150" height="150" alt="Phoenix logo"
       src="https://github.com/AdolfMacro/AdolfMacro/blob/main/logo.png">
</p>

<p align="center">
  <b>English</b> · <a href="./README.fa.md">فارسی</a> · <a href="./README.hy.md">Հայերեն</a>
</p>

# phoenix

**Hide data inside PNG images.** A steganography tool with a fullscreen
terminal-style GUI.

Phoenix appends your payload after the `IEND` chunk of a PNG file. The image
data itself is never touched, so the carrier picture still opens normally in
any viewer, and the payload can optionally be encrypted with a Fernet key.

```
phoenix          # open the GUI, fullscreen
phoenix --help
phoenix --version
phoenix --check  # compare against the published build
```

![Phoenix GUI](https://github.com/AdolfMacro/phoenix/blob/main/screenshots/1.png?raw=true)

---

## How it works

A PNG file is a sequence of chunks:

```
89 50 4E 47 0D 0A 1A 0A   signature
IHDR ...                    image header
IDAT ...                    compressed pixels
IEND AE 42 60 82            end marker
<your payload>              appended here
```

`phoenix/core.py` walks the real chunk stream — reading each chunk's 4-byte
length field and stepping through it — until it reaches `IEND`, then returns
everything after it as the payload.

Walking the structure instead of searching for the `IEND` byte pattern matters
in two ways:

- A payload that itself contains the `IEND` pattern is stored and read back
  **intact**, instead of being silently truncated at the first match.
- A truncated, corrupted, or non-PNG file is rejected with a clear error
  rather than producing a raw `IndexError` traceback.

Binding onto an already-bound image appends a second payload; reading returns
the most recent one. Re-binding onto the carrier you are reading is refused.

---

## Requirements

| | |
| --- | --- |
| Python | 3.9 or newer |
| Runtime deps | [`cryptography`](https://cryptography.io/), [`PyQt6`](https://pypi.org/project/PyQt6/) |
| Display | any X11 or Wayland session (the GUI is Qt based) |
| OS | Linux (the installer and updater are `bash` + `sudo`) |

---

## Install

```bash
git clone https://github.com/AdolfMacro/phoenix.git
cd phoenix
bash installer.sh
```

Run it as a **normal user** — the script asks for `sudo` itself. It installs
the code into `/usr/src/phoenix` and writes a launcher to
`/usr/local/bin/phoenix`.

### Dependency handling (PEP 668)

Modern Debian, Ubuntu, Fedora and Arch mark the system interpreter as
*externally managed*, so `pip install` into it — with or without `--user` — is
refused with `externally-managed-environment`. Phoenix never tries. The
installer picks the first option that works:

1. **An interpreter that already has both packages.** Nothing is installed.
2. **Distro packages**, if a package manager is available
   (`apt-get`, `dnf`, `pacman`, `zypper`): `python3-cryptography` and
   `python3-pyqt6`.
3. **A private virtualenv** at `/usr/src/phoenix/.venv`.

Override the choice when you need to:

```bash
PHOENIX_DEPS=venv    bash installer.sh   # always a virtualenv
PHOENIX_DEPS=distro  bash installer.sh   # only distro packages
PHOENIX_DEPS=system  bash installer.sh   # only an interpreter that already works
PHOENIX_PYTHON=/path/to/python3 bash installer.sh
PHOENIX_PREFIX=~/.local/share/phoenix PHOENIX_BINDIR=~/.local/bin bash installer.sh
```

Running the installer twice is safe: an existing virtualenv is reused rather
than rebuilt, and the launcher always records an absolute interpreter path.

### Uninstall

```bash
sudo rm -rf /usr/src/phoenix /usr/local/bin/phoenix
sudo rm -rf /usr/src/phoenix/.venv      # only if a virtualenv was used
```

---

## Using the GUI

The window opens **fullscreen**. Four pages are reachable from the left menu.

| Key | Action |
| --- | --- |
| `1` … `5` | switch page (1–4 navigate, 5 exits) |
| `F11` | toggle fullscreen |
| `ESC` | leave fullscreen |
| `CTRL+Q` | quit |

`CTRL+C` also quits, cleanly and without a traceback.

### 1 · Bind

Pick a carrier PNG, type or load the payload, and write the output. Ticking
**Encrypt payload with a new Fernet key** mints a key that is shown once —
**store it, it is the only way to read the data back.** The output filename is
pre-filled as `<name>_phoenix.png`.

### 2 · Read

Pick a Phoenix image. The info line reports the image size, the payload size
and whether the payload looks encrypted. Tick **The hidden data is encrypted**
and paste the key if one was used; the recovered text can be copied or saved.

### 3 · Developer

Author, links and a short description of the engine.

### 4 · Update

Compares the local `VERSION.txt` against the one published on GitHub and
reports whether you are up to date, behind, or ahead. Applying an update
re-runs the installer, which needs `sudo`.

The console at the bottom logs every operation with a timestamp.

---

## Using the engine directly

`phoenix.core` has no GUI dependency and no third-party imports beyond
`cryptography`:

```python
from phoenix import core

key = core.generate_key()                       # 44 URL-safe characters
token = core.encrypt_payload("secret", key)     # returns a Fernet token

core.bind("cover.png", "cover_phoenix.png", token)   # -> bytes written
core.read("cover_phoenix.png")                       # -> the raw token
core.read("cover_phoenix.png", key)                  # -> "secret"
```

`read(source, key=None)` distinguishes *no key* from *an empty key*: `None`
means "this payload is plaintext", while any string — including `""` — means
"decrypt with this key", so a missing key is reported instead of handing the
raw ciphertext back as if it were the message.

Every failure raises `PhoenixError` with a message written for a human:

```python
>>> core.read("notes.txt")
PhoenixError: This file is not a PNG image. Only PNG files are supported.

>>> core.read("bound.png", "wrong-key")
PhoenixError: Wrong decryption key, or the payload was altered.
```

### API

| Function | Purpose |
| --- | --- |
| `bind(source, destination, payload) -> int` | write the payload into a copy of the PNG; returns the byte count |
| `read(source, key=None) -> str` | return the payload, decrypting when a key is given |
| `inspect(source) -> dict` | image size, payload size, and whether it looks encrypted |
| `is_png(path) -> bool` | structural check, never raises |
| `validate_png(path) -> Path` | structural check, raises `PhoenixError` |
| `generate_key() -> str` | new Fernet key |
| `encrypt_payload(plaintext, key) -> str` | encrypt to a Fernet token |
| `decrypt_payload(token, key) -> str` | decrypt a Fernet token |
| `find_payload(blob) -> bytes` | extract the payload from raw file bytes |

Safety limits: `MAX_IMAGE_BYTES` is 256 MiB and `MAX_PAYLOAD_BYTES` is 64 MiB;
larger inputs are refused instead of being loaded into memory blindly.

---

## Security notes

Read this before you rely on the tool.

- **The payload is not hidden from someone who looks.** It lives after the
  last chunk, so `strings`, a hex editor, or any script that reads past the
  `IEND` will find it. Steganography conceals data from casual inspection, not
  from an analyst.
- **Encryption is the part that matters.** With **Encrypt payload** ticked the
  payload is Fernet: AES-128-CBC with an HMAC-SHA256 authenticator, keys are
  32 bytes, and a wrong key or a modified payload is rejected rather than
  returned as garbage.
- **Losing the key means losing the data.** There is no recovery path and no
  key escrow. A fresh key is generated on every bind and shown once.
- **A key is never stored** in the image or in `VERSION.txt`; the UI copies it
  to your clipboard and never writes it to disk on your behalf.
- **Keys travel in plaintext** if you paste or store them carelessly. Treat
  them like passwords.
- Images are opened by Qt for the file dialogs and the screenshot; Phoenix
  does not upload anything anywhere.

---

## Project layout

```
phoenix/
├── main.py              entry point: argument parsing, then the GUI
├── phoenix/
│   ├── core.py          steganography engine, no GUI imports
│   ├── gui.py           window, pages, workers
│   ├── widgets.py       glow title, neon buttons, matrix rain, scanlines
│   └── updates.py       version discovery and self-update helper
├── tools/
│   ├── updater.py       legacy entry point, delegates to phoenix.updates
│   └── updater.sh       pulls a release and re-runs the installer
├── installer.sh         PEP 668 aware installer
├── VERSION.txt          single source of truth for the version
└── screenshots/1.png
```

---

## Versioning

`VERSION.txt` holds the version and is the single source of truth for the
package, the window title and `phoenix --version`.

Versions compare by their digits (`0.2:1` → `[0, 2, 1]`), not as strings, so
`0.10` correctly sorts above `0.9` and `0.2:1` above `0.0.1:0`. The published
copy is fetched from
`https://raw.githubusercontent.com/AdolfMacro/phoenix/main/VERSION.txt`.

Bump `VERSION.txt`, `phoenix.VERSION` and the constant in `main.py` together.

---

## Running from a clone

```bash
python3 main.py           # GUI
python3 main.py --version
python3 main.py --check
```

Requires `cryptography` and `PyQt6` in the interpreter you run it with. If
PyQt6 is missing, `main.py` prints the exact install command instead of
raising `ImportError`.

---

## Performance notes

The GUI animates a fullscreen background, which is the only genuinely
expensive part. To keep it cheap:

- The glow title is rendered **once** into a pixmap and blitted afterwards;
  the flicker is a single opacity blit.
- Scanlines are a cached overlay blitted in one call.
- Buttons cache their rendering per state (hover, press, disabled, focus).
- The rain renders into a buffer capped at 1600×900 and scales up, so cost
  does not grow with monitor size, and it **adapts its frame rate** downward
  when a frame takes longer than 9 ms.

Measured on an idle fullscreen window at 2304×1296: a full repaint costs about
14 ms, and the process uses roughly a third of one core while animating.

---

## License

MIT — see [LICENSE](./LICENSE).

## Author

**Mani.k (AdolfMacro)**

- GitHub — <https://github.com/AdolfMacro>
- Profile — <https://adolfmacro.github.io/mani/>
- E-mail — <m4nikamran@gmail.com>
- Telegram — <https://t.me/manikamran>
