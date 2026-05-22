import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scenario.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        scenario_name TEXT,

        date TEXT,
        mission_brief TEXT,
        intel_summary TEXT,
        operation_properties TEXT,

        enemy_class TEXT,
        friendly_class TEXT,

        ship_start_x_nm REAL,
        ship_start_y_nm REAL,
        ship_speed_min REAL,
        ship_speed_max REAL,

        torpedo_start_x_nm REAL,
        torpedo_start_y_nm REAL,
        torpedo_speed REAL,

        safe_zone_x_nm REAL,
        safe_zone_y_nm REAL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def first(value, default=None):
    if isinstance(value, list):
        if not value or value[0] is None:
            return default
        return value[0]

    return value if value is not None else default


def insert_scenario(data):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scenarios (
            scenario_name,
            date,
            mission_brief,
            intel_summary,
            operation_properties,
            enemy_class,
            friendly_class,
            ship_start_x_nm,
            ship_start_y_nm,
            ship_speed_min,
            ship_speed_max,
            torpedo_start_x_nm,
            torpedo_start_y_nm,
            torpedo_speed,
            safe_zone_x_nm,
            safe_zone_y_nm
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        first(data.get("scenario_name"), "Unnamed Scenario"),
        first(data.get("date"), ""),
        first(data.get("mission_brief"), ""),
        first(data.get("intel_summary"), ""),
        first(data.get("operation_properties"), ""),
        first(data.get("enemy_class"), "Unknown"),
        first(data.get("friendly_class"), "Unknown"),

        float(first(data.get("ship_start_x_nm"), 40)),
        float(first(data.get("ship_start_y_nm"), 20)),
        float(first(data.get("ship_speed_min"), 20)),
        float(first(data.get("ship_speed_max"), 30)),

        float(first(data.get("torpedo_start_x_nm"), 0)),
        float(first(data.get("torpedo_start_y_nm"), 0)),
        float(first(data.get("torpedo_speed"), 200)),

        float(first(data.get("safe_zone_x_nm"), 100)),
        float(first(data.get("safe_zone_y_nm"), 0)),
    ))

    conn.commit()
    conn.close()


def get_all_scenarios():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenarios ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_scenario_by_id(scenario_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def reset_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS scenarios")
    conn.commit()
    conn.close()
    init_db()
