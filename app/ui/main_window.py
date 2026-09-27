"""
app.ui.main_window
===================
DentalDetectorApp: the main QMainWindow. This module only orchestrates —
detection, persistence, file I/O, and PDF/Excel export all live in
app.services.*; the SQLite schema lives in app.data.database. Keeping
those concerns out of this file is what makes it possible to test the
services independently of Qt and to reuse them (e.g. from a CLI) later.
"""

import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDialog,
    QFileDialog, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QToolBar, QVBoxLayout, QWidget,
)

from PIL import Image, ImageDraw, ImageFont
import numpy as np

from app.config import DEFAULT_MODEL_PATH, PALETTE
from app.services.case_service import CaseService
from app.services.detection_service import InferenceWorker, ModelLoadWorker
from app.services.export_service import export_detections_csv, export_patients_excel
from app.services.report_service import generate_case_report
from app.utils.helpers import class_color, dashed_rectangle, sanitize_filename
from app.ui.canvas import ImageCanvas
from app.ui.dialogs import AboutDialog, AddFindingDialog, EditFindingDialog, PatientDialog
from app.ui.styles import APP_STYLESHEET
from app.ui.widgets import HoverMenuToolButton


class DentalDetectorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dental OPG Detector")
        self.resize(1440, 860)

        self.case_service = CaseService()

        self.model = None
        self.class_names = []
        self.model_path = DEFAULT_MODEL_PATH

        self.current_image_path = None
        self.original_pil_image = None
        self.rendered_image = None
        self.class_checkboxes = {}

        self._full_pixmap = None   # full-resolution QPixmap of the currently rendered image
        self._fit_scale = None     # scale factor that makes the image fit the viewport
        self.zoom_factor = 1.0     # user zoom on top of the fit scale

        self.image_added_for_current_patient = False
        self.detection_performed_for_current_image = False

        self.ai_detections_current = []   # list of dicts: class_name, confidence, x1,y1,x2,y2
        self.manual_detections = []       # list of dicts: class_name, confidence(None), x1,y1,x2,y2, note

        self.current_patient = None       # dict from CaseService.get_patient
        self.current_case_id = None       # set once the current state has been saved as a case

        self._isolated_detection = None   # ("ai"|"manual", index) of the box currently isolated, or None

        self._build_ui()
        self._apply_style()
        self._auto_load_default_model()

    # ---------------------------------------------------------- UI BUILD --
    def _build_ui(self):
        toolbar = QToolBar("Main")
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # -- Load Model
        act_load_model = QAction("Load Model", self)
        act_load_model.triggered.connect(self.on_load_model_clicked)
        toolbar.addAction(act_load_model)

        # -- Open Image
        act_open_image = QAction("Open Image", self)
        act_open_image.triggered.connect(self.on_open_image_clicked)
        toolbar.addAction(act_open_image)

        # -- Save (hover menu with sub-actions)
        save_button = HoverMenuToolButton("Save", self)
        save_menu = QMenu(save_button)

        act_save_archive = QAction("Save to Archive", self)
        act_save_archive.triggered.connect(self.on_save_case_clicked)
        save_menu.addAction(act_save_archive)

        act_generate_report = QAction("Generate Report as PDF", self)
        act_generate_report.triggered.connect(self.on_generate_report_clicked)
        save_menu.addAction(act_generate_report)

        act_export_csv = QAction("Export as CSV", self)
        act_export_csv.triggered.connect(self.on_export_csv_clicked)
        save_menu.addAction(act_export_csv)

        act_save_image = QAction("Save Image", self)
        act_save_image.triggered.connect(self.on_save_image_clicked)
        save_menu.addAction(act_save_image)

        save_button.setMenu(save_menu)
        toolbar.addWidget(save_button)

        # -- Export patients info (Excel)
        act_export_patients = QAction("Export Patients Info", self)
        act_export_patients.triggered.connect(self.on_export_patients_info_clicked)
        toolbar.addAction(act_export_patients)

        # -- Settings (placeholder, no functionality yet)
        act_settings = QAction("Settings", self)
        act_settings.triggered.connect(self.on_settings_clicked)
        toolbar.addAction(act_settings)

        # -- About us
        act_about = QAction("About Us", self)
        act_about.triggered.connect(self.on_about_clicked)
        toolbar.addAction(act_about)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # ---------------- Left panel: tabs for Detection / Patient ----------------
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setFixedWidth(330)
        left_outer_layout = QVBoxLayout(left_panel)

        self.model_status_label = QLabel("Model: not loaded")
        self.model_status_label.setWordWrap(True)
        self.model_status_label.setObjectName("statusChip")
        left_outer_layout.addWidget(self.model_status_label)

        self.tabs = QTabWidget()
        left_outer_layout.addWidget(self.tabs, stretch=1)

        self.tabs.addTab(self._build_patient_tab(), "Patient")
        self.detection_tab_index = self.tabs.addTab(self._build_detection_tab(), "Detection")
        self._update_detection_tab_availability()

        root_layout.addWidget(left_panel)

        # ---------------- Right side: image + results + findings/notes ----------------
        right_splitter = QSplitter(Qt.Vertical)

        image_panel = QWidget()
        image_panel_layout = QVBoxLayout(image_panel)
        image_panel_layout.setContentsMargins(0, 0, 0, 0)
        image_panel_layout.setSpacing(4)

        zoom_row = QHBoxLayout()
        zoom_hint = QLabel("Ctrl+Scroll or use the buttons to zoom, then use the scrollbars to pan.")
        zoom_hint.setStyleSheet("color: #9aa0ac; font-size: 11px;")
        zoom_row.addWidget(zoom_hint, stretch=1)
        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedWidth(32)
        btn_zoom_out.clicked.connect(lambda: self.on_zoom_step(-1))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(32)
        btn_zoom_in.clicked.connect(lambda: self.on_zoom_step(1))
        btn_zoom_fit = QPushButton("Fit")
        btn_zoom_fit.setFixedWidth(40)
        btn_zoom_fit.clicked.connect(self.on_zoom_fit)
        zoom_row.addWidget(btn_zoom_out)
        zoom_row.addWidget(self.zoom_label)
        zoom_row.addWidget(btn_zoom_in)
        zoom_row.addWidget(btn_zoom_fit)
        image_panel_layout.addLayout(zoom_row)

        self.image_label = ImageCanvas()
        self.image_label.setText("Open an X-ray image to begin")
        self.image_label.setMinimumHeight(380)
        self.image_label.boxDrawn.connect(self.on_manual_box_drawn)
        self.image_label.zoomRequested.connect(self.on_zoom_wheel)
        self.image_label.boxClicked.connect(self.on_image_single_click)
        self.image_label.boxDoubleClicked.connect(self.on_image_double_click)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(False)
        self.image_scroll.setAlignment(Qt.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        image_panel_layout.addWidget(self.image_scroll, stretch=1)

        right_splitter.addWidget(image_panel)

        right_splitter.addWidget(self._build_lower_panel())
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        root_layout.addWidget(right_splitter, stretch=1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def _build_detection_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self.btn_detect = QPushButton("Run Detection")
        self.btn_detect.setObjectName("primaryButton")
        self.btn_detect.setEnabled(False)
        self.btn_detect.clicked.connect(self.on_run_detection_clicked)
        layout.addWidget(self.btn_detect)

        conf_box = QGroupBox("Confidence threshold")
        conf_layout = QVBoxLayout(conf_box)
        self.conf_value_label = QLabel("25%")
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setMinimum(5)
        self.conf_slider.setMaximum(95)
        self.conf_slider.setValue(25)
        self.conf_slider.valueChanged.connect(self._redraw)
        conf_layout.addWidget(self.conf_slider)
        conf_layout.addWidget(self.conf_value_label, alignment=Qt.AlignRight)
        layout.addWidget(conf_box)

        class_box = QGroupBox("Classes to show")
        class_box_layout = QVBoxLayout(class_box)
        select_row = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        btn_all.clicked.connect(lambda: self._set_all_classes(True))
        btn_none.clicked.connect(lambda: self._set_all_classes(False))
        select_row.addWidget(btn_all)
        select_row.addWidget(btn_none)
        class_box_layout.addLayout(select_row)

        class_scroll = QScrollArea()
        class_scroll.setWidgetResizable(True)
        class_scroll.setMaximumHeight(220)
        class_list_widget = QWidget()
        self.class_list_layout = QVBoxLayout(class_list_widget)
        self.class_list_layout.setSpacing(4)
        self.class_list_layout.addStretch(1)
        class_scroll.setWidget(class_list_widget)
        class_box_layout.addWidget(class_scroll)
        layout.addWidget(class_box, stretch=1)

        return tab

    def _build_patient_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        search_box = QGroupBox("Find patient")
        sb_layout = QVBoxLayout(search_box)
        self.patient_search_edit = QLineEdit()
        self.patient_search_edit.setPlaceholderText("Search by name or code...")
        self.patient_search_edit.returnPressed.connect(self.on_search_patient)
        sb_layout.addWidget(self.patient_search_edit)
        search_row = QHBoxLayout()
        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self.on_search_patient)
        btn_new = QPushButton("New Patient")
        btn_new.clicked.connect(self.on_new_patient_clicked)
        search_row.addWidget(btn_search)
        search_row.addWidget(btn_new)
        sb_layout.addLayout(search_row)

        self.btn_add_opg = QPushButton("Add OPG Image")
        self.btn_add_opg.setObjectName("primaryButton")
        self.btn_add_opg.setEnabled(False)
        self.btn_add_opg.clicked.connect(self.on_add_opg_image_clicked)
        sb_layout.addWidget(self.btn_add_opg)

        self.patient_results_list = QListWidget()
        self.patient_results_list.setMaximumHeight(120)
        self.patient_results_list.itemClicked.connect(self.on_patient_result_selected)
        sb_layout.addWidget(self.patient_results_list)
        layout.addWidget(search_box)

        self.patient_label = QLabel("No patient selected")
        self.patient_label.setObjectName("statusChip")
        self.patient_label.setWordWrap(True)
        layout.addWidget(self.patient_label)

        history_box = QGroupBox("Case history")
        hb_layout = QVBoxLayout(history_box)
        self.case_history_list = QListWidget()
        self.case_history_list.itemDoubleClicked.connect(self.on_case_history_item_activated)
        self.case_history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.case_history_list.customContextMenuRequested.connect(self.on_case_history_context_menu)
        hb_layout.addWidget(self.case_history_list)
        hb_layout.addWidget(QLabel(
            "Double-click a case to load its image & findings. Right-click for more options."
        ))
        layout.addWidget(history_box, stretch=1)

        self.on_search_patient()  # populate with all patients initially
        return tab

    def _build_lower_panel(self):
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # ---- results table (AI)
        results_box = QFrame()
        results_layout = QVBoxLayout(results_box)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_header = QLabel("AI Detections")
        results_header.setObjectName("sectionHeader")
        results_layout.addWidget(results_header)

        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Class", "Confidence", "Box (x1,y1,x2,y2)"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        results_layout.addWidget(self.results_table)
        layout.addWidget(results_box, stretch=3)

        # ---- manual findings + notes + save/report
        right_box = QFrame()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)

        findings_header = QLabel("Dentist Findings (manual)")
        findings_header.setObjectName("sectionHeader")
        right_layout.addWidget(findings_header)

        box_hint = QLabel(
            "Double-click a box on the image to isolate it (dim the rest). "
            "Click a box to edit its class/confidence or delete it."
        )
        box_hint.setWordWrap(True)
        box_hint.setStyleSheet("color: #9aa0ac; font-size: 11px;")
        right_layout.addWidget(box_hint)

        self.btn_show_all_boxes = QPushButton("Show All Boxes")
        self.btn_show_all_boxes.clicked.connect(self.on_show_all_boxes_clicked)
        right_layout.addWidget(self.btn_show_all_boxes)

        self.btn_add_finding = QPushButton("✎  Add Manual Finding")
        self.btn_add_finding.setCheckable(True)
        self.btn_add_finding.toggled.connect(self.on_toggle_draw_mode)
        right_layout.addWidget(self.btn_add_finding)

        self.manual_list = QListWidget()
        self.manual_list.setMaximumHeight(120)
        right_layout.addWidget(self.manual_list)

        manual_btn_row = QHBoxLayout()
        btn_remove_finding = QPushButton("Remove Selected")
        btn_remove_finding.clicked.connect(self.on_remove_manual_finding)
        btn_clear_findings = QPushButton("Clear All")
        btn_clear_findings.clicked.connect(self.on_clear_manual_findings)
        manual_btn_row.addWidget(btn_remove_finding)
        manual_btn_row.addWidget(btn_clear_findings)
        right_layout.addLayout(manual_btn_row)

        notes_header = QLabel("Clinical Notes / Diagnosis Summary")
        notes_header.setObjectName("sectionHeader")
        right_layout.addWidget(notes_header)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Overall impression, recommended treatment, follow-up...")
        right_layout.addWidget(self.notes_edit, stretch=1)

        action_row = QHBoxLayout()
        btn_save_case = QPushButton("💾 Save Case to Database")
        btn_save_case.setObjectName("primaryButton")
        btn_save_case.clicked.connect(self.on_save_case_clicked)
        btn_report = QPushButton("📄 Generate PDF Report")
        btn_report.clicked.connect(self.on_generate_report_clicked)
        action_row.addWidget(btn_save_case)
        action_row.addWidget(btn_report)
        right_layout.addLayout(action_row)

        layout.addWidget(right_box, stretch=2)
        return panel

    def _apply_style(self):
        self.setStyleSheet(APP_STYLESHEET)

    # ------------------------------------------------------- MODEL LOAD --
    def _auto_load_default_model(self):
        if os.path.exists(self.model_path):
            self._load_model(self.model_path)
        else:
            self.model_status_label.setText(
                "Model: not found.\nClick 'Load Model...' to select your best.pt file."
            )

    def on_load_model_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select YOLOv8 model (.pt)", "", "PyTorch model (*.pt)"
        )
        if path:
            self._load_model(path)

    def _load_model(self, path):
        self.model_status_label.setText(f"Loading model...\n{os.path.basename(path)}")
        self.status.showMessage("Loading model, please wait...")
        self.btn_detect.setEnabled(False)
        self._model_worker = ModelLoadWorker(path)
        self._model_worker.finished_ok.connect(self._on_model_loaded)
        self._model_worker.finished_err.connect(self._on_model_load_error)
        self._model_worker.start()

    def _on_model_loaded(self, model, names):
        self.model = model
        self.class_names = names
        self.model_path = self._model_worker.model_path
        self.model_status_label.setText(
            f"Model loaded ✓\n{os.path.basename(self.model_path)}\n{len(names)} classes"
        )
        self.status.showMessage("Model loaded successfully", 4000)
        self._populate_class_filters()
        self._update_detection_button()

    def _on_model_load_error(self, error_text):
        self.model_status_label.setText("Model: failed to load")
        QMessageBox.critical(self, "Model load error", error_text)
        self.status.showMessage("Model failed to load", 5000)

    def _populate_class_filters(self):
        while self.class_list_layout.count():
            item = self.class_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.class_checkboxes = {}

        for idx, name in enumerate(self.class_names):
            r, g, b = class_color(idx)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background-color: rgb({r},{g},{b}); border-radius: 3px;")

            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self._redraw)

            row_layout.addWidget(swatch)
            row_layout.addWidget(cb, stretch=1)

            self.class_list_layout.addWidget(row)
            self.class_checkboxes[idx] = cb

    def _set_all_classes(self, checked: bool):
        for cb in self.class_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._redraw()

    def _class_index(self, name: str) -> int:
        if name in self.class_names:
            return self.class_names.index(name)
        return abs(hash(name)) % len(PALETTE)

    # ------------------------------------------------------- DETECTION STATE --
    def _update_detection_button(self):
        can_detect = (
            self.current_patient is not None
            and self.image_added_for_current_patient
            and not self.detection_performed_for_current_image
            and self.model is not None
        )
        self.btn_detect.setEnabled(can_detect)
        self._update_detection_tab_availability()

    def _update_detection_tab_availability(self):
        """The Detection tab is only usable once a patient is selected AND
        an OPG image has been added for that patient. Otherwise it is
        disabled (and switched away from) so the dentist can't jump into it
        prematurely."""
        available = (
            self.current_patient is not None
            and self.image_added_for_current_patient
        )
        self.tabs.setTabEnabled(self.detection_tab_index, available)
        if not available and self.tabs.currentIndex() == self.detection_tab_index:
            self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------- IMAGE OPEN --
    def on_add_opg_image_clicked(self):
        if self.current_patient is None:
            QMessageBox.warning(
                self,
                "No patient selected",
                "Please select or create a patient first."
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Select OPG image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"
        )
        if not path:
            return

        self.current_image_path = path
        self.original_pil_image = Image.open(path).convert("RGB")
        self.ai_detections_current = []
        self.manual_detections = []
        self.current_case_id = None
        self._isolated_detection = None
        self.detection_performed_for_current_image = False

        self.image_label.set_original_size(*self.original_pil_image.size)
        self.zoom_factor = 1.0
        self._fit_scale = None
        self._render_plain_image()
        self.results_table.setRowCount(0)
        self.manual_list.clear()

        self._update_detection_button()

        self.status.showMessage(
            f"OPG image added for {self.current_patient['full_name']}: "
            f"{os.path.basename(path)}",
            5000
        )

    def on_open_image_clicked(self):
        if self.current_patient is None:
            QMessageBox.warning(
                self,
                "No patient selected",
                "Please select a patient first, then use 'Add OPG Image'."
            )
            return

        self.on_add_opg_image_clicked()

    def _render_plain_image(self):
        self.rendered_image = self.original_pil_image
        self._display_pil_image(self.original_pil_image)

    # ------------------------------------------------------- DETECTION --
    def on_run_detection_clicked(self):
        if self.current_patient is None:
            QMessageBox.warning(
                self,
                "No patient selected",
                "Please select a patient first."
            )
            return

        if not self.image_added_for_current_patient:
            QMessageBox.warning(
                self,
                "No OPG image",
                "Please add an OPG image for the selected patient first."
            )
            return

        if self.detection_performed_for_current_image:
            QMessageBox.information(
                self,
                "Detection already performed",
                "Detection has already been performed for this OPG image."
            )
            return

        if self.model is None:
            QMessageBox.warning(self, "No model", "Please load a model first.")
            return

        if self.current_image_path is None:
            QMessageBox.warning(
                self,
                "No image",
                "Please add an OPG image first."
            )
            return

        self.btn_detect.setEnabled(False)
        self.status.showMessage("Running detection...")
        self._inference_worker = InferenceWorker(
            self.model, self.current_image_path
        )
        self._inference_worker.finished_ok.connect(self._on_detection_done)
        self._inference_worker.finished_err.connect(self._on_detection_error)
        self._inference_worker.start()

    def _on_detection_done(self, result, elapsed):
        self.ai_detections_current = []
        self._isolated_detection = None
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                cls_id = int(box.cls.item())
                conf = float(box.conf.item())
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                name = self.class_names[cls_id] if cls_id < len(self.class_names) else str(cls_id)
                self.ai_detections_current.append({
                    "class_name": name, "confidence": conf,
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                })
        self.current_case_id = None  # this is a fresh, unsaved analysis
        self.detection_performed_for_current_image = True
        self._update_detection_button()
        self.status.showMessage(f"Detection finished in {elapsed:.2f}s", 5000)
        self._redraw()

    def _on_detection_error(self, error_text):
        self.btn_detect.setEnabled(True)
        QMessageBox.critical(self, "Detection error", error_text)
        self.status.showMessage("Detection failed", 5000)

    # ------------------------------------------------------- MANUAL BOXES
    def on_toggle_draw_mode(self, checked):
        self.image_label.draw_mode = checked
        self.btn_add_finding.setText(
            "✎  Click & drag on the image (click again to stop)" if checked else "✎  Add Manual Finding"
        )
        self.image_label.setCursor(QCursor(Qt.CrossCursor) if checked else QCursor(Qt.ArrowCursor))

    def on_manual_box_drawn(self, x1, y1, x2, y2):
        if self.model is not None:
            names = self.class_names
        else:
            names = []
        dlg = AddFindingDialog(names, self)
        if dlg.exec() == QDialog.Accepted:
            class_name, note = dlg.get_data()
            if class_name.strip():
                self.manual_detections.append({
                    "class_name": class_name.strip(), "confidence": None,
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "note": note.strip() or None,
                })
                self._redraw()

    def on_remove_manual_finding(self):
        item = self.manual_list.currentItem()
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        del self.manual_detections[idx]
        self._isolated_detection = None
        self._redraw()

    def on_clear_manual_findings(self):
        if not self.manual_detections:
            return
        self.manual_detections = []
        self._isolated_detection = None
        self._redraw()

    def _refresh_manual_findings_list(self):
        self.manual_list.clear()
        for i, d in enumerate(self.manual_detections):
            note = f" — {d['note']}" if d.get("note") else ""
            box = f"[{round(d['x1'])},{round(d['y1'])},{round(d['x2'])},{round(d['y2'])}]"
            item = QListWidgetItem(f"{d['class_name']}{note}  {box}")
            item.setData(Qt.UserRole, i)
            self.manual_list.addItem(item)

    # ------------------------------------------------------- REDRAW/FILTER
    def _redraw(self, *_):
        conf_threshold = self.conf_slider.value() / 100.0
        self.conf_value_label.setText(f"{self.conf_slider.value()}%")

        if self.original_pil_image is None:
            return

        selected_names = {
            name for idx, name in enumerate(self.class_names)
            if idx in self.class_checkboxes and self.class_checkboxes[idx].isChecked()
        }

        base = self.original_pil_image.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        DIM_ALPHA = 55
        FULL_ALPHA = 255

        ai_rows = []
        for i, d in enumerate(self.ai_detections_current):
            if d["confidence"] < conf_threshold:
                continue
            if self.class_names and d["class_name"] in self.class_names and d["class_name"] not in selected_names:
                continue
            is_dimmed = self._isolated_detection is not None and self._isolated_detection != ("ai", i)
            alpha = DIM_ALPHA if is_dimmed else FULL_ALPHA
            color = class_color(self._class_index(d["class_name"]))
            self._draw_solid_box(draw, d, color, font, alpha=alpha)
            ai_rows.append((
                d["class_name"], d["confidence"],
                (round(d["x1"]), round(d["y1"]), round(d["x2"]), round(d["y2"]))
            ))

        for i, d in enumerate(self.manual_detections):
            is_dimmed = self._isolated_detection is not None and self._isolated_detection != ("manual", i)
            alpha = DIM_ALPHA if is_dimmed else FULL_ALPHA
            color = class_color(self._class_index(d["class_name"]))
            self._draw_dashed_box(draw, d, color, font, alpha=alpha)

        composited = Image.alpha_composite(base, overlay).convert("RGB")
        self.rendered_image = composited
        self._display_pil_image(composited)
        self._populate_results_table(ai_rows)
        self._refresh_manual_findings_list()

    def _draw_solid_box(self, draw, d, color, font, alpha=255):
        x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
        rgba = (*color, alpha)
        label = f"{d['class_name']} {d['confidence']:.2f}"
        draw.rectangle([x1, y1, x2, y2], outline=rgba, width=3)
        text_bbox = draw.textbbox((x1, y1), label, font=font)
        th = text_bbox[3] - text_bbox[1]
        draw.rectangle(
            [x1, max(0, y1 - th - 6), x1 + (text_bbox[2] - text_bbox[0]) + 8, y1], fill=rgba
        )
        draw.text((x1 + 4, max(0, y1 - th - 4)), label, fill=(255, 255, 255, alpha), font=font)

    def _draw_dashed_box(self, draw, d, color, font, alpha=255):
        x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
        rgba = (*color, alpha)
        dashed_rectangle(draw, (x1, y1, x2, y2), rgba, width=3)
        label = f"Dr: {d['class_name']}"
        text_bbox = draw.textbbox((x1, y1), label, font=font)
        th = text_bbox[3] - text_bbox[1]
        draw.rectangle(
            [x1, max(0, y1 - th - 6), x1 + (text_bbox[2] - text_bbox[0]) + 8, y1], fill=(20, 20, 20, alpha)
        )
        draw.text((x1 + 4, max(0, y1 - th - 4)), label, fill=rgba, font=font)

    # ------------------------------------------------------- BOX SELECTION (isolate / edit / delete)
    def _hit_test_detection(self, x, y):
        """Return ('ai'|'manual', index) for the smallest currently-visible
        box containing point (x, y) in ORIGINAL image pixel coords, or None
        if no box is there. Only boxes passing the current confidence/class
        filters are considered clickable, matching what's drawn."""
        conf_threshold = self.conf_slider.value() / 100.0
        selected_names = {
            name for idx, name in enumerate(self.class_names)
            if idx in self.class_checkboxes and self.class_checkboxes[idx].isChecked()
        }

        candidates = []
        for i, d in enumerate(self.ai_detections_current):
            if d["confidence"] < conf_threshold:
                continue
            if self.class_names and d["class_name"] in self.class_names and d["class_name"] not in selected_names:
                continue
            if d["x1"] <= x <= d["x2"] and d["y1"] <= y <= d["y2"]:
                area = max(1.0, (d["x2"] - d["x1"]) * (d["y2"] - d["y1"]))
                candidates.append((area, "ai", i))

        for i, d in enumerate(self.manual_detections):
            if d["x1"] <= x <= d["x2"] and d["y1"] <= y <= d["y2"]:
                area = max(1.0, (d["x2"] - d["x1"]) * (d["y2"] - d["y1"]))
                candidates.append((area, "manual", i))

        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0])  # smallest/most specific box wins when overlapping
        _, source, idx = candidates[0]
        return (source, idx)

    def on_image_double_click(self, x, y):
        if self.original_pil_image is None or self.image_label.draw_mode:
            return
        hit = self._hit_test_detection(x, y)
        if hit is None:
            if self._isolated_detection is not None:
                self._isolated_detection = None
                self._redraw()
                self.status.showMessage("Showing all findings", 3000)
            return
        if self._isolated_detection == hit:
            self._isolated_detection = None
            self.status.showMessage("Showing all findings", 3000)
        else:
            self._isolated_detection = hit
            source, idx = hit
            d = self.ai_detections_current[idx] if source == "ai" else self.manual_detections[idx]
            self.status.showMessage(
                f"Isolated: {d['class_name']} — double-click it again (or 'Show All Boxes') to reset", 4000
            )
        self._redraw()

    def on_show_all_boxes_clicked(self):
        if self._isolated_detection is not None:
            self._isolated_detection = None
            self._redraw()
        self.status.showMessage("Showing all findings", 3000)

    def on_image_single_click(self, x, y):
        if self.original_pil_image is None or self.image_label.draw_mode:
            return
        hit = self._hit_test_detection(x, y)
        if hit is None:
            return
        source, idx = hit
        self._open_edit_dialog(source, idx)

    def _open_edit_dialog(self, source, idx):
        detections = self.ai_detections_current if source == "ai" else self.manual_detections
        if idx >= len(detections):
            return
        d = detections[idx]

        dlg = EditFindingDialog(self.class_names, d, source, self)
        if dlg.exec() != QDialog.Accepted:
            return

        if dlg.delete_requested:
            del detections[idx]
            self._isolated_detection = None  # indices may have shifted; drop isolation to stay safe
            self.status.showMessage("Finding deleted", 3000)
        else:
            class_name, confidence, note = dlg.get_data()
            if not class_name:
                QMessageBox.warning(self, "Missing class", "Class name cannot be empty.")
                return
            d["class_name"] = class_name
            if source == "ai" and confidence is not None:
                d["confidence"] = confidence
            if source == "manual":
                d["note"] = note
            self.status.showMessage("Finding updated", 3000)

        self._redraw()

    def _populate_results_table(self, rows):
        HIGH_CONF_THRESHOLD = 0.6
        HIGH_CONF_COLOR = QColor("#ffe066")  # yellow

        self.results_table.setRowCount(len(rows))
        for i, (name, conf, box) in enumerate(rows):
            item_name = QTableWidgetItem(name)
            item_conf = QTableWidgetItem(f"{conf * 100:.1f}%")
            item_box = QTableWidgetItem(str(box))

            if conf > HIGH_CONF_THRESHOLD:
                item_name.setBackground(HIGH_CONF_COLOR)
                item_conf.setBackground(HIGH_CONF_COLOR)
                item_box.setBackground(HIGH_CONF_COLOR)
                item_name.setForeground(QColor("#000000"))
                item_conf.setForeground(QColor("#000000"))
                item_box.setForeground(QColor("#000000"))

            self.results_table.setItem(i, 0, item_name)
            self.results_table.setItem(i, 1, item_conf)
            self.results_table.setItem(i, 2, item_box)

    # ------------------------------------------------------- DISPLAY / ZOOM ------
    def _display_pil_image(self, pil_img: Image.Image, reset_fit=True):
        arr = np.array(pil_img.convert("RGB"))
        h, w, ch = arr.shape
        qimg = QImage(arr.data, w, h, ch * w, QImage.Format_RGB888).copy()
        self._full_pixmap = QPixmap.fromImage(qimg)
        self.image_label.set_original_size(w, h)
        self._current_pixmap_source = arr  # keep a ref alive
        self._apply_zoom(reset_fit=reset_fit)

    def _apply_zoom(self, reset_fit=False):
        if self._full_pixmap is None or self._full_pixmap.isNull():
            return
        pw, ph = self._full_pixmap.width(), self._full_pixmap.height()
        if reset_fit or self._fit_scale is None:
            viewport = self.image_scroll.viewport().size()
            if pw and ph and viewport.width() > 0 and viewport.height() > 0:
                self._fit_scale = min(viewport.width() / pw, viewport.height() / ph, 1.0) or 1.0
            else:
                self._fit_scale = 1.0

        scale = self._fit_scale * self.zoom_factor
        target_w = max(1, int(pw * scale))
        target_h = max(1, int(ph * scale))
        scaled = self._full_pixmap.scaled(
            target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"{int(round(self.zoom_factor * 100))}%")

    def on_zoom_step(self, direction):
        """direction: +1 to zoom in, -1 to zoom out."""
        if self._full_pixmap is None:
            return
        factor = 1.2 if direction > 0 else 1 / 1.2
        self.zoom_factor = max(0.2, min(6.0, self.zoom_factor * factor))
        self._apply_zoom()

    def on_zoom_wheel(self, delta):
        self.on_zoom_step(1 if delta > 0 else -1)

    def on_zoom_fit(self):
        self.zoom_factor = 1.0
        self._apply_zoom(reset_fit=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recompute the "fit" baseline on resize, but keep the user's
        # relative zoom level applied on top of it.
        if self._full_pixmap is not None:
            self._fit_scale = None
            self._apply_zoom(reset_fit=True)

    # ------------------------------------------------------- SAVE / EXPORT
    def on_save_image_clicked(self):
        img = self.rendered_image or self.original_pil_image
        if img is None:
            QMessageBox.information(self, "Nothing to save", "Open an image and run detection first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save result image", "detection_result.png", "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        if path:
            img.save(path)
            self.status.showMessage(f"Saved image to {path}", 4000)

    def on_export_csv_clicked(self):
        if self.results_table.rowCount() == 0:
            QMessageBox.information(self, "Nothing to export", "Run detection first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export detections", "detections.csv", "CSV File (*.csv)"
        )
        if not path:
            return
        rows = [
            (
                self.results_table.item(row, 0).text(),
                self.results_table.item(row, 1).text(),
                self.results_table.item(row, 2).text(),
            )
            for row in range(self.results_table.rowCount())
        ]
        export_detections_csv(path, rows)
        self.status.showMessage(f"Exported CSV to {path}", 4000)

    # ------------------------------------------------------- EXPORT PATIENTS
    def on_export_patients_info_clicked(self):
        patients = self.case_service.search_patients("")
        if not patients:
            QMessageBox.information(self, "No patients", "There are no patients to export yet.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export patients info", "patients_info.xlsx", "Excel File (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        self.status.showMessage("Exporting patients info...")

        problem_counts = {p["id"]: self.case_service.count_patient_problems(p["id"]) for p in patients}

        try:
            export_patients_excel(path, patients, problem_counts)
        except ImportError:
            QMessageBox.critical(
                self, "Missing dependency",
                "This feature needs the 'openpyxl' package.\n\n"
                "Install it with:\n    pip install openpyxl"
            )
            self.status.showMessage("Export failed: missing dependency", 5000)
            return
        except Exception as e:
            QMessageBox.critical(self, "Export error", f"Could not save Excel file:\n{e}")
            self.status.showMessage("Export failed", 5000)
            return

        self.status.showMessage(f"Exported patients info to {path}", 5000)
        QMessageBox.information(self, "Export complete", f"Patients info exported to:\n{path}")

    # ------------------------------------------------------- TOOLBAR EXTRAS
    def on_settings_clicked(self):
        # Placeholder: no functionality yet. Wire this up later.
        self.status.showMessage("Settings: coming soon", 3000)

    def on_about_clicked(self):
        dlg = AboutDialog(self)
        dlg.exec()

    # ------------------------------------------------------- PATIENTS -----
    def on_search_patient(self):
        text = self.patient_search_edit.text() if hasattr(self, "patient_search_edit") else ""
        results = self.case_service.search_patients(text)
        self.patient_results_list.clear()
        for p in results:
            code = f"  [{p['patient_code']}]" if p.get("patient_code") else ""
            item = QListWidgetItem(f"{p['full_name']}{code}")
            item.setData(Qt.UserRole, p["id"])
            self.patient_results_list.addItem(item)

    def on_patient_result_selected(self, item):
        patient_id = item.data(Qt.UserRole)
        self.current_patient = self.case_service.get_patient(patient_id)
        self.current_case_id = None
        self.patient_label.setText(f"Selected patient: {self.current_patient['full_name']}")

        self.btn_add_opg.setEnabled(True)
        self.image_added_for_current_patient = False
        self.detection_performed_for_current_image = False
        self._update_detection_button()

        self._refresh_case_history()

    def on_new_patient_clicked(self):
        dlg = PatientDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["full_name"]:
                QMessageBox.warning(self, "Missing name", "Full name is required.")
                return
            try:
                self.current_patient = self.case_service.create_patient(**data)
            except Exception as e:
                QMessageBox.critical(self, "Could not save patient",
                                      f"{e}\n(Patient code must be unique.)")
                return
            self.current_case_id = None
            self.patient_label.setText(f"Selected patient: {self.current_patient['full_name']}")

            self.btn_add_opg.setEnabled(True)
            self.image_added_for_current_patient = False
            self.detection_performed_for_current_image = False
            self._update_detection_button()

            self.status.showMessage("New patient created and selected", 4000)
            self._refresh_case_history()
            self.on_search_patient()

    # ------------------------------------------------------- CASE HISTORY -
    def _refresh_case_history(self):
        self.case_history_list.clear()
        if self.current_patient is None:
            return
        cases = self.case_service.get_cases_for_patient(self.current_patient["id"])
        for c in cases:
            label = c["case_label"] or "(untitled)"
            item = QListWidgetItem(f"{c['created_at']}   —   {label}")
            item.setData(Qt.UserRole, c["id"])
            self.case_history_list.addItem(item)

    def on_case_history_item_activated(self, item):
        case_id = item.data(Qt.UserRole)
        case = self.case_service.get_case(case_id)
        if case is None:
            return
        original_abs = self.case_service.resolve_case_image_path(case)
        if not original_abs.exists():
            QMessageBox.warning(self, "Missing file", f"Original image not found on disk:\n{original_abs}")
            return

        self.current_image_path = str(original_abs)
        self.original_pil_image = Image.open(original_abs).convert("RGB")
        self.image_label.set_original_size(*self.original_pil_image.size)
        self.zoom_factor = 1.0
        self._fit_scale = None
        self.current_case_id = case_id
        self._isolated_detection = None

        ai_rows = self.case_service.get_detections(case_id, source="ai")
        dr_rows = self.case_service.get_detections(case_id, source="dentist")
        self.ai_detections_current = [
            {"class_name": r["class_name"], "confidence": r["confidence"],
             "x1": r["x1"], "y1": r["y1"], "x2": r["x2"], "y2": r["y2"]}
            for r in ai_rows
        ]

        self.image_added_for_current_patient = True
        self.detection_performed_for_current_image = bool(ai_rows)

        self.manual_detections = [
            {"class_name": r["class_name"], "confidence": None,
             "x1": r["x1"], "y1": r["y1"], "x2": r["x2"], "y2": r["y2"], "note": r["note"]}
            for r in dr_rows
        ]
        self.notes_edit.setPlainText(case.get("dentist_summary") or "")
        if case.get("conf_threshold") is not None:
            self.conf_slider.blockSignals(True)
            self.conf_slider.setValue(max(5, min(95, int(round(case["conf_threshold"] * 100)))))
            self.conf_slider.blockSignals(False)
        self._update_detection_button()
        self._redraw()
        self.status.showMessage(f"Loaded case: {case['case_label']}", 4000)

    def on_case_history_context_menu(self, pos):
        item = self.case_history_list.itemAt(pos)
        if item is None:
            return
        case_id = item.data(Qt.UserRole)

        menu = QMenu(self)
        delete_action = menu.addAction("🗑  Delete Case")
        chosen = menu.exec(self.case_history_list.mapToGlobal(pos))
        if chosen == delete_action:
            self._delete_case(case_id)

    def _delete_case(self, case_id):
        case = self.case_service.get_case(case_id)
        if case is None:
            return
        label = case.get("case_label") or "(untitled)"
        reply = QMessageBox.question(
            self,
            "Delete case",
            f"Delete the case \"{label}\" from {case['created_at']}?\n\n"
            "This permanently removes the case, its AI/dentist findings, "
            "and its image files. This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.case_service.delete_case(case_id)

        # If the case currently loaded in the workspace was the one deleted,
        # reset the working view so it doesn't reference a case that's gone.
        if self.current_case_id == case_id:
            self.current_case_id = None
            self.current_image_path = None
            self.original_pil_image = None
            self.rendered_image = None
            self.ai_detections_current = []
            self.manual_detections = []
            self._isolated_detection = None
            self.image_added_for_current_patient = False
            self.detection_performed_for_current_image = False
            self._full_pixmap = None
            self.image_label.clear()
            self.image_label.setText("Open an X-ray image to begin")
            self.results_table.setRowCount(0)
            self.manual_list.clear()
            self.notes_edit.clear()
            self._update_detection_button()

        self._refresh_case_history()
        self.status.showMessage(f"Case #{case_id} deleted", 4000)

    # ------------------------------------------------------- SAVE CASE ----
    def on_save_case_clicked(self):
        """Persist the current image(s) + AI/dentist detections as a case,
        via CaseService (which handles copying files under dental_data/).
        Returns the new case id, or None if the save was cancelled/failed."""
        if self.current_patient is None:
            QMessageBox.warning(self, "No patient selected",
                                 "Please select or create a patient first (Patient tab).")
            return None
        if self.original_pil_image is None or self.current_image_path is None:
            QMessageBox.warning(self, "No image", "Please open and analyze an image first.")
            return None

        default_label = f"OPG {datetime.now().strftime('%Y-%m-%d')}"
        label, ok = QInputDialog.getText(self, "Case label", "Label for this case/visit:",
                                          text=default_label)
        if not ok:
            return None

        try:
            case_id = self.case_service.save_case(
                patient=self.current_patient,
                source_image_path=self.current_image_path,
                rendered_image=self.rendered_image,
                original_pil_image=self.original_pil_image,
                case_label=label,
                model_name=os.path.basename(self.model_path) if self.model_path else None,
                conf_threshold=self.conf_slider.value() / 100.0,
                dentist_summary=self.notes_edit.toPlainText().strip(),
                ai_detections=self.ai_detections_current,
                manual_detections=self.manual_detections,
            )
        except Exception as e:
            QMessageBox.critical(self, "File save error", f"Could not save case files:\n{e}")
            return None

        self.current_case_id = case_id
        self.status.showMessage(f"Case #{case_id} saved for {self.current_patient['full_name']}", 5000)
        self._refresh_case_history()
        return case_id

    # ------------------------------------------------------- PDF REPORT ---
    def on_generate_report_clicked(self):
        if self.current_patient is None:
            QMessageBox.warning(self, "No patient selected",
                                 "Please select or create a patient first (Patient tab).")
            return
        if self.original_pil_image is None:
            QMessageBox.warning(self, "No image", "Please open and analyze an image first.")
            return

        # A report always reflects a saved case snapshot, so save (or re-save) first.
        case_id = self.on_save_case_clicked()
        if case_id is None:
            return

        case = self.case_service.get_case(case_id)
        patient = self.case_service.get_patient(case["patient_id"])
        ai_dets = self.case_service.get_detections(case_id, source="ai")
        dr_dets = self.case_service.get_detections(case_id, source="dentist")

        default_name = f"{sanitize_filename(patient['full_name'])}_{sanitize_filename(case['case_label'] or 'report')}.pdf"
        out_path, _ = QFileDialog.getSaveFileName(self, "Save PDF report", default_name, "PDF File (*.pdf)")
        if not out_path:
            return

        annotated_abs = self.case_service.resolve_case_annotated_path(case)
        try:
            generate_case_report(
                output_path=out_path,
                patient=patient,
                case=case,
                annotated_image_path=str(annotated_abs),
                ai_detections=ai_dets,
                dentist_detections=dr_dets,
                dentist_summary=case.get("dentist_summary", ""),
            )
        except Exception as e:
            QMessageBox.critical(self, "Report error", f"Failed to generate report:\n{e}\n\n{traceback.format_exc()}")
            return

        self.status.showMessage(f"Report saved to {out_path}", 5000)
        QMessageBox.information(self, "Report generated", f"PDF report saved to:\n{out_path}")

    # ------------------------------------------------------- CLEANUP ------
    def closeEvent(self, event):
        try:
            self.case_service.close()
        except Exception:
            pass
        super().closeEvent(event)
