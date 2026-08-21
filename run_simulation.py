import csv
import json
import math
import os
import random

class SimulationState:
    def __init__(
        self,
        scenario,
        ship_speed_override=None,
        objective_point_override=None,
        log_suffix=None,
        enable_logging=True
    ):

        self.scenario = scenario

        self.tick_count = 0
        self.finished = False
        self.friendly_destroyed = False

        self.scenario_name = scenario["scenario_name"]
        self.date = scenario["date"]

        self.mission_brief = scenario["mission_brief"]
        self.intel_summary = scenario["intel_summary"]
        self.operation_properties = scenario["operation_properties"]

        self.enemy_class = scenario["enemy_class"]
        self.friendly_class = scenario["friendly_class"]

        self.ship_start_x_nm = float(scenario["ship_start_x_nm"])
        self.ship_start_y_nm = float(scenario["ship_start_y_nm"])

        self.ship_x_nm = self.ship_start_x_nm
        self.ship_y_nm = self.ship_start_y_nm

        self.ship_speed_min = float(scenario["ship_speed_min"])
        self.ship_speed_max = float(scenario["ship_speed_max"])

        self.torpedo_start_x_nm = float(scenario["torpedo_start_x_nm"])
        self.torpedo_start_y_nm = float(scenario["torpedo_start_y_nm"])

        self.torpedo_x_nm = self.torpedo_start_x_nm
        self.torpedo_y_nm = self.torpedo_start_y_nm
        
        
        # Manoeuvre settings
        self.manoeuvre_trigger_distance_nm = int(scenario["countermeasure_trigger_distance_nm"] or 20)

        self.minimum_manoeuvre_speed_ratio = 0.9

        self.acceleration_knots_per_tick = 0.10
        self.countermeasure_speed_loss_ratio = 0.3

        self.countermeasure_lifetime_seconds = 10
        self.countermeasure_timer = 0
        self.countermeasure_active = False

        self.countermeasure_effectiveness = 0.4

        self.torpedo_lost_contact_duration = 20
        self.torpedo_lost_contact_timer = 0


        self.friendly_speed = (
            float(ship_speed_override)
            if ship_speed_override is not None
            else self.ship_speed_min
        )

        self.target_friendly_speed = self.friendly_speed
        self.deceleration_knots_per_tick = 0.20

        self.enemy_speed = float(scenario["torpedo_speed"])
        
        self.original_enemy_speed = self.enemy_speed
        self.original_friendly_speed = self.friendly_speed
        
        self.objective_point_distance_nm = float(scenario["objective_point_distance_nm"])
        self.objective_point_bearing_around_ship = float(scenario["objective_point_bearing_around_ship"])
        self.objective_point_multiplier = int(scenario["objective_point_multiplier"])

        try:
            self.objective_points = json.loads(scenario["objective_points_json"] or "[]")
        except Exception:
            self.objective_points = []

        if not self.objective_points:
            self.objective_points = [{
                "id": 1,
                "bearing": 0,
                "x": float(scenario["objective_point_x_nm"]),
                "y": float(scenario["objective_point_y_nm"])
            }]

        self.intercept_distance_nm = 1.0

        if objective_point_override is not None:
            self.selected_objective_point = objective_point_override
        else:
            self.selected_objective_point = self.choose_best_objective_point()

        self.objective_point_x_nm = float(self.selected_objective_point["x"])
        self.objective_point_y_nm = float(self.selected_objective_point["y"])
        self.trajectory = []
        self.record_trajectory()
        self.write_objective_point_analysis_file()
        
        self.current_message = ""
        self.messages = []
        self.result = "RUNNING"

        self.enable_logging = enable_logging

        if self.enable_logging:

            scenario_log_folder = os.path.join(
                "logs",
                f"id{scenario['id']}"
            )

            os.makedirs(
                scenario_log_folder,
                exist_ok=True
            )

            if log_suffix:
                self.log_file = os.path.join(
                    scenario_log_folder,
                    f"sim_{scenario['id']}_{log_suffix}.csv"
                )
            else:
                self.log_file = os.path.join(
                    scenario_log_folder,
                    f"sim_{scenario['id']}.csv"
                )

            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)

                writer.writerow([
                    "scenario_id",
                    "scenario_name",
                    "minute",
                    "ship_x_nm",
                    "ship_y_nm",
                    "torpedo_x_nm",
                    "torpedo_y_nm",
                    "selected_objective_point_id",
                    "selected_objective_point_bearing",
                    "objective_point_x_nm",
                    "objective_point_y_nm",
                    "separation_nm",
                    "distance_to_objective_point_nm",
                    "ship_speed_knots",
                    "torpedo_speed_knots",
                    "countermeasure_active",
                    "countermeasure_timer",
                    "torpedo_lost_contact_timer",
                    "result",
                    "message"
                ])

        else:
            self.log_file = None

        self.add_message(
            f"Simulation started. Best objective point selected: "
            f"Zone {self.selected_objective_point['id']} "
            f"at bearing {self.selected_objective_point['bearing']}°."
        )

        self.log_state()

    def choose_best_objective_point(self):

        outcomes = []

        for zone in self.objective_points:

            outcome = self.test_objective_point(zone)

            outcomes.append(outcome)

        successful = [
            item
            for item in outcomes
            if item["result"] == "SUCCESS"
        ]

        if successful:

            successful.sort(
                key=lambda item: (
                    item["ticks"],
                    -item["final_separation"]
                )
            )

            selected = successful[0]

        else:

            outcomes.sort(
                key=lambda item: (
                    -item["ticks"],
                    -item["final_separation"]
                )
            )

            selected = outcomes[0]

        selected_id = selected["zone"]["id"]

        for outcome in outcomes:

            if outcome["zone"]["id"] == selected_id:

                outcome["reason"] = (
                    "Selected because it achieved the best "
                    "survivability score."
                )

            elif outcome["result"] != "SUCCESS":

                outcome["reason"] = (
                    "Rejected because the torpedo intercepted "
                    "the ship before arrival."
                )

            else:

                outcome["reason"] = (
                    "Rejected because another objective_point "
                    "provided a better outcome."
                )

        self.objective_point_analysis = outcomes

        return selected["zone"]

    def test_objective_point(self, zone):
        ship_x = self.ship_start_x_nm
        ship_y = self.ship_start_y_nm

        torpedo_x = self.torpedo_start_x_nm
        torpedo_y = self.torpedo_start_y_nm

        safe_x = float(zone["x"])
        safe_y = float(zone["y"])

        tick = 0
        max_ticks = 10000

        while tick < max_ticks:
            tick += 1

            ship_move_nm = self.friendly_speed / 60.0
            torpedo_move_nm = self.enemy_speed / 60.0

            ship_x, ship_y = self.move_point_towards_static(
                ship_x,
                ship_y,
                safe_x,
                safe_y,
                ship_move_nm
            )

            torpedo_x, torpedo_y = self.move_point_towards_static(
                torpedo_x,
                torpedo_y,
                ship_x,
                ship_y,
                torpedo_move_nm
            )

            separation = self.distance_static(
                ship_x,
                ship_y,
                torpedo_x,
                torpedo_y
            )

            distance_to_objective_point = self.distance_static(
                ship_x,
                ship_y,
                safe_x,
                safe_y
            )

            if separation <= self.intercept_distance_nm:
                return {
                    "zone": zone,
                    "result": "FAILED",
                    "ticks": tick,
                    "final_separation": separation
                }

            if distance_to_objective_point <= 1:
                return {
                    "zone": zone,
                    "result": "SUCCESS",
                    "ticks": tick,
                    "final_separation": separation
                }

        return {
            "zone": zone,
            "result": "STOPPED",
            "ticks": max_ticks,
            "final_separation": self.distance_static(
                ship_x,
                ship_y,
                torpedo_x,
                torpedo_y
            )
        }

    def add_message(self, message):

        self.current_message = (
            f"Minute {self.tick_count}: {message}"
        )

        self.messages.append(self.current_message)

    def distance_between_ship_and_torpedo(self):
        return self.distance_static(
            self.ship_x_nm,
            self.ship_y_nm,
            self.torpedo_x_nm,
            self.torpedo_y_nm
        )

    def update_ship_speed(self):
        if self.friendly_speed < self.target_friendly_speed:
            self.friendly_speed += self.acceleration_knots_per_tick

            if self.friendly_speed > self.target_friendly_speed:
                self.friendly_speed = self.target_friendly_speed

        elif self.friendly_speed > self.target_friendly_speed:
            self.friendly_speed -= self.deceleration_knots_per_tick

            if self.friendly_speed < self.target_friendly_speed:
                self.friendly_speed = self.target_friendly_speed


    def update_manoeuvre_logic(self):
        distance = self.distance_between_ship_and_torpedo()

        self.update_ship_speed()

        if self.countermeasure_timer > 0:
            self.countermeasure_timer -= 1
            self.countermeasure_active = True
        else:
            self.countermeasure_active = False
            self.target_friendly_speed = self.original_friendly_speed

        if self.torpedo_lost_contact_timer > 0:
            self.torpedo_lost_contact_timer -= 1
            return

        ship_ready = (
            self.friendly_speed >=
            self.original_friendly_speed * self.minimum_manoeuvre_speed_ratio
        )

        if (
            distance <= self.manoeuvre_trigger_distance_nm
            and ship_ready
            and not self.countermeasure_active
        ):
            self.countermeasure_active = True
            self.countermeasure_timer = self.countermeasure_lifetime_seconds

            self.target_friendly_speed = (
                self.original_friendly_speed *
                (1 - self.countermeasure_speed_loss_ratio)
            )

            self.add_message(
                "Countermeasure deployed. Ship speed reduced during manoeuvre."
            )
            
    
            roll = random.random()

            if roll <= self.countermeasure_effectiveness:
                self.torpedo_lost_contact_timer = self.torpedo_lost_contact_duration
                self.add_message("Countermeasure successful. Torpedo lost contact.")
            else:
                self.add_message("Countermeasure failed. Torpedo maintained contact.")
                


    def tick(self):

        if self.finished:
            return

        self.tick_count += 1
        self.update_manoeuvre_logic()
        ship_move_nm = self.friendly_speed / 60.0
        torpedo_move_nm = self.enemy_speed / 60.0

        self.move_towards_ship_objective_point(ship_move_nm)

        self.move_torpedo_towards_ship(torpedo_move_nm)

        separation_nm = self.get_separation_nm()

        distance_to_objective_point_nm = (
            self.get_distance_to_objective_point_nm()
        )

        if separation_nm <= self.intercept_distance_nm:

            self.finished = True
            self.friendly_destroyed = True

            self.result = (
                "MISSION FAILED - "
                "TORPEDO INTERCEPTED SHIP"
            )

            self.add_message(
                f"Mission failed. "
                f"Torpedo intercepted ship "
                f"at {separation_nm} NM."
            )
            
            self.record_trajectory()
            self.log_state()
            return

        if (distance_to_objective_point_nm <= 1 and not self.friendly_destroyed):

            self.finished = True

            self.result = (
                "MISSION SUCCESS - "
                "SHIP REACHED Objective Point"
            )

            self.add_message(
                f"Mission success. "
                f"Ship reached Objective Point"
                f"{self.selected_objective_point['id']}."
            )

            self.record_trajectory()
            self.log_state()
            return

        self.add_message(
            f"Separation: {separation_nm} NM."
        )

        self.record_trajectory()
        self.log_state()

    def move_towards_ship_objective_point(self, move_nm):

        self.ship_x_nm, self.ship_y_nm = (
            self.move_point_towards(
                self.ship_x_nm,
                self.ship_y_nm,
                self.objective_point_x_nm,
                self.objective_point_y_nm,
                move_nm
            )
        )

    def move_torpedo_towards_ship(self, move_nm):

        if self.torpedo_lost_contact_timer > 0:
            return

        self.torpedo_x_nm, self.torpedo_y_nm = (
            self.move_point_towards(
                self.torpedo_x_nm,
                self.torpedo_y_nm,
                self.ship_x_nm,
                self.ship_y_nm,
                move_nm
            )
        )

    def move_point_towards(
        self,
        x,
        y,
        target_x,
        target_y,
        move_nm
    ):
        return self.move_point_towards_static(
            x,
            y,
            target_x,
            target_y,
            move_nm
        )

    @staticmethod
    def move_point_towards_static(
        x,
        y,
        target_x,
        target_y,
        move_nm
    ):

        dx = target_x - x
        dy = target_y - y

        distance = math.sqrt(dx ** 2 + dy ** 2)

        if distance == 0:
            return x, y

        if move_nm >= distance:
            return target_x, target_y

        new_x = x + (dx / distance) * move_nm
        new_y = y + (dy / distance) * move_nm

        return new_x, new_y

    @staticmethod
    def distance_static(x1, y1, x2, y2):
        return math.sqrt(
            (x1 - x2) ** 2 +
            (y1 - y2) ** 2
        )

    def get_separation_nm(self):

        return round(self.distance_static(
            self.ship_x_nm,
            self.ship_y_nm,
            self.torpedo_x_nm,
            self.torpedo_y_nm
        ), 2)

    def get_distance_to_objective_point_nm(self):

        return round(self.distance_static(
            self.objective_point_x_nm,
            self.objective_point_y_nm,
            self.ship_x_nm,
            self.ship_y_nm
        ), 2)

    def get_ship_bearing_to_objective_point(self):

        return self.get_bearing(
            self.ship_x_nm,
            self.ship_y_nm,
            self.objective_point_x_nm,
            self.objective_point_y_nm
        )

    def get_torpedo_bearing_to_ship(self):

        return self.get_bearing(
            self.torpedo_x_nm,
            self.torpedo_y_nm,
            self.ship_x_nm,
            self.ship_y_nm
        )

    def get_bearing(
        self,
        x1,
        y1,
        x2,
        y2
    ):

        dx = x2 - x1
        dy = y2 - y1

        angle = math.degrees(
            math.atan2(dx, dy)
        )

        bearing = (angle + 360) % 360

        return round(bearing)

    @property
    def plot_bounds(self):

        xs = [
            self.ship_x_nm,
            self.torpedo_x_nm,
            self.objective_point_x_nm
        ]

        ys = [
            self.ship_y_nm,
            self.torpedo_y_nm,
            self.objective_point_y_nm
        ]

        for zone in self.objective_points:
            xs.append(float(zone["x"]))
            ys.append(float(zone["y"]))

        padding = 10

        return {
            "min_x": min(xs) - padding,
            "max_x": max(xs) + padding,
            "min_y": min(ys) - padding,
            "max_y": max(ys) + padding
        }


    def write_objective_point_analysis_file(self):

        folder = os.path.join(
            "logs",
            f"id{self.scenario['id']}"
        )

        os.makedirs(folder, exist_ok=True)

        filename = os.path.join(
            folder,
            f"objective_point_analysis_{self.scenario['id']}.txt"
        )

        with open(filename, "w", encoding="utf-8") as f:

            f.write("Objective Points ANALYSIS\n")
            f.write("=" * 60 + "\n\n")

            f.write(
                f"Scenario: {self.scenario_name}\n"
            )

            f.write(
                f"Selected Objective Point: "
                f"{self.selected_objective_point['id']}\n\n"
            )

            for outcome in self.objective_point_analysis:

                zone = outcome["zone"]

                f.write("-" * 60 + "\n")

                f.write(
                    f"Objective Point {zone['id']}\n"
                )

                f.write(
                    f"Bearing: {zone['bearing']}°\n"
                )

                f.write(
                    f"Coordinates: "
                    f"({zone['x']}, {zone['y']})\n"
                )

                f.write(
                    f"Outcome: "
                    f"{outcome['result']}\n"
                )

                f.write(
                    f"Minutes: "
                    f"{outcome['ticks']}\n"
                )

                f.write(
                    f"Final Separation: "
                    f"{round(outcome['final_separation'],2)} NM\n"
                )

                f.write(
                    f"Reason: "
                    f"{outcome['reason']}\n\n"
                )

    def record_trajectory(self):
        self.trajectory.append({
            "minute": self.tick_count,

            "ship_x_nm": round(self.ship_x_nm, 2),
            "ship_y_nm": round(self.ship_y_nm, 2),
            "torpedo_x_nm": round(self.torpedo_x_nm, 2),
            "torpedo_y_nm": round(self.torpedo_y_nm, 2),

            "ship_distance_to_objective_point_nm": self.get_distance_to_objective_point_nm(),
            "torpedo_distance_to_ship_nm": self.get_separation_nm()
        })


    def log_state(self):

        if not self.enable_logging:
            return

        with open(self.log_file, "a", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                self.scenario["id"],
                self.scenario_name,
                self.tick_count,
                round(self.ship_x_nm, 2),
                round(self.ship_y_nm, 2),
                round(self.torpedo_x_nm, 2),
                round(self.torpedo_y_nm, 2),
                self.selected_objective_point["id"],
                self.selected_objective_point["bearing"],
                self.objective_point_x_nm,
                self.objective_point_y_nm,
                self.get_separation_nm(),
                self.get_distance_to_objective_point_nm(),
                self.friendly_speed,
                self.enemy_speed,
                "Y" if self.countermeasure_active else "N",
                self.countermeasure_timer,
                self.torpedo_lost_contact_timer,
                self.result,
                self.current_message
            ])