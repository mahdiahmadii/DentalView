"""
app.ui.styles
=============
The application's Qt stylesheet, kept out of main_window.py so visual
tweaks don't require touching business/UI-wiring code.
"""

APP_STYLESHEET = """
    QMainWindow { background-color: #1e2129; }
    QWidget { color: #e8e8ec; font-size: 13px; }
    #leftPanel { background-color: #262a35; border-radius: 8px; padding: 10px; }
    #statusChip { background-color: #2f3542; padding: 8px; border-radius: 6px; }
    #sectionHeader { font-weight: 600; font-size: 14px; padding: 4px 0; color: #000000; }
    QGroupBox { border: 1px solid #3a3f4b; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px;color: #000000; }
    QPushButton { background-color: #3a3f4b; border: none; padding: 8px; border-radius: 6px; }
    QPushButton:hover { background-color: #454b59; }
    QPushButton:disabled { color: #777; }
    QPushButton:checked { background-color: #b0563d; }
    #primaryButton { background-color: #4f7cff; font-weight: 600; }
    #primaryButton:hover { background-color: #6389ff; }
    QTableWidget, QListWidget { background-color: #14161c; gridline-color: #2c2f38; border-radius: 6px; }
    QHeaderView::section { background-color: #262a35; padding: 6px; border: none; }
    QScrollArea { border: none; }
    QTextEdit, QLineEdit, QComboBox, QDateEdit { background-color: #14161c; border: 1px solid #3a3f4b; border-radius: 5px; padding: 5px; color: #e8e8ec; }
    QSlider::groove:horizontal { height: 6px; background: #3a3f4b; border-radius: 3px; }
    QSlider::handle:horizontal { background: #4f7cff; width: 16px; margin: -6px 0; border-radius: 8px; }
    QTabBar::tab { background: #2f3542; padding: 6px 12px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
    QTabBar::tab:selected { background: #4f7cff; }
    QLabel { color: #000000;}
    QComboBox QAbstractItemView { color: #000000; background-color: #ffffff;selection-color: #ffffff; selection-background-color: #4f7cff;}
    QCalendarWidget {color: #000000; background-color: #ffffff;}
    QCalendarWidget QAbstractItemView {color: #000000; background-color: #ffffff; selection-color: #ffffff; selection-background-color: #4f7cff;}
    QCheckBox {color: #000000;}
"""
