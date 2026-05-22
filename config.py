from pathlib import Path
import pytesseract

# Project root
BASE_DIR = Path(__file__).resolve().parent

# App + assets
APP_DIR = BASE_DIR / "app"
ASSETS_DIR = APP_DIR / "assets"

# Scenario template
SCENARIO_TEMPLATE = ASSETS_DIR / "scenario_template.pdf"

# OCR tools
POPPLER_PATH = ASSETS_DIR / "poppler" / "Library" / "bin"

OUTPUT_FILE = BASE_DIR / "output.txt"
DEBUG_DIR = BASE_DIR / "debug_pages"
UPLOAD_FOLDER = BASE_DIR / "uploads"

# Bounding boxes for OCR (left, top, right, bottom)
OCR_BOXES = {
    "document_info": (50, 615, 1500, 850),
    "mission_brief": (50, 950, 1500, 1200),
    "intel_summary": (50, 1250, 1500, 1500),
    "operative":     (50, 1600, 1500, 1750)
}

# Safety checks (strongly recommended)
if not SCENARIO_TEMPLATE.exists():
    raise RuntimeError(f"Scenario template missing: {SCENARIO_TEMPLATE}")


if not POPPLER_PATH.exists():
    raise RuntimeError(f"Poppler not found: {POPPLER_PATH}")
