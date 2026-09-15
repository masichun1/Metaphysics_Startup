"""Transparent always-on-top pet window with drag/click interaction."""
import random
import time

from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QPixmap, QPainter, QAction
from PySide6.QtWidgets import QWidget, QApplication, QMenu

from pet.animation import breath_scale, sway_angle, BlinkScheduler

FRAME_INTERVAL_MS = 30
DRAG_THRESHOLD = 5
MARGIN_RATIO = 1.08  # window is 8% larger than the sprite to fit breath/sway


class PetWindow(QWidget):
    def __init__(self, open_path, closed_path, height=300):
        super().__init__()
        self._open = QPixmap(open_path)
        self._closed = QPixmap(closed_path)
        self._start = time.monotonic()
        self._blink = BlinkScheduler()
        self._reaction = None       # (kind, start_time) or None
        self._press_pos = None
        self._dragging = False

        self._setup_window()
        self._setup_menu()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(FRAME_INTERVAL_MS)

    # --- window ---
    def _setup_window(self):
        w = int(self._open.width() * MARGIN_RATIO)
        h = int(self._open.height() * MARGIN_RATIO)
        self.resize(w, h)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - w - 40, screen.bottom() - h - 40)

    def _setup_menu(self):
        self._menu = QMenu(self)
        self._top_action = QAction("置顶", self, checkable=True)
        self._top_action.setChecked(True)
        self._top_action.toggled.connect(self._on_toggle_top)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        self._menu.addAction(self._top_action)
        self._menu.addAction(quit_action)

    def _on_toggle_top(self, checked):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()

    # --- animation state ---
    def _now(self):
        return time.monotonic() - self._start

    def _current_scale(self):
        now = self._now()
        s = breath_scale(now)
        if self._reaction and self._reaction[0] == "startle":
            dt = now - self._reaction[1]
            if dt < 0.3:
                p = dt / 0.3
                s += 0.06 * (1 - abs(2 * p - 1))
        return s

    def _current_angle(self):
        now = self._now()
        a = sway_angle(now)
        if self._reaction and self._reaction[0] == "shake":
            dt = now - self._reaction[1]
            if dt < 0.4:
                direction = 1 if int(dt / 0.1) % 2 == 0 else -1
                a += 4.0 * (1 - dt / 0.4) * direction
        return a

    def _is_blinking(self):
        return self._blink.tick(self._now())

    # --- render ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        pix = self._closed if self._is_blinking() else self._open
        scale = self._current_scale()
        angle = self._current_angle()
        center = QPoint(self.width() // 2, self.height() // 2)
        painter.translate(center)
        painter.rotate(angle)
        painter.scale(scale, scale)
        target = QRectF(-pix.width() / 2, -pix.height() / 2, pix.width(), pix.height())
        painter.drawPixmap(target, pix, QRectF(pix.rect()))

    # --- interaction ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._dragging = False
        elif event.button() == Qt.RightButton:
            self._menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return
        delta = event.globalPosition().toPoint() - self._press_pos
        if not self._dragging and (abs(delta.x()) + abs(delta.y())) > DRAG_THRESHOLD:
            self._dragging = True
        if self._dragging:
            self.move(self.pos() + delta)
            self._press_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._dragging:
            self._trigger_reaction()
        self._press_pos = None
        self._dragging = False

    def _trigger_reaction(self):
        kind = random.choice(["blink", "startle", "shake"])
        now = self._now()
        if kind == "blink":
            self._blink.force_blink(now)
        else:
            self._reaction = (kind, now)
