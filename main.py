"""
Dental OPG Detector
====================
Desktop application (PySide6) for running a trained YOLOv8 model on dental
panoramic X-ray (OPG) images, storing patients/cases in a local SQLite
database, letting the dentist add manual bounding-box findings on top of
the AI detections, and exporting a PDF report of the analyzed image plus
findings table and clinical notes.

Architecture
------------
app/
  config.py            static configuration (paths, palette, about info)
  data/database.py      SQLite repository (schema + CRUD only)
  services/
    case_service.py     business workflows: patients, cases, save/delete
                         (coordinates database.py with image files on disk)
    detection_service.py background QThread workers for YOLO load/inference
    report_service.py   PDF report generation (reportlab)
    export_service.py   CSV / Excel export helpers
  ui/
    main_window.py       the QMainWindow, wires widgets to services
    canvas.py             ImageCanvas (box drawing / click hit-testing)
    dialogs.py             About / Add-Finding / Edit-Finding / Patient dialogs
    widgets.py              small reusable Qt widgets
    styles.py                 the app stylesheet
  utils/helpers.py       framework-agnostic helper functions

Each layer only depends on the layers below it (ui -> services -> data),
which keeps the persistence/model/report logic independently testable and
free of Qt imports.

Run:
    pip install -r requirements.txt
    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import DentalDetectorApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Dental OPG Detector")
    window = DentalDetectorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
