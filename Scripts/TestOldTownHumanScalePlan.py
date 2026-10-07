"""Independent contact and ergonomic invariants for the data-only scale plan."""
import unittest

from OldTownHumanScalePlan import HUMAN, VALIDATION_CAPSULE, chair_height, target_parts


class HumanScalePlanTests(unittest.TestCase):
    def setUp(self):
        self.parts = {p["name"].replace("SM_OTS_Blender_", ""): p for p in target_parts()}

    def test_eight_parts_and_floor_pivots(self):
        self.assertEqual(len(self.parts), 8)
        for name in ("BedFrame", "OldWoodTable", "OldWoodChair", "WardrobeCase"):
            self.assertEqual(self.parts[name]["target_offset_cm"][2], 0.0)

    def test_mattress_pillow_contact_and_containment(self):
        mattress, pillow = self.parts["BedMattress"], self.parts["BedPillow"]
        self.assertAlmostEqual(mattress["target_offset_cm"][2], 44.0)
        mattress_top = mattress["target_offset_cm"][2] + mattress["target_dimensions_cm"][2]
        self.assertAlmostEqual(mattress_top, 59.0)
        self.assertAlmostEqual(pillow["target_offset_cm"][2], mattress_top)
        for axis in (0, 1):
            self.assertLessEqual(abs(pillow["target_offset_cm"][axis]) + pillow["target_dimensions_cm"][axis] / 2,
                                 mattress["target_dimensions_cm"][axis] / 2)

    def test_chair_seat_and_visual_body_width(self):
        self.assertAlmostEqual(chair_height(47.0), 48.0)
        self.assertAlmostEqual(chair_height(92.0), 100.0)
        self.assertGreater(self.parts["OldWoodChair"]["target_dimensions_cm"][0], HUMAN["shoulder_width_cm"])
        self.assertEqual(VALIDATION_CAPSULE["diameter_cm"], 68.0)

    def test_hinges_remain_symmetric_and_above_floor(self):
        left, right = self.parts["WardrobeDoorL"], self.parts["WardrobeDoorR"]
        self.assertAlmostEqual(left["target_offset_cm"][0], -right["target_offset_cm"][0])
        self.assertEqual(left["target_offset_cm"][1:], right["target_offset_cm"][1:])
        self.assertGreater(left["target_offset_cm"][2], 0.0)
        self.assertEqual(left["target_dimensions_cm"], right["target_dimensions_cm"])


if __name__ == "__main__":
    unittest.main()
