"""
app.services.case_service
==========================
Business-logic layer sitting between the UI and the Database repository.
Owns the workflows that combine DB writes with filesystem operations
(copying/deleting image files under DATA_ROOT/images), so the UI layer
never touches sqlite or the filesystem directly.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import DATA_ROOT, IMAGES_ROOT
from app.data.database import Database
from app.utils.helpers import sanitize_filename


@dataclass
class SavedCaseImages:
    original_abs: Path
    annotated_abs: Path
    original_rel: Path
    annotated_rel: Path


class CaseService:
    """Coordinates Database operations with the on-disk image files that
    belong to each case."""

    def __init__(self, database: Optional[Database] = None):
        self.db = database or Database()

    # ------------------------------------------------------------ patients
    def create_patient(self, **fields) -> dict:
        patient_id = self.db.add_patient(**fields)
        return self.db.get_patient(patient_id)

    def search_patients(self, text: str = ""):
        return self.db.search_patients(text)

    def get_patient(self, patient_id):
        return self.db.get_patient(patient_id)

    # --------------------------------------------------------------- cases
    def get_cases_for_patient(self, patient_id):
        return self.db.get_cases_for_patient(patient_id)

    def get_case(self, case_id):
        return self.db.get_case(case_id)

    def get_detections(self, case_id, source=None):
        return self.db.get_detections(case_id, source=source)

    def resolve_case_image_path(self, case: dict) -> Path:
        """Absolute path to a case's original image on disk."""
        return DATA_ROOT / case["image_path"]

    def resolve_case_annotated_path(self, case: dict) -> Path:
        return DATA_ROOT / case["annotated_image_path"]

    def _patient_image_dir(self, patient: dict) -> Path:
        folder_name = (
            sanitize_filename(patient.get("patient_code") or f"P{patient['id']:04d}")
            + "_" + sanitize_filename(patient["full_name"])
        )
        return IMAGES_ROOT / folder_name

    def save_case(self, patient: dict, source_image_path: str, rendered_image,
                  original_pil_image, case_label: str, model_name: Optional[str],
                  conf_threshold: float, dentist_summary: str,
                  ai_detections: list, manual_detections: list) -> int:
        """Copy the original + annotated images into
        dental_data/images/<patient>/ and persist the case + its current
        AI/dentist detections. Returns the new case id.

        Raises OSError on file-copy failure so the caller can show a
        friendly error message.
        """
        patient_dir = self._patient_image_dir(patient)
        patient_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_safe = sanitize_filename(case_label)
        ext = Path(source_image_path).suffix or ".png"
        original_dest = patient_dir / f"{timestamp}_{label_safe}_original{ext}"
        annotated_dest = patient_dir / f"{timestamp}_{label_safe}_annotated.png"

        if Path(source_image_path).resolve() != original_dest.resolve():
            shutil.copy2(source_image_path, original_dest)
        img_to_save = rendered_image or original_pil_image
        img_to_save.save(annotated_dest)

        rel_original = original_dest.relative_to(DATA_ROOT)
        rel_annotated = annotated_dest.relative_to(DATA_ROOT)

        case_id = self.db.add_case(
            patient_id=patient["id"],
            image_path=str(rel_original),
            case_label=case_label,
            annotated_image_path=str(rel_annotated),
            model_name=model_name,
            conf_threshold=conf_threshold,
            dentist_summary=dentist_summary,
        )

        detections_to_store = []
        for d in ai_detections:
            if d["confidence"] < conf_threshold:
                continue
            detections_to_store.append({**d, "source": "ai"})
        for d in manual_detections:
            detections_to_store.append({**d, "source": "dentist"})
        if detections_to_store:
            self.db.add_detections(case_id, detections_to_store)

        return case_id

    def delete_case(self, case_id: int, delete_files: bool = True) -> None:
        """Delete a case (and, via ON DELETE CASCADE, its detections) from
        the database. Also removes the case's original/annotated image
        files from disk when delete_files=True. Missing files are ignored
        so a partially-broken case can still be cleaned up."""
        case = self.db.get_case(case_id)
        if case is None:
            return

        if delete_files:
            for rel_path in (case.get("image_path"), case.get("annotated_image_path")):
                if not rel_path:
                    continue
                abs_path = DATA_ROOT / rel_path
                try:
                    if abs_path.exists():
                        abs_path.unlink()
                except OSError:
                    pass  # best-effort: DB row deletion still proceeds

        self.db.delete_case(case_id)

    # --------------------------------------------------------- reporting
    def count_patient_problems(self, patient_id: int) -> int:
        """Count AI detections with confidence > 50% plus all dentist
        (manual) findings, summed across every saved case for a patient."""
        count = 0
        cases = self.db.get_cases_for_patient(patient_id)
        for case in cases:
            ai_dets = self.db.get_detections(case["id"], source="ai")
            dr_dets = self.db.get_detections(case["id"], source="dentist")
            count += sum(1 for d in ai_dets if (d.get("confidence") or 0) > 0.5)
            count += len(dr_dets)
        return count

    def close(self):
        self.db.close()
