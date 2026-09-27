"""
app.ui.widgets
===============
Small, generic Qt widgets with no business logic — reusable building
blocks for main_window.py.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QToolButton


class HoverMenuToolButton(QToolButton):
    """QToolButton that pops its attached menu up on mouse hover (in addition
    to the normal click behaviour)."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)

    def enterEvent(self, event):
        menu = self.menu()
        if menu is not None:
            pos = self.mapToGlobal(QPoint(0, self.height()))
            menu.popup(pos)
        super().enterEvent(event)
