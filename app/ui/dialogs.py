"""
app.ui.dialogs
===============
Modal QDialog subclasses used by the main window: About, add/edit a
finding (bounding box), and create/edit a patient.
"""

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
)

from app.config import AUTHOR_GITHUB_URL, AUTHOR_LINKEDIN_URL, AUTHOR_NAME


class AboutDialog(QDialog):
    """Simple 'About us' dialog with author info and links."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("درباره ما")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        title = QLabel("Dental OPG Detector")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        body = QLabel(
            f"این پروژه توسط <b>{AUTHOR_NAME}</b> نوشته شده است.<br>"
            "این نرم‌افزار برای تحلیل تصاویر پانورامیک دندان (OPG) با استفاده از "
            "مدل یادگیری عمیق YOLOv8 و ثبت بیماران، موارد و یافته‌های بالینی طراحی شده است."
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        layout.addWidget(body)

        links = QLabel(
            f'GitHub: <a href="{AUTHOR_GITHUB_URL}">{AUTHOR_GITHUB_URL}</a><br>'
            f'LinkedIn: <a href="{AUTHOR_LINKEDIN_URL}">{AUTHOR_LINKEDIN_URL}</a>'
        )
        links.setTextFormat(Qt.RichText)
        links.setOpenExternalLinks(True)
        links.setWordWrap(True)
        layout.addWidget(links)

        close_btn = QPushButton("بستن")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class AddFindingDialog(QDialog):
    """Prompt the dentist for the class/label + optional note of a manually
    drawn bounding box."""

    def __init__(self, class_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Dentist Finding")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Finding / class:"))
        self.class_combo = QComboBox()
        self.class_combo.setEditable(True)
        self.class_combo.addItems(class_names)
        self.class_combo.setCurrentText("")
        layout.addWidget(self.class_combo)

        layout.addWidget(QLabel("Note (optional):"))
        self.note_edit = QLineEdit()
        layout.addWidget(self.note_edit)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Add Finding")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def get_data(self):
        return self.class_combo.currentText(), self.note_edit.text()


class EditFindingDialog(QDialog):
    """Edit an existing finding (AI detection or dentist box): change its
    class, and either its confidence (AI) or its note (dentist) — or delete
    it entirely."""

    def __init__(self, class_names, detection, source, parent=None):
        super().__init__(parent)
        self.source = source
        self.delete_requested = False
        self.setWindowTitle("Edit AI Detection" if source == "ai" else "Edit Dentist Finding")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Finding / class:"))
        self.class_combo = QComboBox()
        self.class_combo.setEditable(True)
        self.class_combo.addItems(class_names)
        self.class_combo.setCurrentText(detection.get("class_name", ""))
        layout.addWidget(self.class_combo)

        self.confidence_spin = None
        self.note_edit = None

        if source == "ai":
            layout.addWidget(QLabel("Confidence (%) — doctor override:"))
            self.confidence_spin = QSpinBox()
            self.confidence_spin.setRange(1, 100)
            self.confidence_spin.setValue(
                max(1, min(100, int(round((detection.get("confidence") or 0) * 100))))
            )
            layout.addWidget(self.confidence_spin)
        else:
            layout.addWidget(QLabel("Note (optional):"))
            self.note_edit = QLineEdit()
            self.note_edit.setText(detection.get("note") or "")
            layout.addWidget(self.note_edit)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Save Changes")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        delete_btn = QPushButton("🗑 Delete")
        delete_btn.clicked.connect(self._on_delete)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_delete(self):
        self.delete_requested = True
        self.accept()

    def get_data(self):
        class_name = self.class_combo.currentText().strip()
        confidence = self.confidence_spin.value() / 100.0 if self.confidence_spin is not None else None
        note = self.note_edit.text().strip() or None if self.note_edit is not None else None
        return class_name, confidence, note


class PatientDialog(QDialog):
    """Create (or edit) a patient record."""

    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Patient" if existing else "New Patient")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.dob_edit = QDateEdit()
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setDisplayFormat("yyyy-MM-dd")
        self.dob_edit.setDate(QDate(2000, 1, 1))
        self.sex_combo = QComboBox()
        self.sex_combo.addItems(["", "Male", "Female", "Other"])
        self.phone_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(60)

        if existing:
            self.name_edit.setText(existing.get("full_name", ""))
            self.code_edit.setText(existing.get("patient_code") or "")
            if existing.get("date_of_birth"):
                y, m, d = [int(v) for v in existing["date_of_birth"].split("-")]
                self.dob_edit.setDate(QDate(y, m, d))
            self.sex_combo.setCurrentText(existing.get("sex") or "")
            self.phone_edit.setText(existing.get("phone") or "")
            self.notes_edit.setPlainText(existing.get("notes") or "")

        for label_text, widget in [
            ("Full name*:", self.name_edit),
            ("Patient code (optional, unique):", self.code_edit),
            ("Date of birth:", self.dob_edit),
            ("Sex:", self.sex_combo),
            ("Phone:", self.phone_edit),
            ("Notes:", self.notes_edit),
        ]:
            layout.addWidget(QLabel(label_text))
            layout.addWidget(widget)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def get_data(self):
        return {
            "full_name": self.name_edit.text().strip(),
            "patient_code": self.code_edit.text().strip() or None,
            "date_of_birth": self.dob_edit.date().toString("yyyy-MM-dd"),
            "sex": self.sex_combo.currentText() or None,
            "phone": self.phone_edit.text().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
        }
