import re
from database import insert_scenario


def clean_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def get_match(pattern, text, default=None, flags=re.IGNORECASE | re.DOTALL):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else default


def to_float(value, default=0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def populate_data_frame(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    text = text.replace("\r\n", "\n").replace("\r", "\n")

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

    ship_start_x_nm = to_float(get_match(r"Ship start X\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 40), 40)
    ship_start_y_nm = to_float(get_match(r"Ship start Y\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 20), 20)

    ship_speed_min = to_float(get_match(r"Ship Speed Minimum\s*\(Knots\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 20), 20)
    ship_speed_max = to_float(get_match(r"Ship Speed Maximum\s*\(Knots\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 30), 30)

    torpedo_start_x_nm = to_float(get_match(r"Torpedo start X\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 0), 0)
    torpedo_start_y_nm = to_float(get_match(r"Torpedo start Y\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 0), 0)

    torpedo_speed = to_float(get_match(r"Torpedo speed\s*\(Knots\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 200), 200)

    safe_zone_x_nm = to_float(get_match(r"Safe zone X\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 100), 100)
    safe_zone_y_nm = to_float(get_match(r"Safe zone Y\s*\(NM\)\s*:\s*(-?\d+(?:\.\d+)?)", operation_raw, 0), 0)

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

        "safe_zone_x_nm": [safe_zone_x_nm],
        "safe_zone_y_nm": [safe_zone_y_nm],
    }

    print("\n--- PARSED DATA ---")
    for key, value in data.items():
        print(f"{key:<30}: {value[0]}")
    print("--- END ---\n")

    insert_scenario(data)