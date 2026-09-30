"""Hacker-terminal widget set used by the Phoenix GUI."""

from __future__ import annotations

import random
import time
from typing import List

from PyQt6.QtCore import (
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

# ---------------------------------------------------------------- palette ---
BLACK = "#000000"
GREEN = "#00ff66"
GREEN_HOT = "#c8ffd8"
GREEN_MID = "#00c853"
GREEN_DIM = "#0a5c2e"
GREEN_DEEP = "#03210f"
CYAN = "#00e5ff"
AMBER = "#ffb300"
RED = "#ff3b3b"
TEXT = "#9dffbe"
TEXT_DIM = "#4fbf80"

GLYPH_ALPHABET = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉ0123456789"
    "ABCDEFGHJKLMNPQRSTUVWXYZ<>/\\|=+-*#$%&@"
)

# Crisper, more legible faces first. DejaVu Sans Mono is a solid last resort
# but its heavy bold weight renders poorly at display sizes, so faces that
# stay readable when blown up are preferred.
_FAMILY_PREFERENCE = (
    "Consolas",
    "JetBrains Mono",
    "Fira Code",
    "Cascadia Code",
    "Cascadia Mono",
    "Iosevka",
    "Noto Sans Mono",
    "Nimbus Mono PS",
    "Ubuntu Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "FreeMono",
    "Courier New",
    "Courier",
    "Menlo",
    "Monaco",
)


def pick_family(app=None) -> str:
    """Return the first installed monospace family."""
    from PyQt6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    for name in _FAMILY_PREFERENCE:
        if name in families:
            return name
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def mono_font(size: int, bold: bool = False, family: str | None = None) -> QFont:
    font = QFont(family or pick_family(), size)
    font.setBold(bold)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


# ------------------------------------------------------------- glow label ---
def _ring(radius: float) -> tuple[tuple[float, float], ...]:
    """Eight offsets around the origin, for multi-pass glow accumulation."""
    return (
        (radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius),
        (radius, radius), (-radius, -radius),
        (radius, -radius), (-radius, radius),
    )


class GlowLabel(QWidget):
    """Display text with a real neon bloom.

    The glyphs are converted to a :class:`QPainterPath` once, then that path
    is filled repeatedly at small offsets with a falling alpha ramp. Stroking
    the text outline (the obvious approach) produces a hard ring around the
    letters at display sizes; filling offset copies reads as actual light.
    Letter tracking is applied while building the path, which gives the wide
    terminal look and keeps the glyphs from crowding each other.
    """

    def __init__(
        self,
        text: str = "",
        size: int = 96,
        color: str = GREEN,
        family: str | None = None,
        tracking: float = 0.16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        self._family = family or pick_family()
        self._tracking = tracking
        self._intensity = 1.0
        self._path: QPainterPath | None = None
        self._path_size = QSizeF()
        # The bloom costs ~40 path fills; re-running it on every repaint made
        # the title 60 ms on its own. It is rendered once and blitted after.
        self._cache: QPixmap | None = None
        self._cache_key: tuple | None = None
        self.setFont(mono_font(size, bold=True, family=self._family))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        self._flicker = QTimer(self)
        self._flicker.timeout.connect(self._on_flicker)
        self._flicker.start(200)
        self._rebuild()

    # -- public ---------------------------------------------------------
    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._text = text
        self._rebuild()

    def text(self) -> str:
        return self._text

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def setFont(self, font: QFont) -> None:  # noqa: N802 - Qt naming
        super().setFont(font)
        self._rebuild()

    def stop_animation(self) -> None:
        self._flicker.stop()

    # -- internals ------------------------------------------------------
    def _on_flicker(self) -> None:
        # Mostly steady with the occasional shallow dip, like a real tube.
        self._intensity = 1.0 if random.random() > 0.15 else random.uniform(0.78, 0.94)
        self.update()

    def _rebuild(self) -> None:
        self._path = None
        self._cache = None
        self._cache_key = None
        if not self._text:
            self.updateGeometry()
            self.update()
            return
        font = self.font()
        metrics = QFontMetricsF(font)
        tracking = metrics.height() * self._tracking
        path = QPainterPath()
        x = 0.0
        for char in self._text:
            path.addText(QPointF(x, 0.0), font, char)
            x += metrics.horizontalAdvance(char) + tracking
        bounds = path.boundingRect()
        path.translate(-bounds.left(), -bounds.top())
        self._path = path
        self._path_size = QSizeF(bounds.width(), bounds.height())
        self.setMinimumHeight(int(bounds.height() + metrics.height() * 0.55))
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        metrics = QFontMetricsF(self.font())
        extra = metrics.height() * (self._tracking * max(0, len(self._text) - 1))
        return QSize(int(self._path_size.width() + extra + 40),
                     int(metrics.height() * 1.6))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return QSize(1, int(self._path_size.height() + 12))

    # -- painting -------------------------------------------------------
    def _build_cache(self) -> None:
        """Render the glow once into an offscreen pixmap."""
        if self._path is None or self._path_size.isEmpty() or self.width() < 4:
            return
        ratio = self.devicePixelRatioF() or 1.0
        key = (self._text, self.font().key(), self.width(), self.height(), round(ratio, 2))
        if self._cache is not None and self._cache_key == key:
            return

        pixmap = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_bloom(painter)
        painter.end()

        self._cache = pixmap
        self._cache_key = key

    def _paint_bloom(self, painter: QPainter) -> None:
        path = self._path
        assert path is not None
        available = self.rect().adjusted(24, 6, -24, -6)
        scale = min(
            available.width() / self._path_size.width(),
            available.height() / self._path_size.height(),
            1.0,
        )
        if scale <= 0:
            return
        width = self._path_size.width() * scale
        height = self._path_size.height() * scale
        origin = QPointF(
            available.left() + (available.width() - width) / 2.0,
            available.top() + (available.height() - height) / 2.0,
        )

        painter.translate(origin)
        painter.scale(scale, scale)
        base = QColor(self._color)

        def fill(colour: QColor) -> None:
            painter.fillPath(path, QBrush(colour))

        # Wide faint bloom, then a tight halo hugging the glyphs.
        for radius, alpha in ((14, 9), (10, 12), (7, 16), (4, 30), (2, 70)):
            colour = QColor(base)
            colour.setAlpha(alpha)
            for dx, dy in _ring(radius):
                painter.save()
                painter.translate(dx, dy)
                fill(colour)
                painter.restore()

        fill(QColor(GREEN_HOT if base.name() == QColor(GREEN).name() else "#ffffff"))

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._path is None or self._path_size.isEmpty():
            return
        try:
            self._build_cache()
            if self._cache is None:
                return
            painter = QPainter(self)
            try:
                # The flicker is one blit instead of 41 path fills. Skip the
                # opacity blend entirely while it is at full strength, since a
                # blended blit costs roughly twice a plain copy.
                if self._intensity < 0.995:
                    painter.setOpacity(self._intensity)
                painter.drawPixmap(0, 0, self._cache)
            finally:
                painter.end()
        except KeyboardInterrupt:
            raise
        except Exception:  # pragma: no cover - never break the paint loop
            pass


# ------------------------------------------------------------ neon button ---
class NeonButton(QWidget):
    """Flat, high-contrast terminal button with a hover halo."""

    clicked = pyqtSignal()

    def __init__(
        self,
        text: str,
        hint: str = "",
        color: str = GREEN,
        size: int = 20,
        family: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._hint = hint
        self._color = QColor(color)
        self._family = family or pick_family()
        self._hover = False
        self._press = 0.0
        self._enabled = True
        # Repainting every button on every animated background frame was the
        # last big cost; the rendering only changes when the state does.
        self._cache: QPixmap | None = None
        self._cache_key: tuple | None = None
        self._font = mono_font(size, bold=True, family=self._family)
        self._hint_font = mono_font(max(11, size - 8), family=self._family)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumHeight(size * 3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setEnabled(self, value: bool) -> None:  # noqa: N802
        self._enabled = bool(value)
        self._invalidate()
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._enabled
            else Qt.CursorShape.ArrowCursor
        )
        self.update()

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self._invalidate()

    def _invalidate(self) -> None:
        self._cache = None
        self._cache_key = None
        self.update()

    def _state_key(self) -> tuple:
        return (
            self._text,
            self._hint,
            self._color.name(),
            self._enabled,
            self._hover,
            self._press > 0,
            self.hasFocus(),
            self.width(),
            self.height(),
        )

    def _build_cache(self) -> None:
        if self.width() < 4 or self.height() < 4:
            self._cache = None
            return
        key = self._state_key()
        if self._cache is not None and self._cache_key == key:
            return
        ratio = self.devicePixelRatioF() or 1.0
        pixmap = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        self._paint(target=pixmap)
        self._cache = pixmap
        self._cache_key = key

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        metrics = QFontMetrics(self._font)
        hint = QFontMetrics(self._hint_font).horizontalAdvance(f"[{self._hint}]")
        return QSize(max(170, metrics.horizontalAdvance(self._text) + hint + 64),
                    metrics.height() * 2 + 14)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        # A button may be squeezed by its layout; paintEvent elides the
        # label rather than clipping it, so the minimum stays small and the
        # surrounding columns keep their space.
        return QSize(56, self._font.pointSize() * 2 + 10)

    # -- events ---------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self._invalidate()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._press = 0.0
        self._invalidate()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self._press = 1.0
            self._invalidate()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            was = self._press
            self._press = 0.0
            self._invalidate()
            if was and self.rect().contains(event.position().toPoint()):
                self.clicked.emit()

    def focusInEvent(self, event) -> None:  # noqa: N802
        self._invalidate()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._invalidate()
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._enabled:
                self.clicked.emit()
            return
        super().keyPressEvent(event)

    # -- paint ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        try:
            self._build_cache()
            if self._cache is not None:
                painter = QPainter(self)
                try:
                    painter.drawPixmap(0, 0, self._cache)
                finally:
                    painter.end()
                return
            self._paint(event)
        except KeyboardInterrupt:
            raise
        except Exception:  # pragma: no cover - never break the paint loop
            pass

    def _paint(self, event=None, target=None) -> None:  # noqa: N802
        if target is not None:
            painter = QPainter(target)
        else:
            painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        box = self.rect().adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(box), 8, 8)

        fill = QColor(GREEN_DEEP if (self._hover or self._press) else BLACK)
        fill.setAlpha(220)
        painter.fillPath(path, fill)

        border = QColor(self._color)
        if not self._enabled:
            border = QColor(TEXT_DIM)
            border.setAlpha(90)
        painter.setPen(QPen(border, 2 if self._hover else 1))
        painter.drawPath(path)

        if self._hover and self._enabled:
            glow = QColor(self._color)
            glow.setAlpha(70)
            painter.setPen(QPen(glow, 6))
            painter.drawPath(path)

        painter.setFont(self._font)
        text_color = QColor(self._color) if self._enabled else QColor(TEXT_DIM)
        if self._press:
            text_color = QColor(GREEN_HOT)

        metrics = QFontMetrics(self._font)
        hint_metrics = QFontMetrics(self._hint_font)
        pad = 16
        gap = 12
        right = pad

        # Reserve room for the shortcut hint only when it genuinely fits,
        # then elide the label instead of letting Qt clip it mid-word.
        hint_text = f"[{self._hint}]" if self._hint else ""
        hint_width = hint_metrics.horizontalAdvance(hint_text) if hint_text else 0
        if hint_text and metrics.horizontalAdvance(self._text) + hint_width + gap + 2 * pad > box.width():
            hint_text = ""

        text_rect = box.adjusted(pad, 0, -(pad + hint_width + (gap if hint_text else 0)), 0)
        label = metrics.elidedText(
            self._text, Qt.TextElideMode.ElideRight, max(0, text_rect.width())
        )
        painter.setPen(QPen(text_color))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        if hint_text:
            painter.setFont(self._hint_font)
            painter.setPen(QPen(QColor(TEXT_DIM) if self._enabled else QColor(GREEN_DEEP)))
            painter.drawText(
                box.adjusted(0, 0, -pad, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                hint_text,
            )

        if self.hasFocus():
            painter.setPen(QPen(QColor(self._color), 1, Qt.PenStyle.DashLine))
            painter.drawPath(path)
        painter.end()



# ----------------------------------------------------------- matrix rain ---
class MatrixRain(QWidget):
    """Animated falling glyphs, rendered on a half-resolution buffer.

    A 4K display would need thousands of glyphs per frame at native scale;
    drawing into a half-size pixmap and letting Qt smooth-scale it up keeps
    the animation cheap and doubles as a blur, which suits the glow.
    """

    def __init__(self, parent: QWidget | None = None, fps: int = 14) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._columns: List[int] = []
        self._speed: List[float] = []
        self._buffer: QPixmap | None = None
        self._vignette: QPixmap | None = None
        self._font = mono_font(16, family=pick_family())
        self._glyphs: List[QPixmap] = []
        self._head_count = 0
        self._rows = 1
        self._glyph_w = 10
        self._glyph_h = 20
        self._base_interval = max(16, int(1000 / fps))
        self._interval = self._base_interval
        self._last_paint_ms = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(self._interval)

    def stop(self) -> None:
        self._timer.stop()

    def _retune(self) -> None:
        """Back off on slow machines, speed up on fast ones.

        Repainting the rain invalidates every sibling widget that shares the
        window backing store, so the frame budget matters far more here than
        anywhere else.
        """
        cost = self._last_paint_ms
        if cost > 9 and self._interval < 260:
            target = min(260, int(self._interval * 1.35) + 4)
        elif cost < 5 and self._interval > self._base_interval:
            target = max(self._base_interval, int(self._interval * 0.8))
        else:
            return
        self._interval = target
        self._timer.start(target)

    # -- setup ----------------------------------------------------------
    # The buffer is upscaled to the widget, so capping it keeps the per-frame
    # cost flat on 4K displays instead of growing with the pixel count.
    MAX_BUFFER_W = 1600
    MAX_BUFFER_H = 900

    def _buffer_size(self) -> tuple[int, int]:
        width = max(2, self.width() // 2)
        height = max(2, self.height() // 2)
        if width > self.MAX_BUFFER_W or height > self.MAX_BUFFER_H:
            scale = min(self.MAX_BUFFER_W / width, self.MAX_BUFFER_H / height)
            width = max(2, int(width * scale))
            height = max(2, int(height * scale))
        return width, height

    def _prepare(self) -> None:
        width, height = self._buffer_size()

        metrics = QFontMetrics(self._font)
        self._glyph_w = max(6, metrics.horizontalAdvance("W"))
        self._glyph_h = max(12, metrics.height())

        glyphs: List[QPixmap] = []
        head_colors = (GREEN, "#aaffc4", CYAN, GREEN_MID)
        tail_colors = (GREEN_DIM, "#0d7a3a", "#0a5c2e", "#074a24")
        for color in head_colors + tail_colors:
            for char in GLYPH_ALPHABET:
                pixmap = QPixmap(self._glyph_w + 2, self._glyph_h + 2)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setFont(self._font)
                painter.setPen(QPen(QColor(color)))
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, char)
                painter.end()
                glyphs.append(pixmap)

        buffer = QPixmap(width, height)
        buffer.fill(QColor(BLACK))

        # Opaque vignette, pre-composited onto black. Each frame then starts
        # with a straight copy rather than a fillRect plus an alpha blend,
        # which was the single most expensive step at 4K.
        vignette = QPixmap(width, height)
        vignette.fill(QColor(BLACK))
        vp = QPainter(vignette)
        shade = QRadialGradient(
            QPointF(width / 2.0, height / 2.0),
            max(width, height) * 0.75,
        )
        shade.setColorAt(0.0, QColor(0, 0, 0, 90))
        shade.setColorAt(1.0, QColor(0, 0, 0, 205))
        vp.fillRect(vignette.rect(), QBrush(shade))
        vp.end()

        # Swap everything in one go: a paint event can never observe a
        # half-built state.
        self._glyphs = glyphs
        self._head_count = len(head_colors) * len(GLYPH_ALPHABET)
        self._buffer = buffer
        self._vignette = vignette

        count = max(1, width // (self._glyph_w * 3))
        rows = max(1, height // self._glyph_h)
        self._columns = [-random.randint(0, rows) for _ in range(count)]
        self._speed = [random.uniform(0.25, 1.0) for _ in range(count)]
        self._rows = rows

    # -- animation ------------------------------------------------------
    def _advance(self) -> None:
        if self._buffer is None or self._buffer.size() != QSize(*self._buffer_size()):
            self._prepare()
            return
        for index, y in enumerate(self._columns):
            self._columns[index] = (y + self._speed[index]) % self._rows
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._prepare()
        super().resizeEvent(event)

    # -- paint ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        buffer = self._buffer
        glyphs = self._glyphs
        head = self._head_count
        if buffer is None or not glyphs or head >= len(glyphs):
            return

        started = time.perf_counter()
        painter = QPainter(buffer)
        try:
            if self._vignette is not None:
                painter.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_Source
                )
                painter.drawPixmap(0, 0, self._vignette)
                painter.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_SourceOver
                )
            glyph_h = self._glyph_h
            rows = self._rows
            for col, head_row in enumerate(self._columns):
                x = col * self._glyph_w * 2
                if x + self._glyph_w >= buffer.width():
                    continue
                # Cap the trail: on a 4K buffer the alpha-blended glyph blits
                # were costing more than everything else combined.
                trail = random.randint(5, max(6, min(12, rows // 3)))
                for offset in range(trail):
                    row = head_row - offset
                    if row < 0:
                        break
                    if offset == 0:
                        pixmap = glyphs[random.randrange(head)]
                        painter.setOpacity(1.0)  # the leading glyph burns brighter
                    else:
                        fade = 1.0 - offset / trail
                        pixmap = glyphs[head + random.randrange(len(glyphs) - head)]
                        painter.setOpacity(0.25 + 0.6 * fade * fade)
                    painter.drawPixmap(int(x), int(row * glyph_h), pixmap)
        finally:
            painter.end()

        screen = QPainter(self)
        try:
            screen.drawPixmap(self.rect(), buffer)
        finally:
            screen.end()
        self._last_paint_ms = (time.perf_counter() - started) * 1000.0
        self._retune()


# ------------------------------------------------------------ scan lines ---
class Scanlines(QWidget):
    """Static CRT scanline overlay drawn above everything.

    Tiling a 1 x spacing brush, or drawing a few hundred individual lines,
    cost 11-35 ms per full-screen repaint. The overlay is completely static,
    so it is built once per resize and blitted afterwards.
    """

    def __init__(self, parent: QWidget | None = None, spacing: int = 4) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._spacing = max(2, spacing)
        self._overlay: QPixmap | None = None

    def _build(self) -> None:
        width = max(1, self.width())
        height = max(1, self.height())
        if width < 2 or height < 2:
            self._overlay = None
            return
        ratio = self.devicePixelRatioF() or 1.0
        overlay = QPixmap(int(width * ratio), int(height * ratio))
        overlay.setDevicePixelRatio(ratio)
        overlay.fill(Qt.GlobalColor.transparent)
        painter = QPainter(overlay)
        painter.setPen(QPen(QColor(0, 0, 0, 46), 1))
        for y in range(0, height, self._spacing):
            painter.drawLine(0, y, width, y)
        painter.end()
        self._overlay = overlay

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._build()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._overlay is None or self._overlay.size() != self.size() * self.devicePixelRatioF():
            self._build()
        if self._overlay is None:
            return
        painter = QPainter(self)
        try:
            painter.drawPixmap(0, 0, self._overlay)
        finally:
            painter.end()
