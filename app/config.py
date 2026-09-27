"""
app.config
==========
Centralized, static configuration for the application: paths, palettes,
and author/about info. Nothing in this module has side effects other than
creating the DATA_ROOT/IMAGES_ROOT folders lazily (done in app.data.database).
"""

import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Filesystem
# --------------------------------------------------------------------------

DATA_ROOT = Path("dental_data")
DB_PATH = DATA_ROOT / "dental_records.db"
IMAGES_ROOT = DATA_ROOT / "images"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")


def resource_path(relative_path: str) -> str:
    """Get absolute path to a bundled resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


DEFAULT_MODEL_PATH = resource_path(os.path.join("assets", "best.pt"))

# --------------------------------------------------------------------------
# Visuals
# --------------------------------------------------------------------------

PALETTE = [
    (239, 83, 80), (66, 165, 245), (102, 187, 106), (255, 202, 40),
    (171, 71, 188), (38, 198, 218), (255, 112, 67), (156, 204, 101),
    (92, 107, 192), (240, 98, 146), (0, 172, 193), (255, 167, 38),
    (141, 110, 99), (120, 144, 156),
]

# --------------------------------------------------------------------------
# Project / author info
# --------------------------------------------------------------------------

AUTHOR_NAME = "مهدی احمدی"
AUTHOR_GITHUB_URL = "https://github.com/mahdiahmadii"
AUTHOR_LINKEDIN_URL = "https://www.linkedin.com/in/mahdiahmadii"
