# PAIO-Omni · orb_visuals.py  v3.2
"""
Everything about how the orb actually LOOKS lives here, and only here.
bubble.py handles the mechanics (dragging, click-vs-drag, expand/collapse,
state tracking, the QTimer driving `phase` forward) and calls these four
functions to draw whatever the current state is — this file has zero
say over behavior, only pixels.

Right now all four states draw the same plain black circle — deliberately
minimal, a clean hook point rather than a design already baked in. Edit
these however you want; bubble.py doesn't care what's inside them as
long as each function draws into the given QPainter within the given rect.

Signature contract (bubble.py calls these every repaint):
    idle(painter, rect, phase)
    listening(painter, rect, phase, ripple)
    thinking(painter, rect, phase)
    making(painter, rect, phase)

  painter  - a QPainter already set up (antialiasing on) for this widget
  rect     - a QRectF, the area to draw into
  phase    - float 0..1, loops continuously — drive any animation off this
  ripple   - float 0..1, LISTENING only — resets to 0 each time listening starts
"""

from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt


def _plain_black_circle(painter, rect):
    painter.setBrush(QBrush(QColor(0, 0, 0)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(rect)


def idle(painter, rect, phase):
    _plain_black_circle(painter, rect)


def listening(painter, rect, phase, ripple):
    _plain_black_circle(painter, rect)


def thinking(painter, rect, phase):
    _plain_black_circle(painter, rect)


def making(painter, rect, phase):
    _plain_black_circle(painter, rect)
