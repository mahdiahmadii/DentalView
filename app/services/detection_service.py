"""
app.services.detection_service
===============================
Background workers that keep the GUI thread responsive while the YOLO
model is loaded or run. UI code only talks to these two QThread
subclasses through their finished_ok / finished_err signals — no direct
ultralytics/YOLO usage should live in the UI layer.
"""

import time
import traceback

from PySide6.QtCore import QThread, Signal


class ModelLoadWorker(QThread):
    finished_ok = Signal(object, list)
    finished_err = Signal(str)

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path

    def run(self):
        try:
            from ultralytics import YOLO
            model = YOLO(self.model_path)
            names = [model.names[i] for i in range(len(model.names))]
            self.finished_ok.emit(model, names)
        except Exception as e:
            self.finished_err.emit(f"{e}\n\n{traceback.format_exc()}")


class InferenceWorker(QThread):
    finished_ok = Signal(object, float)
    finished_err = Signal(str)

    def __init__(self, model, image_path):
        super().__init__()
        self.model = model
        self.image_path = image_path

    def run(self):
        try:
            t0 = time.time()
            results = self.model.predict(
                source=self.image_path, conf=0.05, iou=0.5, verbose=False
            )
            elapsed = time.time() - t0
            self.finished_ok.emit(results[0], elapsed)
        except Exception as e:
            self.finished_err.emit(f"{e}\n\n{traceback.format_exc()}")
