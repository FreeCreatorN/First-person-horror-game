"""Geometry checks for guest-room connections and preserved street routes."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts"))

from OldTownHotelPlan import build_hotel_plan, validate_hotel_plan
from OldTownRoadLayoutRevision import plan_road_layout


BUILDING = {
    "label": "OTS_PerimeterBoundaryEast_01",
    "world_min": [9000., -3500., 0.], "world_max": [10040., 3500., 1500.],
    "interior_min": [9020., -3480., 11.], "interior_max": [10020., 3480., 1480.],
    "floor_z": [11., 378.25, 745.5, 1112.75],
    "door_width_cm": 140., "door_height_cm": 230.,
    "primary_entry_route": [[8890., 158., 11.], [9125., 158., 11.]],
    "ground_route": [[9125., 158., 11.], [9350., 158., 11.],
                     [9350., 3225., 11.], [9482., 3225., 11.]],
    "stair_keepout": {"min": [9407., 3105., 11.], "max": [10015., 3505., 1500.]},
}


def intersects(a, b):
    return all(min(a["world_max"][i], b["world_max"][i])
               - max(a["world_min"][i], b["world_min"][i]) > .01 for i in range(3))


class HotelGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = build_hotel_plan(BUILDING)

    def test_real_floors_and_existing_entry_are_preserved(self):
        self.assertEqual(self.plan["floor_z_cm"], BUILDING["floor_z"])
        self.assertEqual(self.plan["exterior_entry"]["width_cm"], 140.)
        self.assertEqual(self.plan["exterior_entry"]["route"], BUILDING["primary_entry_route"])
        self.assertEqual(self.plan["validation"]["status"], "PASS")
        self.assertGreater(self.plan["validation"]["minimum_fixed_box_path_clearance_cm"], 0.)

    def test_all_twenty_four_rooms_have_one_door_and_window(self):
        rooms = self.plan["guest_rooms"]
        self.assertEqual(len(rooms), 24)
        self.assertEqual({floor: sum(r["floor"] == floor for r in rooms) for floor in (1, 2, 3)},
                         {1: 8, 2: 8, 3: 8})
        self.assertEqual(len({r["door_id"] for r in rooms}), 24)
        self.assertEqual(len({r["window_id"] for r in rooms}), 24)
        for room in rooms:
            doors = [d for d in self.plan["room_doors"] if d["door_id"] == room["door_id"]]
            windows = [w for w in self.plan["guest_windows"] if w["window_id"] == room["window_id"]]
            self.assertEqual(len(doors), 1)
            self.assertEqual(len(windows), 1)
            self.assertEqual(windows[0]["room_id"], room["id"])
            self.assertGreaterEqual(doors[0]["minimum_clear_opening_cm"], 68.)
            self.assertEqual(doors[0]["width_cm"], 90.)
            self.assertEqual(doors[0]["height_cm"], 200.)

    def test_front_wall_segments_leave_the_full_door_aperture_open(self):
        for door in self.plan["room_doors"]:
            opening = {"world_min": door["opening_min"], "world_max": door["opening_max"]}
            parts = [b for b in self.plan["boxes"] if b["name"] in door["fixed_wall_actor_names"]]
            self.assertEqual(len(parts), 3)
            self.assertFalse(any(intersects(opening, b) for b in parts))
            # A blocked-wall control proves the aperture is real, not a missing room wall.
            blocked_point = [door["pivot_cm"][0], door["opening_min"][1] - 20., door["opening_min"][2] + 100.]
            self.assertTrue(any(all(b["world_min"][i] < blocked_point[i] < b["world_max"][i]
                                    for i in range(3)) for b in parts))

    def test_rear_window_cuts_cross_only_external_wall_thickness(self):
        for window in self.plan["guest_windows"]:
            room = next(r for r in self.plan["rooms"] if r["id"] == window["room_id"])
            self.assertEqual(window["wall"], "Rear")
            self.assertEqual(window["world_min"][0], 10019.5)
            self.assertEqual(window["world_max"][0], 10040.5)
            self.assertGreater(window["world_min"][1], room["world_min"][1])
            self.assertLess(window["world_max"][1], room["world_max"][1])
            self.assertGreater(window["world_min"][2], room["world_min"][2] + 100.)
            self.assertLess(window["world_max"][2], room["world_max"][2])
            self.assertFalse(any(intersects(window, b) for b in self.plan["boxes"]
                                 if b.get("floor") == room["floor"] and b["collision"]))

    def test_corridors_and_original_north_stair_keepout_have_no_fixed_props(self):
        corridors = [r for r in self.plan["corridor_keepouts"] if r["name"].endswith("Corridor")]
        self.assertEqual(len(corridors), 3)
        self.assertTrue(all(r["world_max"][0] - r["world_min"][0] >= 230. for r in corridors))
        for reserved in self.plan["corridor_keepouts"]:
            self.assertFalse(any(intersects(reserved, b) for b in self.plan["boxes"]
                                 if b["category"] != "ground" and b["collision"]), reserved["name"])

    def test_room_and_outdoor_paths_detect_a_real_obstruction(self):
        corrupted = copy.deepcopy(self.plan)
        route = next(r for r in corrupted["routes"] if r["name"] == "Hotel_Room_201_Entry")
        point = route["points"][1]
        corrupted["boxes"].append({"name": "BlockingControl", "collision": True,
                                    "category": "hotel_interior",
                                    "world_min": [point[0] - 40., point[1] - 40., point[2]],
                                    "world_max": [point[0] + 40., point[1] + 40., point[2] + 190.]})
        failed = validate_hotel_plan(corrupted)
        self.assertEqual(failed["status"], "FAIL")
        self.assertTrue(any(f["kind"] == "capsule_path_blocked" for f in failed["failures"]))

    def test_room_beds_and_tables_keep_adult_dimensions(self):
        beds = [b for b in self.plan["boxes"] if b["role"] == "GuestBedBase"]
        desks = [b for b in self.plan["boxes"] if b["role"] == "GuestDeskTop"]
        self.assertEqual(len(beds), 24)
        self.assertEqual(len(desks), 24)
        self.assertTrue(all([b["world_max"][i] - b["world_min"][i] for i in (0, 1)] == [150., 210.]
                            for b in beds))
        self.assertTrue(all(b["world_max"][2] - BUILDING["floor_z"][b["floor"]] == 80. for b in desks))

    def test_input_from_current_saved_report_and_converter_agree(self):
        from ConvertOldTownBuildings import plan_buildings
        plan_path = ROOT / "Saved/CodexOutputs/EnterableStreet_20261002/RevisionPlan.json"
        revision = json.loads(plan_path.read_text(encoding="utf-8"))
        building = next(b for b in plan_buildings([], revision) if b.label == BUILDING["label"])
        generated = build_hotel_plan(building)
        self.assertEqual(generated["rooms"], self.plan["rooms"])
        self.assertEqual(generated["guest_windows"], self.plan["guest_windows"])


class RoofCapTranslationRegressionTests(unittest.TestCase):
    def test_eight_real_roof_caps_follow_their_moved_buildings(self):
        source_path = ROOT / "Saved/CodexOutputs/EnterableStreet_20261002/SourceInventory.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        planned = plan_road_layout(source)
        translated = {r["label"]: r for r in planned["translated_inventory"]["actors"]}
        for side in ("North", "South"):
            for index in range(1, 5):
                stem = "%s%02d_01" % (side, index)
                roof_name = "OTS_PerimeterRoofCap" + stem
                building_name = "OTS_PerimeterBackdrop" + stem
                self.assertEqual(planned["actor_translations"][roof_name],
                                 planned["actor_translations"][building_name])
                roof = translated[roof_name]["meshes"][0]
                mass = translated[building_name]["meshes"][0]
                for axis in (0, 1):
                    roof_low = roof["world_origin"][axis] - roof["world_extent"][axis]
                    roof_high = roof["world_origin"][axis] + roof["world_extent"][axis]
                    wall_low = mass["world_origin"][axis] - mass["world_extent"][axis]
                    wall_high = mass["world_origin"][axis] + mass["world_extent"][axis]
                    self.assertAlmostEqual(wall_low - roof_low, 10.)
                    self.assertAlmostEqual(roof_high - wall_high, 10.)


if __name__ == "__main__":
    unittest.main()
