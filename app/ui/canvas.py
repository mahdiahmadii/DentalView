"""
app.ui.canvas
=============
ImageCanvas: a QLabel subclass that renders the X-ray image and supports
click-and-drag box drawing, single/double click hit-testing, and
Ctrl+Wheel zoom requests. Pure UI widget — no DB/service knowledge.
"""

from PySide6.QtCore import Qt, QRect, QSize, QTimer, Signal
from PySide6.QtWidgets import QApplication, QLabel, QRubberBand


class ImageCanvas(QLabel):
    boxDrawn = Signal(float, float, float, float)  # x1,y1,x2,y2 in ORIGINAL image px
    zoomRequested = Signal(int)  # wheel delta, emitted on Ctrl+Wheel
    boxClicked = Signal(float, float)        # single click point, ORIGINAL image px
    boxDoubleClicked = Signal(float, float)  # double click point, ORIGINAL image px

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.draw_mode = False
        self.orig_size = None  # (w, h) of the original PIL image currently shown
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = None
        self._click_origin = None
        self._pending_click_point = None

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(event.angleDelta().y())
            event.accept()
        else:
            super().wheelEvent(event)

    def _widget_to_original_point(self, pos):
        """Translate a widget-space click position into ORIGINAL image
        pixel coordinates, or None if the click landed outside the image."""
        rect = self._pixmap_rect()
        pm = self.pixmap()
        if not rect or pm is None or pm.isNull() or not self.orig_size:
            return None
        if not rect.contains(pos):
            return None
        sx = self.orig_size[0] / pm.width()
        sy = self.orig_size[1] / pm.height()
        x = (pos.x() - rect.left()) * sx
        y = (pos.y() - rect.top()) * sy
        return (x, y)

    def set_original_size(self, w, h):
        self.orig_size = (w, h)

    def _pixmap_rect(self):
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return None
        lw, lh = self.width(), self.height()
        pw, ph = pm.width(), pm.height()
        x = (lw - pw) // 2
        y = (lh - ph) // 2
        return QRect(x, y, pw, ph)

    def mousePressEvent(self, event):
        if self.draw_mode and event.button() == Qt.LeftButton:
            rect = self._pixmap_rect()
            if rect and rect.contains(event.pos()):
                self._origin = event.pos()
                self._rubber_band.setGeometry(QRect(self._origin, QSize()))
                self._rubber_band.show()
                return
        if (not self.draw_mode) and event.button() == Qt.LeftButton:
            self._click_origin = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.draw_mode and self._origin is not None:
            rect = QRect(self._origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.draw_mode and self._origin is not None:
            self._rubber_band.hide()
            rect = QRect(self._origin, event.pos()).normalized()
            self._origin = None
            pm_rect = self._pixmap_rect()
            pm = self.pixmap()
            if pm_rect and self.orig_size and pm and rect.width() > 4 and rect.height() > 4:
                rect = rect.intersected(pm_rect)
                sx = self.orig_size[0] / pm.width()
                sy = self.orig_size[1] / pm.height()
                x1 = (rect.left() - pm_rect.left()) * sx
                y1 = (rect.top() - pm_rect.top()) * sy
                x2 = (rect.right() - pm_rect.left()) * sx
                y2 = (rect.bottom() - pm_rect.top()) * sy
                self.boxDrawn.emit(x1, y1, x2, y2)
            return

        if (not self.draw_mode) and event.button() == Qt.LeftButton and self._click_origin is not None:
            moved = (event.pos() - self._click_origin).manhattanLength()
            self._click_origin = None
            # Only treat this as a "click" if the mouse barely moved (not a
            # drag meant to pan/select). Delay the single-click action so a
            # following double-click can cancel it.
            if moved < 4:
                pt = self._widget_to_original_point(event.pos())
                if pt is not None:
                    self._pending_click_point = pt
                    QTimer.singleShot(
                        QApplication.instance().doubleClickInterval(),
                        lambda p=pt: self._maybe_emit_single_click(p)
                    )
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.draw_mode or event.button() != Qt.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        self._pending_click_point = None  # cancel any pending single-click
        self._click_origin = None         # prevent the trailing release from scheduling a new one
        pt = self._widget_to_original_point(event.pos())
        if pt is not None:
            self.boxDoubleClicked.emit(*pt)
        super().mouseDoubleClickEvent(event)

    def _maybe_emit_single_click(self, pt):
        if self._pending_click_point == pt:
            self._pending_click_point = None
            self.boxClicked.emit(*pt)
