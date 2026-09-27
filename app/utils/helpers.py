"""
app.utils.helpers
==================
Small, dependency-light helper functions shared across the app. Kept
separate from UI and service code so they can be unit-tested in isolation.
"""

import math
import re

from app.config import PALETTE


def class_color(cls_id: int) -> tuple:
    """Deterministic color for a given class id, cycling through PALETTE."""
    return PALETTE[cls_id % len(PALETTE)]


def sanitize_filename(s: str) -> str:
    """Make a string safe to use as a file/folder name component."""
    s = (s or "").strip()
    s = re.sub(r"[^\w\-. ]", "_", s)
    s = re.sub(r"\s+", "_", s)
    return s or "unnamed"


def dashed_rectangle(draw, box, color, width=3, dash=8, gap=5):
    """Draw a dashed rectangle outline with PIL (no native dash support)."""
    x1, y1, x2, y2 = box

    def dashed_line(p1, p2):
        (xa, ya), (xb, yb) = p1, p2
        length = math.hypot(xb - xa, yb - ya)
        if length == 0:
            return
        dx, dy = (xb - xa) / length, (yb - ya) / length
        pos = 0.0
        while pos < length:
            start = (xa + dx * pos, ya + dy * pos)
            end_pos = min(pos + dash, length)
            end = (xa + dx * end_pos, ya + dy * end_pos)
            draw.line([start, end], fill=color, width=width)
            pos += dash + gap

    dashed_line((x1, y1), (x2, y1))
    dashed_line((x2, y1), (x2, y2))
    dashed_line((x2, y2), (x1, y2))
    dashed_line((x1, y2), (x1, y1))
