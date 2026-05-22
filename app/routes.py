from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    send_from_directory,
    jsonify
)

import pdfplumber
import os

from data_organise import populate_data_frame

from database import (
    get_all_scenarios,
    get_scenario_by_id
)

from run_simulation import SimulationState

from config import (
    SCENARIO_TEMPLATE,
    OUTPUT_FILE,
    UPLOAD_FOLDER
)

main = Blueprint("main", __name__)

sim = None

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("logs", exist_ok=True)


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/download-scenario-template")
def download_scenario_template():
    return send_file(
        SCENARIO_TEMPLATE,
        as_attachment=True,
        download_name="scenario_template.pdf"
    )


@main.post("/upload-scenario")
def upload_pdf():
    file = request.files.get("pdf")

    if not file or not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "message": "Please upload a valid PDF file.",
            "category": "error"
        })

    pdf_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(pdf_path)

    return jsonify({
        "message": f"PDF '{file.filename}' uploaded successfully.",
        "category": "success"
    })


@main.post("/upload-scenario-pdfplumber")
def extract_pdfplumber():
    file = request.files.get("pdf")

    if not file or not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "message": "Please upload a valid PDF file.",
            "category": "error"
        })

    pdf_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(pdf_path)

    extracted_text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""

                extracted_text += (
                    f"--- Page {page_num} ---\n"
                    f"{page_text}\n\n"
                )

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(extracted_text)

        populate_data_frame(OUTPUT_FILE)

        return jsonify({
            "message": "PDF extracted with pdfplumber and scenario saved to database.",
            "category": "success"
        })

    except Exception as e:
        return jsonify({
            "message": f"pdfplumber extraction failed: {e}",
            "category": "error"
        }), 500


@main.get("/scenarios")
def scenarios():
    scenarios = get_all_scenarios()

    return render_template(
        "scenarios.html",
        scenarios=scenarios
    )



@main.get("/view-scenario")
def view_scenario():
    global sim

    scenario_id = request.args.get("scenario_id")

    if not scenario_id:
        return "Missing scenario_id", 400

    scenario = get_scenario_by_id(
        int(scenario_id)
    )

    if scenario is None:
        return "Scenario not found", 404

    sim = SimulationState(scenario)

    return render_template(
        "simulation.html",
        sim=sim
    )


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

        "safe_zone_x_nm": sim.safe_zone_x_nm,
        "safe_zone_y_nm": sim.safe_zone_y_nm,

        "separation_nm": sim.get_separation_nm(),
        "distance_to_safe_zone_nm": sim.get_distance_to_safe_zone_nm(),

        "bearing": sim.get_ship_bearing_to_safe_zone(),
        "torpedo_bearing": sim.get_torpedo_bearing_to_ship(),

        "friendly_speed": sim.friendly_speed,
        "enemy_speed": sim.enemy_speed,

        "finished": sim.finished,
        "destroyed": sim.friendly_destroyed,
        "current_message": sim.current_message,
        "result": sim.result,
    }


@main.get("/state")
def state():
    global sim

    if sim is None:
        return jsonify({
            "error": "no active simulation"
        }), 400

    return jsonify(
        sim_state_response()
    )


@main.post("/tick")
def tick():
    global sim

    if sim is None:
        return jsonify({
            "error": "no simulation"
        }), 400

    sim.tick()

    return jsonify(
        sim_state_response()
    )


@main.post("/reset")
def reset():
    global sim

    if sim is None:
        return jsonify({
            "error": "no simulation"
        }), 400

    sim = SimulationState(sim.scenario)

    return jsonify({
        "ok": True
    })


@main.post("/run-speed-sweep")
def run_speed_sweep():
    scenario_id = request.form.get("scenario_id")
    min_speed = request.form.get("min_speed")
    max_speed = request.form.get("max_speed")

    if not scenario_id or not min_speed or not max_speed:
        return jsonify({
            "message": "Scenario ID, minimum speed, and maximum speed are required.",
            "category": "error"
        }), 400

    min_speed = int(float(min_speed))
    max_speed = int(float(max_speed))

    if min_speed > max_speed:
        return jsonify({
            "message": "Minimum speed cannot be greater than maximum speed.",
            "category": "error"
        }), 400

    scenario = get_scenario_by_id(int(scenario_id))

    if scenario is None:
        return jsonify({
            "message": "Scenario not found.",
            "category": "error"
        }), 404

    results = []

    for speed in range(min_speed, max_speed + 1):
        batch_sim = SimulationState(
            scenario,
            ship_speed_override=speed,
            log_suffix=f"speed_{speed}"
        )

        max_ticks = 10000

        while not batch_sim.finished and batch_sim.tick_count < max_ticks:
            batch_sim.tick()

        if not batch_sim.finished:
            batch_sim.finished = True
            batch_sim.result = "STOPPED - MAX TICKS REACHED"
            batch_sim.add_message("Simulation stopped because max ticks were reached.")
            batch_sim.log_state()

        filename = os.path.basename(batch_sim.log_file)

        results.append({
            "speed": speed,
            "ticks": batch_sim.tick_count,
            "destroyed": batch_sim.friendly_destroyed,
            "result": batch_sim.result,
            "log_file": filename
        })

    return jsonify({
        "message": "Speed sweep complete.",
        "category": "success",
        "results": results
    })


@main.get("/logs/<path:filename>")
def download_log(filename):
    return send_from_directory(
        "logs",
        filename,
        as_attachment=True
    )


@main.get("/db-view")
def db_view():
    scenarios = get_all_scenarios()

    return render_template(
        "view_database_scenarios.html",
        scenarios=scenarios
    )
    
    
@main.post("/prepare-speed-sweep")
def prepare_speed_sweep():

    scenario_id = int(
        request.form.get("scenario_id")
    )

    scenario = get_scenario_by_id(
        scenario_id
    )

    min_speed = int(
        float(scenario["ship_speed_min"])
    )

    max_speed = int(
        float(scenario["ship_speed_max"])
    )

    results = []

    for speed in range(
        min_speed,
        max_speed + 1
    ):

        batch_sim = SimulationState(
            scenario,
            ship_speed_override=speed,
            log_suffix=f"speed_{speed}",
            enable_logging=True
        )

        max_ticks = 10000

        while (
            not batch_sim.finished
            and batch_sim.tick_count < max_ticks
        ):
            batch_sim.tick()

        if not batch_sim.finished:

            batch_sim.finished = True

            batch_sim.result = (
                "STOPPED - MAX TICKS REACHED"
            )

            batch_sim.add_message(
                "Simulation stopped because "
                "max ticks were reached."
            )

            batch_sim.log_state()

        results.append({
            "speed": speed,
            "ticks": batch_sim.tick_count,
            "result": batch_sim.result
        })

    return jsonify({
        "message": "Speed simulations generated.",
        "results": results
    })


@main.post("/play-speed-simulation")
def play_speed_simulation():

    global sim

    scenario_id = int(
        request.form.get("scenario_id")
    )

    speed = int(
        float(request.form.get("speed"))
    )

    scenario = get_scenario_by_id(
        scenario_id
    )

    sim = SimulationState(
        scenario,
        ship_speed_override=speed,
        enable_logging=False
    )

    return jsonify({
        "ok": True,
        "speed": speed
    })