"""Phoenix GUI - fullscreen hacker-terminal front end."""

from __future__ import annotations

import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, List

from PyQt6.QtCore import QObject, QRunnable, QUrl, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QGuiApplication,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import core
from .updates import check_remote_version
from .widgets import (
    AMBER,
    CYAN,
    GREEN,
    GREEN_DIM,
    GREEN_HOT,
    RED,
    TEXT,
    TEXT_DIM,
    GlowLabel,
    MatrixRain,
    NeonButton,
    Scanlines,
    mono_font,
    pick_family,
)

APP_NAME = "Phoenix"
CONSOLE_LINES = 250
NAV_LABELS = ("BIND DATA", "READ DATA", "DEVELOPER", "UPDATE")


# --------------------------------------------------------------- theming ---
def build_stylesheet(family: str) -> str:
    return f"""
    QWidget {{
        background: transparent;
        color: {TEXT};
        font-family: "{family}";
        font-size: 15px;
    }}
    QFrame#card {{
        background: rgba(0, 20, 8, 210);
        border: 1px solid {GREEN_DIM};
        border-radius: 10px;
    }}
    QLabel#heading {{
        color: {GREEN};
        font-size: 15px;
        font-weight: bold;
    }}
    QLabel#subtle {{ color: {TEXT_DIM}; font-size: 13px; }}
    QLabel#value {{
        color: {GREEN_HOT};
        font-size: 15px;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#error {{ color: {RED}; font-size: 14px; font-weight: bold; }}
    QLabel#ok {{ color: {GREEN}; font-size: 14px; font-weight: bold; }}
    QLineEdit {{
        background: rgba(0, 8, 4, 220);
        border: 1px solid {GREEN_DIM};
        border-radius: 6px;
        padding: 9px 11px;
        color: {GREEN_HOT};
        selection-background-color: {GREEN_DIM};
    }}
    QLineEdit:focus {{ border: 1px solid {GREEN}; }}
    QLineEdit:disabled {{ color: {TEXT_DIM}; }}
    QPlainTextEdit {{
        background: rgba(0, 6, 3, 235);
        border: 1px solid {GREEN_DIM};
        border-radius: 8px;
        padding: 10px;
        color: {TEXT};
        selection-background-color: {GREEN_DIM};
    }}
    QPlainTextEdit:focus {{ border: 1px solid {GREEN}; }}
    QCheckBox {{ color: {TEXT}; spacing: 10px; background: transparent; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px;
        border: 1px solid {GREEN_DIM};
        border-radius: 4px;
        background: rgba(0, 8, 4, 220);
    }}
    QCheckBox::indicator:checked {{ background: {GREEN}; border: 1px solid {GREEN}; }}
    QProgressBar {{
        background: rgba(0, 8, 4, 220);
        border: 1px solid {GREEN_DIM};
        border-radius: 5px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {GREEN_DIM}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    """


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("heading")
    return label


def subtle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    return label


def status_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    return label


def repaint_status(label: QLabel, text: str, kind: str) -> None:
    label.setObjectName(kind)
    label.setText(text)
    label.style().unpolish(label)
    label.style().polish(label)


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return frame, layout


def file_row(
    caption: str,
    placeholder: str,
    on_browse: Callable[[], None],
) -> tuple[QWidget, QLineEdit]:
    """A labelled read-only path field with a Browse button."""
    holder = QWidget()
    column = QVBoxLayout(holder)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(6)
    column.addWidget(heading(caption))

    row = QHBoxLayout()
    row.setSpacing(10)
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setReadOnly(True)
    browse = NeonButton("BROWSE", size=15)
    browse.setFixedWidth(170)
    browse.clicked.connect(on_browse)
    row.addWidget(edit, 1)
    row.addWidget(browse, 0)
    column.addLayout(row)
    return holder, edit


def text_area(placeholder: str, readonly: bool = False, size: int = 16):
    editor = QPlainTextEdit()
    editor.setPlaceholderText(placeholder)
    editor.setReadOnly(readonly)
    editor.setFont(mono_font(size, family=pick_family()))
    editor.setTabStopDistance(28)
    editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    return editor


def action_row(*buttons: NeonButton) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    for button in buttons:
        row.addWidget(button)
    row.addStretch(1)
    return row


def small_button(label: str, hint: str, width: int, slot: Callable[[], None]) -> NeonButton:
    button = NeonButton(label, hint=hint, size=14)
    button.setFixedWidth(width)
    button.clicked.connect(slot)
    return button


# ------------------------------------------------------------ background ---
class Background(QWidget):
    """Owns the animated rain; always kept behind every other widget."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.rain = MatrixRain(self)
        self.setGeometry(parent.rect())

    def resizeEvent(self, event) -> None:  # noqa: N802
        self.rain.setGeometry(self.rect())
        super().resizeEvent(event)


# --------------------------------------------------------------- workers ---
class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)


class _Worker(QRunnable):
    """Runs a blocking call off the GUI thread."""

    def __init__(self, fn: Callable[[], object], signals: _Signals) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except core.PhoenixError as exc:
            self._signals.failed.emit(str(exc))
        except Exception:
            self._signals.failed.emit(
                "Unexpected failure:\n" + traceback.format_exc(limit=3)
            )
        else:
            self._signals.done.emit(result)


# ----------------------------------------------------------------- pages ---
class BindPage(QWidget):
    def __init__(self, host: "PhoenixWindow") -> None:
        super().__init__()
        self.host = host
        self._key = core.generate_key()
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        left_card, left = card()
        left.addWidget(heading("01 / BIND  -  hide data inside a PNG"))
        left.addWidget(
            subtle(
                "The payload is appended after the image's IEND chunk. The "
                "picture itself is never touched and still opens normally."
            )
        )

        self.src_holder, self.src_edit = file_row(
            "SOURCE IMAGE", "select a .png carrier ...", self._pick_source
        )
        left.addWidget(self.src_holder)

        self.dst_holder, self.dst_edit = file_row(
            "OUTPUT IMAGE", "where to write the carrier ...", self._pick_target
        )
        left.addWidget(self.dst_holder)

        self.encrypt_box = QCheckBox("ENCRYPT PAYLOAD WITH A NEW FERNET KEY")
        self.encrypt_box.setChecked(True)
        self.encrypt_box.toggled.connect(self._on_encrypt_toggled)
        left.addWidget(self.encrypt_box)

        self.key_holder, self.key_edit = file_row(
            "DECRYPTION KEY", "mint or paste a key ...", self._new_key
        )
        self.key_edit.setReadOnly(True)
        self.key_holder.layout().addLayout(
            action_row(
                small_button("NEW KEY", "R", 150, self._new_key),
                small_button("COPY", "C", 130, lambda: self.host.copy(self.key_edit.text(), "key")),
            )
        )
        left.addWidget(self.key_holder)
        left.addStretch(1)

        right_card, right = card()
        right.addWidget(heading("PAYLOAD"))
        self.payload_edit = text_area("type the secret to hide ...")
        right.addWidget(self.payload_edit, 1)
        right.addLayout(
            action_row(
                small_button("LOAD FROM FILE", "L", 230, self._load_payload),
                small_button("CLEAR", "", 150, self.payload_edit.clear),
            )
        )

        self.bind_button = NeonButton("BIND DATA  >>", hint="RUN", size=20)
        self.bind_button.clicked.connect(self._bind)
        self.bind_status = status_label()
        right.addWidget(self.bind_button)
        right.addWidget(self.bind_status)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        columns.addWidget(left_card, 5)
        columns.addWidget(right_card, 6)
        root.addLayout(columns, 1)

        self._on_encrypt_toggled(True)

    # -- field handlers -------------------------------------------------
    def _pick_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select the carrier PNG", "", "PNG images (*.png);;All files (*)"
        )
        if not path:
            return
        self.src_edit.setText(path)
        source = Path(path)
        self.dst_edit.setText(str(source.with_name(f"{source.stem}_phoenix.png")))
        self.host.log(f"carrier selected -> {source.name}")

    def _pick_target(self) -> None:
        start = self.src_edit.text() or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the output PNG", start, "PNG images (*.png)"
        )
        if path:
            self.dst_edit.setText(path if path.lower().endswith(".png") else path + ".png")

    def _load_payload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load payload", "", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            self.payload_edit.setPlainText(
                Path(path).read_text(encoding="utf-8", errors="replace")
            )
            self.host.log(f"payload loaded <- {Path(path).name}")
        except OSError as exc:
            self._fail(f"Cannot read {Path(path).name}: {exc}")

    def _new_key(self) -> None:
        self._key = core.generate_key()
        self.key_edit.setText(self._key)
        self.host.log("fresh Fernet key minted")

    def _on_encrypt_toggled(self, checked: bool) -> None:
        self.key_holder.setVisible(bool(checked))
        if checked and not self.key_edit.text():
            self._new_key()

    def _fail(self, message: str) -> None:
        repaint_status(self.bind_status, message, "error")
        self.host.log(message, "error")

    # -- action ---------------------------------------------------------
    def _bind(self) -> None:
        raw = self.payload_edit.toPlainText()
        source = self.src_edit.text()
        target = self.dst_edit.text()
        encrypt = self.encrypt_box.isChecked()
        key = self._key

        if not raw.strip():
            self._fail("Payload is empty. Type something to hide first.")
            return
        if not target:
            self._fail("Pick an output file name first.")
            return

        payload = core.encrypt_payload(raw, key) if encrypt else raw
        started = time.perf_counter()
        self.bind_button.setEnabled(False)
        repaint_status(self.bind_status, "writing payload ...", "subtle")

        def job() -> dict:
            written = core.bind(source, target, payload)
            return {
                "written": written,
                "encrypted": encrypt,
                "elapsed": time.perf_counter() - started,
                "info": core.inspect(target),
            }

        def done(result: dict) -> None:
            self.bind_button.setEnabled(True)
            mode = "encrypted" if result["encrypted"] else "plaintext"
            name = Path(result["info"]["path"]).name
            repaint_status(
                self.bind_status,
                f"OK   {result['written']} bytes ({mode}) -> {name}   "
                f"in {result['elapsed'] * 1000:.0f} ms",
                "ok",
            )
            self.host.log(f"bound {result['written']} bytes -> {name} ({mode})")
            if result["encrypted"]:
                self.host.log(
                    "save that key, it is the only way back", "warn"
                )

        def failed(message: str) -> None:
            self.bind_button.setEnabled(True)
            self._fail(message)

        self.host.run(job, done, failed)


class ReadPage(QWidget):
    def __init__(self, host: "PhoenixWindow") -> None:
        super().__init__()
        self.host = host
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        left_card, left = card()
        left.addWidget(heading("02 / READ  -  extract hidden data"))
        left.addWidget(
            subtle(
                "Pick a Phoenix image. Tick the encryption box only if the "
                "payload was bound with a key."
            )
        )

        self.src_holder, self.src_edit = file_row(
            "IMAGE TO INSPECT", "select a png carrying data ...", self._pick
        )
        left.addWidget(self.src_holder)

        self.info = status_label()
        left.addWidget(self.info)

        self.enc_box = QCheckBox("THE HIDDEN DATA IS ENCRYPTED")
        self.enc_box.toggled.connect(self._on_enc_toggled)
        left.addWidget(self.enc_box)

        self.key_holder, self.key_edit = file_row(
            "DECRYPTION KEY", "paste the key you stored at bind time ...",
            self._paste_key,
        )
        self.key_edit.setReadOnly(False)
        key_layout = self.key_holder.layout()
        key_layout.addLayout(
            action_row(
                small_button("PASTE", "V", 150, self._paste_key),
                small_button("COPY", "C", 150,
                             lambda: self.host.copy(self.out_edit.toPlainText(), "payload")),
            )
        )
        key_layout.addLayout(
            action_row(
                small_button("SAVE", "S", 150, self._save_result),
                small_button("REVEAL", "", 150, self._reveal),
            )
        )
        left.addWidget(self.key_holder)
        left.addStretch(1)

        right_card, right = card()
        right.addWidget(heading("RECOVERED DATA"))
        self.out_edit = text_area("the hidden message appears here ...", readonly=True)
        right.addWidget(self.out_edit, 1)

        self.read_button = NeonButton("READ DATA  >>", hint="RUN", size=20)
        self.read_button.clicked.connect(self._read)
        self.read_status = status_label()
        right.addWidget(self.read_button)
        right.addWidget(self.read_status)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        columns.addWidget(left_card, 5)
        columns.addWidget(right_card, 6)
        root.addLayout(columns, 1)

        self._on_enc_toggled(False)

    # -- field handlers -------------------------------------------------
    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select the PNG to inspect", "", "PNG images (*.png);;All files (*)"
        )
        if path:
            self.src_edit.setText(path)
            self.host.describe(path)

    def _paste_key(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            self._fail("Clipboard is empty.")
            return
        self.key_edit.setText(text)
        self.enc_box.setChecked(True)
        self.host.log("key pasted from clipboard")

    def _on_enc_toggled(self, checked: bool) -> None:
        self.key_holder.setVisible(bool(checked))
        if checked:
            self.key_edit.setFocus()

    def _fail(self, message: str) -> None:
        repaint_status(self.read_status, message, "error")
        self.host.log(message, "error")

    def _save_result(self) -> None:
        data = self.out_edit.toPlainText()
        if not data:
            self._fail("Nothing to save yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save recovered data", "recovered.txt", "Text files (*.txt)"
        )
        if not path:
            return
        try:
            Path(path).write_text(data, encoding="utf-8")
            self.host.log(f"recovered data written -> {Path(path).name}")
        except OSError as exc:
            self._fail(f"Cannot write {Path(path).name}: {exc}")

    def _reveal(self) -> None:
        path = self.src_edit.text()
        if not path or not Path(path).is_file():
            self._fail("Pick an existing image first.")
            return
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["explorer", f"/select,{path}"])
        except OSError as exc:
            self._fail(f"No file manager available: {exc}")

    # -- action ---------------------------------------------------------
    def _read(self) -> None:
        path = self.src_edit.text()
        key = self.key_edit.text() if self.enc_box.isChecked() else None
        if not path:
            self._fail("Select an image first.")
            return
        self.read_button.setEnabled(False)
        repaint_status(self.read_status, "scanning image ...", "subtle")
        started = time.perf_counter()

        def job() -> dict:
            return {
                "payload": core.read(path, key),
                "meta": core.inspect(path),
                "elapsed": time.perf_counter() - started,
            }

        def done(result: dict) -> None:
            self.read_button.setEnabled(True)
            self.out_edit.setPlainText(result["payload"])
            meta = result["meta"]
            repaint_status(
                self.read_status,
                f"OK   {meta['payload_size']} bytes extracted in "
                f"{result['elapsed'] * 1000:.0f} ms",
                "ok",
            )
            self.host.log(f"extracted {meta['payload_size']} bytes from {meta['name']}")

        def failed(message: str) -> None:
            self.read_button.setEnabled(True)
            self.out_edit.clear()
            self._fail(message)

        self.host.run(job, done, failed)


class DevPage(QWidget):
    def __init__(self, host: "PhoenixWindow") -> None:
        super().__init__()
        self.host = host
        frame, layout = card()
        layout.addWidget(heading("03 / DEVELOPER"))
        body = QLabel(
            "<div>"
            "<span style='color:#00ff66'>PHOENIX</span> &mdash; PNG steganography.<br><br>"
            "<b>Author</b>&nbsp;&nbsp;&nbsp; Mani.k (AdolfMacro)<br>"
            "<b>GitHub</b>&nbsp;&nbsp;&nbsp;"
            "<a href='https://github.com/AdolfMacro/phoenix' "
            "style='color:#00e5ff'>github.com/AdolfMacro/phoenix</a><br>"
            "<b>Profile</b>&nbsp;&nbsp;"
            "<a href='https://adolfmacro.github.io/mani/' "
            "style='color:#00e5ff'>adolfmacro.github.io/mani</a><br>"
            "<b>E-mail</b>&nbsp;&nbsp;&nbsp; m4nikamran@gmail.com<br>"
            "<b>Telegram</b>&nbsp;"
            "<a href='https://t.me/manikamran' "
            "style='color:#00e5ff'>t.me/manikamran</a><br><br>"
            "<span style='color:#4fbf80'>Interface: fullscreen terminal UI, neon "
            "glow, matrix rain.<br>Engine: pure-python steganography over the PNG "
            "IEND chunk, optional Fernet (AES-128-CBC + HMAC-SHA256) encryption.</span>"
            "</div>"
        )
        body.setObjectName("subtle")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setOpenExternalLinks(True)
        body.setFont(mono_font(16, family=pick_family()))
        body.setWordWrap(True)
        # 'Ignored' stops the label's text width from becoming the page's
        # minimum width, which used to starve the navigation column.
        body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(body, 1)

        links = QHBoxLayout()
        for label, url in (
            ("GITHUB", "https://github.com/AdolfMacro/phoenix"),
            ("PROFILE", "https://adolfmacro.github.io/mani/"),
            ("TELEGRAM", "https://t.me/manikamran"),
        ):
            button = small_button(label, "", 230, lambda u=url: QGuiApplication.openUrl(QUrl(u)))
            links.addWidget(button)
        links.addStretch(1)
        layout.addLayout(links)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(frame, 1)


class UpdatePage(QWidget):
    def __init__(self, host: "PhoenixWindow") -> None:
        super().__init__()
        self.host = host
        frame, layout = card()
        layout.addWidget(heading("04 / UPDATE"))

        row = QHBoxLayout()
        row.addWidget(subtle("installed version"))
        self.version = QLabel(host.version)
        self.version.setObjectName("value")
        row.addWidget(self.version)
        row.addStretch(1)
        layout.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setVisible(False)
        layout.addWidget(self.bar)

        self.message = status_label()
        layout.addWidget(self.message)

        self.check_button = small_button("CHECK FOR UPDATES", "RUN", 400, self._check)
        layout.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(
            small_button("SHOW INSTALLER COMMAND", "", 400, self._installer),
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(
            subtle(
                "Phoenix compares its local VERSION.txt against the copy "
                "published on GitHub. Applying an update rewrites "
                "/usr/src/phoenix and needs sudo."
            )
        )
        layout.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(frame, 1)

    def _check(self) -> None:
        self.check_button.setEnabled(False)
        self.bar.setVisible(True)
        repaint_status(self.message, "contacting github ...", "subtle")

        def done(result: dict) -> None:
            self.bar.setVisible(False)
            self.check_button.setEnabled(True)
            if result.get("error"):
                repaint_status(self.message, result["error"], "error")
                self.host.log(f"update check failed: {result['error']}", "error")
            elif result.get("outdated"):
                repaint_status(
                    self.message,
                    f"A newer build is available: {result['remote']} "
                    f"(you run {result['local']}).",
                    "subtle",
                )
                self.host.log(
                    f"update available: {result['local']} -> {result['remote']}", "warn"
                )
            elif result.get("ahead"):
                repaint_status(
                    self.message,
                    f"You are ahead of the published build: {result['local']} "
                    f"local vs {result['remote']} on GitHub. Push VERSION.txt "
                    "once this build is published.",
                    "subtle",
                )
                self.host.log(
                    f"local {result['local']} is ahead of published "
                    f"{result['remote']}"
                )
            else:
                repaint_status(
                    self.message, f"You are on the latest build ({result['remote']}).",
                    "ok",
                )
                self.host.log(f"up to date ({result['remote']})")

        def failed(message: str) -> None:
            self.bar.setVisible(False)
            self.check_button.setEnabled(True)
            repaint_status(self.message, message, "error")

        self.host.run(check_remote_version, done, failed)

    def _installer(self) -> None:
        script = self.host.installer_path
        if not script.is_file():
            repaint_status(self.message, "installer.sh was not found.", "error")
            return
        repaint_status(self.message, f"Run this in a terminal:\n\n    bash {script}", "subtle")
        self.host.log(f"installer located at {script}")


# ---------------------------------------------------------------- window ---
class PhoenixWindow(QWidget):
    def __init__(self, version: str = "0.2:1") -> None:
        super().__init__()
        self.version = version
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.installer_path = (
            Path(__file__).resolve().parent.parent / "installer.sh"
        )
        self._nav: List[NeonButton] = []
        self.resize(1320, 880)
        self._windowed_state = None

        self.setWindowTitle(f"{APP_NAME} {version}")
        self.background = Background(self)
        self._scanlines = Scanlines(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(46, 24, 46, 20)
        root.setSpacing(14)
        # The console is built first: pages log into it while they are
        # constructed, so it has to exist before the page objects do.
        header = self._build_header()
        console = self._build_console()
        root.addWidget(header, 0)
        root.addLayout(self._build_body(), 1)
        root.addWidget(console, 0)

        self._install_shortcuts()
        # Default presentation is fullscreen; F11 / ESC toggle it afterwards.
        self.show()
        self._windowed_state = self.saveGeometry()
        self.showFullScreen()
        QTimer.singleShot(0, lambda: self.log(f"{APP_NAME} {version} online"))

    # -- construction ---------------------------------------------------
    def _build_header(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.title = GlowLabel("PHOENIX", size=120, color=GREEN)
        self.title.setMinimumHeight(200)
        self.title.setToolTip("Phoenix")
        column.addWidget(self.title)

        tagline = QLabel(
            "S T E G A N O G R A P H Y &nbsp;//&nbsp; H I D E &nbsp; D A T A "
            "&nbsp; I N S I D E &nbsp; P N G"
        )
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:16px; background:transparent;"
        )
        column.addWidget(tagline)

        badge = QLabel(f"v{self.version}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"color:{GREEN}; font-size:13px; background:transparent;")
        column.addWidget(badge)
        return holder

    def _build_body(self) -> QHBoxLayout:
        body = QHBoxLayout()
        body.setSpacing(22)

        menu = QVBoxLayout()
        menu.setSpacing(12)
        menu.addWidget(heading("OPERATIONS"))
        colors = (GREEN, CYAN, GREEN, AMBER)
        for index, label in enumerate(NAV_LABELS):
            button = NeonButton(label, hint=str(index + 1), color=colors[index], size=19)
            button.clicked.connect(lambda _=False, i=index: self.select(i))
            menu.addWidget(button)
            self._nav.append(button)

        quit_button = NeonButton("EXIT", hint="5", color=RED, size=19)
        quit_button.clicked.connect(self.close)
        menu.addWidget(quit_button)
        menu.addStretch(1)
        menu.addWidget(subtle("F11 fullscreen\nESC leave fullscreen\nCTRL+Q quit"))

        self.stack = QStackedWidget()
        self.bind_page = BindPage(self)
        self.read_page = ReadPage(self)
        self.update_page = UpdatePage(self)
        self._pages = [self.bind_page, self.read_page, DevPage(self), self.update_page]
        for page in self._pages:
            self.stack.addWidget(page)

        # The menu lives in a wrapper with a real minimum width: without it a
        # wide page can squeeze the column and clip every button label.
        menu_box = QWidget()
        menu_box.setLayout(menu)
        menu_box.setMinimumWidth(252)
        menu_box.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        body.addWidget(menu_box, 0)
        body.addWidget(self.stack, 1)
        self.select(0)
        return body

    def _build_console(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(128)
        self.console.setMaximumBlockCount(CONSOLE_LINES)
        self.console.setFont(mono_font(13, family=pick_family()))
        self.console.setStyleSheet(
            f"QPlainTextEdit{{background:rgba(0,10,5,205);"
            f"border:1px solid {GREEN_DIM};border-radius:8px;"
            f"color:{TEXT_DIM};padding:8px;}}"
        )
        column.addWidget(self.console)

        footer = QHBoxLayout()
        self.status = QLabel("[ ready ]")
        self.status.setObjectName("subtle")
        footer.addWidget(self.status)
        footer.addStretch(1)
        footer.addWidget(
            small_button("FULLSCREEN", "F11", 230, self.toggle_full_screen)
        )
        column.addLayout(footer)
        return holder

    def _install_shortcuts(self) -> None:
        def bind(keys: str, slot: Callable[[], None]) -> None:
            QShortcut(QKeySequence(keys), self, activated=slot)

        for index, label in enumerate(NAV_LABELS):
            bind(str(index + 1), lambda i=index: self.select(i))
        bind("5", self.close)
        bind("F11", self.toggle_full_screen)
        bind("Esc", self.leave_full_screen)
        bind("Ctrl+Q", self.close)

    # -- state ----------------------------------------------------------
    def select(self, index: int) -> None:
        index = max(0, min(index, len(self._pages) - 1))
        self.stack.setCurrentIndex(index)
        for position, button in enumerate(self._nav):
            button.setText(
                f"> {NAV_LABELS[position]}" if position == index else f"  {NAV_LABELS[position]}"
            )

    def show_full_screen(self) -> None:
        if self.isFullScreen():
            return
        self._windowed_state = self.saveGeometry()
        self.showFullScreen()
        self.status.setText("[ fullscreen - ESC to leave ]")

    def toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.leave_full_screen()
        else:
            self.show_full_screen()

    def leave_full_screen(self) -> None:
        if not self.isFullScreen():
            return
        state = self._windowed_state
        self.showNormal()
        # Restore the pre-fullscreen geometry; the window manager applies the
        # state change asynchronously, so this has to wait a tick.
        if state is not None:
            QTimer.singleShot(0, lambda: self.restoreGeometry(state))
        self._windowed_state = None
        self.status.setText("[ windowed - F11 for fullscreen ]")

    def resizeEvent(self, event) -> None:  # noqa: N802
        self.background.setGeometry(self.rect())
        self._scanlines.setGeometry(self.rect())
        self._scanlines.raise_()
        super().resizeEvent(event)

    # -- services -------------------------------------------------------
    def log(self, message: str, level: str = "info") -> None:
        console = getattr(self, "console", None)
        if console is None:  # still booting
            return
        colors = {"info": GREEN, "warn": AMBER, "error": RED, "cmd": CYAN}
        tags = {"info": "[phoenix]", "warn": "[warning]", "error": "[failure]",
                "cmd": "[shell]"}
        color = colors.get(level, GREEN)
        stamp = time.strftime("%H:%M:%S")
        self.console.appendHtml(
            f'<span style="color:{TEXT_DIM}">{stamp} {tags.get(level, "[phoenix]")}</span> '
            f'<span style="color:{color}">{_escape(message)}</span>'
        )
        bar = self.console.verticalScrollBar()
        bar.setValue(bar.maximum())

    def copy(self, text: str, what: str) -> None:
        if not text:
            self.log(f"nothing to copy ({what})", "warn")
            return
        QGuiApplication.clipboard().setText(text)
        self.log(f"{what} copied to clipboard")

    def describe(self, path: str) -> None:
        def done(info: dict) -> None:
            kind = "encrypted" if info["encrypted"] else "plaintext"
            repaint_status(
                self.read_page.info,
                f"{info['name']}   image {info['image_size']} B   "
                f"payload {info['payload_size']} B   looks {kind}",
                "value",
            )
            if info["payload_size"] and info["encrypted"]:
                self.read_page.enc_box.setChecked(True)
            self.log(
                f"inspected {info['name']}: {info['payload_size']} payload "
                f"bytes ({kind})"
            )

        def failed(message: str) -> None:
            repaint_status(self.read_page.info, message, "error")

        self.run(lambda: core.inspect(path), done, failed)

    def run(
        self,
        fn: Callable[[], object],
        on_done: Callable[[object], None],
        on_failed: Callable[[str], None],
    ) -> None:
        signals = _Signals()
        signals.done.connect(on_done)
        signals.failed.connect(on_failed)
        self.pool.start(_Worker(fn, signals))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.log("shutting down ...")
        self.background.rain.stop()
        self.pool.waitForDone(3000)
        event.accept()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _install_sigint(app: QApplication) -> None:
    """Make Ctrl+C quit cleanly.

    Letting ``KeyboardInterrupt`` propagate out of ``paintEvent`` left the
    QPainter alive, which produced a flood of "endPaint() called with active
    painter" messages. Handling the signal instead lets the current frame
    finish and then closes the loop.
    """

    def handler(signum, frame) -> None:  # noqa: ARG001 - signal signature
        app.quit()

    try:
        import signal

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, OSError, AttributeError):  # pragma: no cover
        pass


def launch(version: str = "0.2:1") -> int:
    """Create the QApplication (if needed) and open the window."""
    app = QApplication.instance()
    owned = app is None
    if owned:
        app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(version)
    app.setStyleSheet(build_stylesheet(pick_family()))
    PhoenixWindow(version)
    _install_sigint(app)
    return app.exec() if owned else 0


def main() -> int:
    return launch()
