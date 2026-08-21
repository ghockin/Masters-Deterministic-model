from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
LOG_FOLDER = BASE_DIR / "logs"
OUTPUT_FILE = BASE_DIR / "extracted_text.txt"
SCENARIO_TEMPLATE = BASE_DIR / "scenario_template.pdf"
