"""
app.data.database
==================
SQLite persistence layer for the Dental OPG Detector (repository pattern).
This module owns the schema and raw CRUD only — no filesystem/image
handling and no UI concerns. Higher-level workflows (e.g. "save a case,
including copying image files") live in app.services.case_service.

Schema
------
patients   : one row per patient
cases      : one row per analyzed image / visit, linked to a patient
detections : one row per bounding box (AI-generated OR dentist-added),
             linked to a case. The `source` column distinguishes them:
             'ai'      -> produced by the YOLO model
             'dentist' -> manually drawn/added inside the app

All paths stored in the DB are relative to DATA_ROOT so the whole
`dental_data` folder (db + images) can be moved/copied/backed up together.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

from app.config import DATA_ROOT, DB_PATH, IMAGES_ROOT

# Re-exported for backwards-compatible callers (app.services, etc.)
__all__ = ["Database", "DATA_ROOT", "DB_PATH", "IMAGES_ROOT"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    # ------------------------------------------------------------- schema
    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                patient_code TEXT UNIQUE,
                date_of_birth TEXT,
                sex TEXT,
                phone TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                case_label TEXT,
                image_path TEXT NOT NULL,
                annotated_image_path TEXT,
                model_name TEXT,
                conf_threshold REAL,
                dentist_summary TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('ai','dentist')),
                class_name TEXT NOT NULL,
                confidence REAL,
                x1 REAL NOT NULL, y1 REAL NOT NULL,
                x2 REAL NOT NULL, y2 REAL NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cases_patient ON cases(patient_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_det_case ON detections(case_id)")
        self.conn.commit()

    # ------------------------------------------------------------ patients
    def add_patient(self, full_name, patient_code=None, date_of_birth=None,
                     sex=None, phone=None, notes=None) -> int:
        cur = self.conn.execute(
            """INSERT INTO patients (full_name, patient_code, date_of_birth, sex,
                                      phone, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (full_name.strip(), (patient_code or "").strip() or None,
             date_of_birth, sex, phone, notes, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_patient(self, patient_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE patients SET {cols} WHERE id = ?",
                           (*fields.values(), patient_id))
        self.conn.commit()

    def get_patient(self, patient_id):
        row = self.conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return dict(row) if row else None

    def search_patients(self, text: str = ""):
        text = f"%{text.strip()}%"
        rows = self.conn.execute(
            """SELECT * FROM patients
               WHERE full_name LIKE ? OR IFNULL(patient_code,'') LIKE ?
               ORDER BY full_name COLLATE NOCASE""",
            (text, text),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_patients(self):
        rows = self.conn.execute("SELECT * FROM patients ORDER BY full_name COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------- cases
    def add_case(self, patient_id, image_path, case_label=None,
                 annotated_image_path=None, model_name=None,
                 conf_threshold=None, dentist_summary=None) -> int:
        cur = self.conn.execute(
            """INSERT INTO cases (patient_id, case_label, image_path, annotated_image_path,
                                   model_name, conf_threshold, dentist_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, case_label, str(image_path),
             str(annotated_image_path) if annotated_image_path else None,
             model_name, conf_threshold, dentist_summary, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_case(self, case_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE cases SET {cols} WHERE id = ?",
                           (*fields.values(), case_id))
        self.conn.commit()

    def get_case(self, case_id):
        row = self.conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None

    def get_cases_for_patient(self, patient_id):
        rows = self.conn.execute(
            "SELECT * FROM cases WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_case(self, case_id):
        """Delete a case row. Its detections are removed automatically via
        ON DELETE CASCADE. Image files on disk are NOT touched here — see
        app.services.case_service.CaseService.delete_case for the full
        (DB + filesystem) workflow used by the UI."""
        self.conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        self.conn.commit()

    # --------------------------------------------------------- detections
    def add_detections(self, case_id, detections: list):
        """detections: list of dicts with keys
        source, class_name, confidence, x1, y1, x2, y2, note(optional)"""
        rows = [
            (case_id, d["source"], d["class_name"], d.get("confidence"),
             d["x1"], d["y1"], d["x2"], d["y2"], d.get("note"), _now())
            for d in detections
        ]
        self.conn.executemany(
            """INSERT INTO detections (case_id, source, class_name, confidence,
                                        x1, y1, x2, y2, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()

    def clear_detections(self, case_id, source=None):
        if source:
            self.conn.execute("DELETE FROM detections WHERE case_id = ? AND source = ?",
                               (case_id, source))
        else:
            self.conn.execute("DELETE FROM detections WHERE case_id = ?", (case_id,))
        self.conn.commit()

    def get_detections(self, case_id, source=None):
        if source:
            rows = self.conn.execute(
                "SELECT * FROM detections WHERE case_id = ? AND source = ? ORDER BY id",
                (case_id, source),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM detections WHERE case_id = ? ORDER BY source, id",
                (case_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
