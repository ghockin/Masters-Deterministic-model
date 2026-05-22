import csv
import math
import os


class SimulationState:
    def __init__(
        self,
        scenario,
        ship_speed_override=None,
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

        self.ship_x_nm = float(scenario["ship_start_x_nm"])
        self.ship_y_nm = float(scenario["ship_start_y_nm"])

        self.ship_speed_min = float(scenario["ship_speed_min"])
        self.ship_speed_max = float(scenario["ship_speed_max"])

        self.safe_zone_x_nm = float(scenario["safe_zone_x_nm"])
        self.safe_zone_y_nm = float(scenario["safe_zone_y_nm"])

        self.torpedo_x_nm = float(scenario["torpedo_start_x_nm"])
        self.torpedo_y_nm = float(scenario["torpedo_start_y_nm"])

        self.friendly_speed = (
            float(ship_speed_override)
            if ship_speed_override is not None
            else self.ship_speed_min
        )

        self.enemy_speed = float(scenario["torpedo_speed"])

        self.intercept_distance_nm = 1.0

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
                    "safe_zone_x_nm",
                    "safe_zone_y_nm",
                    "separation_nm",
                    "distance_to_safe_zone_nm",
                    "ship_speed_knots",
                    "torpedo_speed_knots",
                    "result",
                    "message"
                ])

        else:
            self.log_file = None

        self.add_message("Simulation started.")
        self.log_state()

    def add_message(self, message):

        self.current_message = (
            f"Minute {self.tick_count}: {message}"
        )

        self.messages.append(self.current_message)

    def tick(self):

        if self.finished:
            return

        self.tick_count += 1

        ship_move_nm = self.friendly_speed / 60.0
        torpedo_move_nm = self.enemy_speed / 60.0

        self.move_towards_ship_safe_zone(ship_move_nm)

        self.move_torpedo_towards_ship(torpedo_move_nm)

        separation_nm = self.get_separation_nm()

        distance_to_safe_zone_nm = (
            self.get_distance_to_safe_zone_nm()
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

            self.log_state()
            return

        if distance_to_safe_zone_nm <= 1:

            self.finished = True

            self.result = (
                "MISSION SUCCESS - "
                "SHIP REACHED SAFE ZONE"
            )

            self.add_message(
                "Mission success. "
                "Ship reached safe zone."
            )

            self.log_state()
            return

        self.add_message(
            f"Separation: {separation_nm} NM."
        )

        self.log_state()

    def move_towards_ship_safe_zone(self, move_nm):

        self.ship_x_nm, self.ship_y_nm = (
            self.move_point_towards(
                self.ship_x_nm,
                self.ship_y_nm,
                self.safe_zone_x_nm,
                self.safe_zone_y_nm,
                move_nm
            )
        )

    def move_torpedo_towards_ship(self, move_nm):

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

    def get_separation_nm(self):

        return round(math.sqrt(
            (self.ship_x_nm - self.torpedo_x_nm) ** 2 +
            (self.ship_y_nm - self.torpedo_y_nm) ** 2
        ), 2)

    def get_distance_to_safe_zone_nm(self):

        return round(math.sqrt(
            (self.safe_zone_x_nm - self.ship_x_nm) ** 2 +
            (self.safe_zone_y_nm - self.ship_y_nm) ** 2
        ), 2)

    def get_ship_bearing_to_safe_zone(self):

        return self.get_bearing(
            self.ship_x_nm,
            self.ship_y_nm,
            self.safe_zone_x_nm,
            self.safe_zone_y_nm
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

        max_x = max(
            self.ship_x_nm,
            self.torpedo_x_nm,
            self.safe_zone_x_nm,
            100
        )

        max_y = max(
            self.ship_y_nm,
            self.torpedo_y_nm,
            self.safe_zone_y_nm,
            100
        )

        return {
            "min_x": 0,
            "max_x": max_x,
            "min_y": 0,
            "max_y": max_y
        }

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
                self.safe_zone_x_nm,
                self.safe_zone_y_nm,
                self.get_separation_nm(),
                self.get_distance_to_safe_zone_nm(),
                self.friendly_speed,
                self.enemy_speed,
                self.result,
                self.current_message
            ])