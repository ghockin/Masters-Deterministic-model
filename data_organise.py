import re
import json
import math
from pathlib import Path
from database import insert_scenario


BASE_DIR = Path(__file__).resolve().parent
OBJECTIVE_POINT_DOCUMENT = BASE_DIR / "objective_points_generated.txt"

# =========================
# PATTERNS
# =========================

PATTERNS = {
    "ship_start": [
        r"commence transit from position\s*\(([-\d\.]+)\s*,\s*([-\d\.]+)\)",
        r"starting position\s*\(([-\d\.]+)\s*,\s*([-\d\.]+)\)",
        r"start(?:ing)? coordinates?\s*[:\-]?\s*([-\d\.]+)[,\s]+([-\d\.]+)",
        r"position is\s*\(([-\d\.]+)\s*,\s*([-\d\.]+)\)"
    ],

    "speed_range": [
        r"speed between\s*([-\d\.]+)\s*and\s*([-\d\.]+)",
        r"speed range\s*[:\-]?\s*([-\d\.]+)\s*[-–]\s*([-\d\.]+)",
        r"max speed\s*([-\d\.]+).*?min speed\s*([-\d\.]+)"
    ],

    "countermeasure_distance": [
        r"within\s*([-\d\.]+)\s*nautical miles",
        r"trigger distance\s*[:\-]?\s*([-\d\.]+)",
        r"countermeasures.*?([-\d\.]+)\s*NM"
    ],

    "torpedo_position": [
        r"torpedo position.*?\(([-\d\.]+)\s*,\s*([-\d\.]+)\)",
        r"last known position.*?([-\d\.]+)[,\s]+([-\d\.]+)"
    ],

    "torpedo_speed": [
        r"torpedo speed.*?([-\d\.]+)",
        r"speed of torpedo.*?([-\d\.]+)"
    ],

    "objective_distance": [
        r"objective point distance\s*[:\-]?\s*([-\d\.]+)",
        r"objective distance\s*([-\d\.]+)",
        r"distance to objective.*?([-\d\.]+)"
    ],

    "objective_bearing": [
        r"objective point bearing\s*[:\-]?\s*([-\d\.]+)",
        r"bearing.*?([-\d\.]+)\s*degrees",
        r"bearing.*?([-\d\.]+)"
    ],

    "objective_quantity": [
        r"objective point quantity\s*[:\-]?\s*([-\d\.]+)",
        r"number of objective points\s*([-\d\.]+)",
        r"objective points.*?([-\d\.]+)"
    ]
}




# =========================
# UTILITIES
# =========================

def clean_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def get_match(pattern, text, default=None, flags=re.IGNORECASE | re.DOTALL):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else default


def to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def extract_with_patterns(pattern_list, text, count=1, default=None):
    for pattern in pattern_list:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            if count == 1:
                return to_float(groups[0], default)
            return [to_float(g, default) for g in groups]
    return default



# =========================
# Objective Point GENERATION
# =========================

def create_objective_points(ship_x, ship_y, distance, bearing_range, quantity):
    objective_points = []

    if quantity <= 0:
        quantity = 1

    angle_step = bearing_range / quantity

    for i in range(quantity):
        bearing = i * angle_step
        radians = math.radians(bearing)

        x = ship_x + math.sin(radians) * distance
        y = ship_y + math.cos(radians) * distance

        objective_points.append({
            "id": i + 1,
            "bearing": round(bearing, 2),
            "x": round(x, 2),
            "y": round(y, 2)
        })

    return objective_points


def write_objective_point_document(scenario_name, objective_points):
    with open(OBJECTIVE_POINT_DOCUMENT, "w", encoding="utf-8") as f:
        f.write("Objective point Document\n")
        f.write(f"Scenario: {scenario_name}\n")
        f.write("=" * 50 + "\n\n")

        for zone in objective_points:
            f.write(
                f"objective_point {zone['id']} | "
                f"Bearing: {zone['bearing']}° | "
                f"X: {zone['x']} NM | "
                f"Y: {zone['y']} NM\n"
            )


# =========================
# MAIN PARSER
# =========================

def populate_data_frame(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # -------------------------
    # BASIC HEADER INFO
    # -------------------------

    opord_name = get_match(
        r"^\s*OPORD:\s*([^\n\r]+)",
        text,
        "Unnamed Scenario",
        flags=re.IGNORECASE | re.MULTILINE
    )

    scenario_name = f"Scenario Data - {opord_name}"

    date = get_match(
        r"(?:DATE/TIME|DATE)\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8})",
        text,
        ""
    )

    mission_raw = get_match(
        r"Mission Brief\s*(.*?)\s*Intel Summary",
        text,
        ""
    )

    intel_raw = get_match(
        r"Intel Summary\s*(.*?)\s*Operation Properties",
        text,
        ""
    )

    operation_raw = get_match(
        r"Operation Properties\s*(.*?)\s*Approved By",
        text,
        ""
    )

    mission_brief = clean_text(mission_raw)
    intel_summary = clean_text(intel_raw)
    operation_properties = clean_text(operation_raw)

    # -------------------------
    # ENEMY + FRIENDLY INFO
    # -------------------------

    enemy_class = get_match(
        r"Class:\s*([A-Za-z0-9\s\-]+)",
        intel_raw,
        "Unknown"
    )

    friendly_match = re.search(
        r"\b(HMS\s+[A-Za-z0-9\-]+)\b",
        mission_raw,
        re.IGNORECASE
    )

    friendly_class = friendly_match.group(1).strip() if friendly_match else "Unknown"

    # =====================================================
    # NAVAL ORDER PARSING (MAIN EXTRACTION LOGIC)
    # =====================================================

    ship_coords = extract_with_patterns(PATTERNS["ship_start"], text, count=2, default=[20, 40])
    ship_start_x_nm, ship_start_y_nm = ship_coords

    speed_range = extract_with_patterns(PATTERNS["speed_range"], text, count=2, default=[20, 30])
    ship_speed_min, ship_speed_max = speed_range

    countermeasure_trigger_distance_nm = extract_with_patterns(
        PATTERNS["countermeasure_distance"], text, default=4
    )


    torpedo_coords = extract_with_patterns(PATTERNS["torpedo_position"], text, count=2, default=[0, 0])
    torpedo_start_x_nm, torpedo_start_y_nm = torpedo_coords


    torpedo_speed = extract_with_patterns(PATTERNS["torpedo_speed"], text, default=60)


    # -------------------------
    # Objective point
    # -------------------------

    objective_point_distance_nm = extract_with_patterns(
        PATTERNS["objective_distance"], text, default=100
    )


    objective_point_bearing_around_ship = extract_with_patterns(
        PATTERNS["objective_bearing"], text, default=360
    )


    objective_point_multiplier = int(extract_with_patterns(
        PATTERNS["objective_quantity"], text, default=6
    ))


    objective_points = create_objective_points(
        ship_start_x_nm,
        ship_start_y_nm,
        objective_point_distance_nm,
        objective_point_bearing_around_ship,
        objective_point_multiplier
    )

    objective_point_x_nm = objective_points[0]["x"]
    objective_point_y_nm = objective_points[0]["y"]

    write_objective_point_document(scenario_name, objective_points)

    # -------------------------
    # BUILD OUTPUT DATASET
    # -------------------------

    data = {
        "scenario_name": [scenario_name],
        "date": [date],
        "mission_brief": [mission_brief],
        "intel_summary": [intel_summary],
        "operation_properties": [operation_properties],

        "enemy_class": [enemy_class],
        "friendly_class": [friendly_class],

        "ship_start_x_nm": [ship_start_x_nm],
        "ship_start_y_nm": [ship_start_y_nm],
        "ship_speed_min": [ship_speed_min],
        "ship_speed_max": [ship_speed_max],

        "torpedo_start_x_nm": [torpedo_start_x_nm],
        "torpedo_start_y_nm": [torpedo_start_y_nm],
        "torpedo_speed": [torpedo_speed],

        "objective_point_distance_nm": [objective_point_distance_nm],
        "objective_point_bearing_around_ship": [objective_point_bearing_around_ship],
        "objective_point_multiplier": [objective_point_multiplier],
        "objective_points_json": [json.dumps(objective_points)],

        "objective_point_x_nm": [objective_point_x_nm],
        "objective_point_y_nm": [objective_point_y_nm],

        "countermeasure_trigger_distance_nm": [countermeasure_trigger_distance_nm],
    }

    print("\n--- PARSED DATA ---")
    for key, value in data.items():
        print(f"{key:<35}: {value[0]}")
    print("--- END ---\n")

    insert_scenario(data)