from flask import Blueprint, render_template, request, send_file, send_from_directory, jsonify
import os
import zipfile
import pdfplumber
from pathlib import Path
import random
from data_organise import populate_data_frame
from database import get_all_scenarios, get_scenario_by_id
from run_simulation import SimulationState
from config import SCENARIO_TEMPLATE, OUTPUT_FILE, UPLOAD_FOLDER, LOG_FOLDER, BASE_DIR

main = Blueprint("main", __name__)
sim = None

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/download-scenario-template")
def download_scenario_template():
    if not Path(SCENARIO_TEMPLATE).exists():
        return "No scenario_template.pdf found yet.", 404
    return send_file(SCENARIO_TEMPLATE, as_attachment=True, download_name="scenario_template.pdf")


@main.post("/upload-scenario")
def upload_pdf():
    file = request.files.get("pdf")
    if not file or not file.filename.lower().endswith(".pdf"):
        return jsonify({"message": "Please upload a valid PDF file.", "category": "error"}), 400
    pdf_path = Path(UPLOAD_FOLDER) / file.filename
    file.save(pdf_path)
    return jsonify({"message": f"PDF '{file.filename}' uploaded successfully.", "category": "success"})


@main.post("/upload-scenario-pdfplumber")
def extract_pdfplumber():
    file = request.files.get("pdf")
    if not file or not file.filename.lower().endswith(".pdf"):
        return jsonify({"message": "Please upload a valid PDF file.", "category": "error"}), 400

    pdf_path = Path(UPLOAD_FOLDER) / file.filename
    file.save(pdf_path)
    extracted_text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                extracted_text += f"--- Page {page_num} ---\n{page_text}\n\n"

        Path(OUTPUT_FILE).write_text(extracted_text, encoding="utf-8")
        populate_data_frame(OUTPUT_FILE)
        return jsonify({"message": "PDF extracted with pdfplumber and scenario saved to database.", "category": "success"})
    except Exception as e:
        return jsonify({"message": f"pdfplumber extraction failed: {e}", "category": "error"}), 500


@main.get("/scenarios")
def scenarios():
    return render_template("scenarios.html", scenarios=get_all_scenarios())


@main.get("/db-view")
def db_view():
    return render_template("view_database_scenarios.html", scenarios=get_all_scenarios())


@main.get("/view-scenario")
def view_scenario():
    global sim
    scenario_id = request.args.get("scenario_id")
    if not scenario_id:
        return "Missing scenario_id", 400
    scenario = get_scenario_by_id(int(scenario_id))
    if scenario is None:
        return "Scenario not found", 404
    sim = SimulationState(scenario)
    return render_template("simulation.html", sim=sim)


def sim_state_response():
    return {
        "tick": sim.tick_count,

        "plot_bounds": sim.plot_bounds,

        "ship_x_nm": round(sim.ship_x_nm, 2),
        "ship_y_nm": round(sim.ship_y_nm, 2),

        "ship_speed_min": sim.ship_speed_min,
        "ship_speed_max": sim.ship_speed_max,

        "torpedo_x_nm": round(sim.torpedo_x_nm, 2),
        "torpedo_y_nm": round(sim.torpedo_y_nm, 2),

        "objective_point_x_nm": sim.objective_point_x_nm,
        "objective_point_y_nm": sim.objective_point_y_nm,

        "objective_points": sim.objective_points,
        "selected_objective_point": sim.selected_objective_point,

        "separation_nm": sim.get_separation_nm(),
        "distance_to_objective_point_nm": sim.get_distance_to_objective_point_nm(),

        "bearing": sim.get_ship_bearing_to_objective_point(),
        "torpedo_bearing": sim.get_torpedo_bearing_to_ship(),

        "friendly_speed": sim.friendly_speed,
        "enemy_speed": sim.enemy_speed,

        "finished": sim.finished,
        "destroyed": sim.friendly_destroyed,
        "current_message": sim.current_message,
        "result": sim.result,
        "trajectory": sim.trajectory,
        "countermeasure_active": sim.countermeasure_active,
        "countermeasure_timer": sim.countermeasure_timer,
        "torpedo_lost_contact_timer": sim.torpedo_lost_contact_timer,
    }

@main.get("/state")
def state():
    if sim is None:
        return jsonify({"error": "no active simulation"}), 400
    return jsonify(sim_state_response())


@main.post("/tick")
def tick():
    if sim is None:
        return jsonify({"error": "no simulation"}), 400
    sim.tick()
    return jsonify(sim_state_response())


@main.post("/reset")
def reset():
    global sim
    if sim is None:
        return jsonify({"error": "no simulation"}), 400
    sim = SimulationState(sim.scenario)
    return jsonify({"ok": True})


@main.post("/prepare-speed-sweep")
def prepare_speed_sweep():
    scenario_id = int(request.form.get("scenario_id"))
    scenario = get_scenario_by_id(scenario_id)
    min_speed = int(float(scenario["ship_speed_min"]))
    max_speed = int(float(scenario["ship_speed_max"]))
    results = []

    for speed in range(min_speed, max_speed + 1):
        random.seed(f"{scenario_id}-{speed}")
        batch_sim = SimulationState(scenario, ship_speed_override=speed, log_suffix=f"speed_{speed}", enable_logging=True)
        max_ticks = 10000
        while not batch_sim.finished and batch_sim.tick_count < max_ticks:
            batch_sim.tick()
        if not batch_sim.finished:
            batch_sim.finished = True
            batch_sim.result = "STOPPED - MAX TICKS REACHED"
            batch_sim.add_message("Simulation stopped because max ticks were reached.")
            batch_sim.record_trajectory()
            batch_sim.log_state()
        
        final_result = batch_sim.result

        if batch_sim.friendly_destroyed:
            final_result = "MISSION FAILED - TORPEDO INTERCEPTED SHIP"
        elif not batch_sim.finished:
            final_result = "STOPPED - MAX TICKS REACHED"

        results.append({
            "speed": speed,
            "ticks": batch_sim.tick_count,
            "destroyed": batch_sim.friendly_destroyed,
            "result": final_result,
            "log_file": f"id{scenario_id}/sim_{scenario_id}_speed_{speed}.csv"
        })

    return jsonify({"message": "Speed simulations generated.", "results": results})


@main.post("/play-speed-simulation")
def play_speed_simulation():
    global sim
    scenario_id = int(request.form.get("scenario_id"))
    speed = int(float(request.form.get("speed")))
    scenario = get_scenario_by_id(scenario_id)
    random.seed(f"{scenario_id}-{speed}")
    sim = SimulationState(scenario, ship_speed_override=speed, enable_logging=False)
    return jsonify({"ok": True, "speed": speed})


@main.get("/logs/<path:filename>")
def download_log(filename):
    return send_from_directory(LOG_FOLDER, filename, as_attachment=True)


@main.get("/download-all-logs/<int:scenario_id>")
def download_all_logs(scenario_id):
    folder = Path(LOG_FOLDER) / f"id{scenario_id}"
    if not folder.exists():
        return "No logs generated for this scenario yet.", 404
    zip_path = Path(LOG_FOLDER) / f"scenario_{scenario_id}_logs.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_file in folder.glob("*.csv"):
            zf.write(csv_file, arcname=csv_file.name)
    return send_file(zip_path, as_attachment=True, download_name=f"scenario_{scenario_id}_logs.zip")


@main.get("/download-objective-point-analysis/<int:scenario_id>")
def download_objective_point_analysis(scenario_id):

    folder = Path(LOG_FOLDER) / f"id{scenario_id}"

    report_file = folder / f"objective_point_analysis_{scenario_id}.txt"

    if not report_file.exists():
        return "Objective point analysis not generated yet.", 404

    return send_file(
        report_file,
        as_attachment=True,
        download_name=report_file.name
    )