# PAIO-Omni · bubble.py  v3.2
"""
The native OS widget UI — a frameless, translucent, always-on-top orb
that floats over everything else, freely draggable, defaulting to the
top-right corner on every launch (no position persistence).

v3.2: all drawing logic moved out to orb_visuals.py. This file owns
only the mechanics — dragging, click-vs-drag detection, expand/collapse,
state tracking, and the QTimer driving `phase` forward — and calls
whichever orb_visuals function matches the current state on every
repaint. See orb_visuals.py to change how any state actually looks;
nothing in this file should need to change for that.

All background work (STT, TTS, LLM calls) happens off the Qt main
thread; this module only exposes thread-safe signals for state changes
and expand/collapse so orchestrator.py's worker threads never touch
Qt objects directly from the wrong thread.
"""

from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, Signal, QObject, QEasingCurve
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QApplication

import orb_visuals

IDLE, LISTENING, THINKING, MAKING = "idle", "listening", "thinking", "making"

ORB_SIZE = 88
PANEL_SIZE = (360, 480)
MARGIN = 24

_STATE_SPEED = {
    IDLE: 0.015,
    LISTENING: 0.05,
    THINKING: 0.09,
    MAKING: 0.07,
}


class OrbWidget(QWidget):
    """The circular orb itself. Draws nothing on its own — every pixel
    comes from orb_visuals.py; this class just drives the animation
    clock and hands off to the right function each frame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(ORB_SIZE, ORB_SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._state = IDLE
        self._phase = 0.0    # 0..1, loops continuously
        self._ripple = 0.0   # 0..1, only meaningful during LISTENING

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30fps — smooth without hammering the CPU

    def set_state(self, state: str):
        if state not in (IDLE, LISTENING, THINKING, MAKING):
            return
        self._state = state
        if state == LISTENING:
            self._ripple = 0.0

    def _tick(self):
        self._phase = (self._phase + _STATE_SPEED[self._state]) % 1.0
        if self._state == LISTENING:
            self._ripple = (self._ripple + 0.04) % 1.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(4, 4, ORB_SIZE - 8, ORB_SIZE - 8)

        if self._state == IDLE:
            orb_visuals.idle(painter, rect, self._phase)
        elif self._state == LISTENING:
            orb_visuals.listening(painter, rect, self._phase, self._ripple)
        elif self._state == THINKING:
            orb_visuals.thinking(painter, rect, self._phase)
        elif self._state == MAKING:
            orb_visuals.making(painter, rect, self._phase)

        painter.end()


class Bubble(QWidget):
    """Top-level frameless/translucent/always-on-top window. Freely
    draggable; always resets to the top-right corner on launch."""

    stateChanged = Signal(str)
    triggered = Signal()  # emitted on click — orchestrator wires this to wake handling

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(ORB_SIZE, ORB_SIZE)

        self._orb = OrbWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._orb)

        self._expanded = False
        self._drag_offset = None
        self._response_label = None

        self._reset_to_top_right()

    def _reset_to_top_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - ORB_SIZE - MARGIN
        y = screen.top() + MARGIN
        self.move(x, y)

    # ---- dragging ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._was_drag = False

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self._was_drag = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not getattr(self, "_was_drag", False):
                self.triggered.emit()
            self._drag_offset = None

    # ---- state / expansion (call these from the Qt main thread only —
    # orchestrator.py should route worker-thread updates through a
    # Signal rather than calling these directly from another thread) ----
    def set_state(self, state: str):
        self._orb.set_state(state)
        self.stateChanged.emit(state)

    def expand(self):
        if self._expanded:
            return
        self._expanded = True
        start = self.geometry()
        end_w, end_h = PANEL_SIZE
        screen = QApplication.primaryScreen().availableGeometry()
        end_x = screen.right() - end_w - MARGIN
        end_y = screen.top() + MARGIN

        self.setFixedSize(end_w, end_h)
        self._response_label = QTextEdit(self)
        self._response_label.setReadOnly(True)
        self._response_label.setStyleSheet(
            "background: rgba(15,15,18,235); color: #eee; border: none; "
            "border-radius: 12px; padding: 12px; font-size: 13px;"
        )
        self._response_label.setGeometry(0, ORB_SIZE + 8, end_w, end_h - ORB_SIZE - 8)
        self._response_label.show()

        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(self.geometry().__class__(end_x, end_y, end_w, end_h))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim  # keep a reference so it isn't garbage-collected mid-animation

    def collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        if self._response_label:
            self._response_label.deleteLater()
            self._response_label = None
        self.setFixedSize(ORB_SIZE, ORB_SIZE)
        self._reset_to_top_right()
        self.set_state(IDLE)

    def show_text(self, text: str):
        if self._response_label:
            self._response_label.setPlainText(text)
