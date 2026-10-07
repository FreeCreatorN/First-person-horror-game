import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from Scripts.OldTownFurnitureAudit import SUPPORTS, validate_bounds, world_bounds
from Scripts.OldTownFurnitureAudit import audit_actors
from Scripts.OldTownFurnitureAudit import validate_end_window_bounds


class FurnitureAuditTests(unittest.TestCase):
    def fixture(self):
        result = {}
        for i, (label, (z, footprint)) in enumerate(SUPPORTS.items()):
            x0, y0, x1, y1 = footprint
            x = x0 + 2 + i * 3
            result[label] = ((x, y0 + 2, z), (x + 1, y0 + 3, z + 1))
        return result

    def test_supported_objects_pass(self):
        self.assertEqual(len(validate_bounds(self.fixture())), 8)

    def test_floating_object_fails(self):
        bounds = self.fixture()
        key = next(iter(bounds))
        lo, hi = bounds[key]
        bounds[key] = ((lo[0], lo[1], lo[2] + 70), (hi[0], hi[1], hi[2] + 70))
        with self.assertRaisesRegex(ValueError, "support gap"):
            validate_bounds(bounds)

    def test_overhang_fails(self):
        bounds = self.fixture()
        key = next(iter(bounds))
        lo, hi = bounds[key]
        bounds[key] = ((0, lo[1], lo[2]), hi)
        with self.assertRaisesRegex(ValueError, "overhangs"):
            validate_bounds(bounds)

    def test_overlapping_objects_fail(self):
        bounds = self.fixture()
        bounds["OTS_MainHomeProp_Thermos"] = bounds["OTS_P5Prop_MainHomeCounterDisplayLeft"]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_bounds(bounds)

    def test_missing_furniture_fails(self):
        with self.assertRaisesRegex(ValueError, "Missing"):
            validate_bounds({})

    def test_rotated_scaled_bounds(self):
        lo, hi = world_bounds((-1, -2, 0), (1, 2, 3), (10, 20, 1), (2, 3, 4), 90)
        for actual, expected in zip(lo + hi, (4, 18, 1, 16, 22, 13)):
            self.assertAlmostEqual(actual, expected)

    def mock_actor(self):
        actor = MagicMock()
        actor.get_actor_label.return_value = "OTS_P5Prop_MainHomeShopShelf_01"
        vector = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        actor.get_component_by_class.return_value.get_local_bounds.return_value = (
            vector(-148, -21, -70), vector(148, 17, 240))
        actor.get_actor_location.return_value = vector(1025, 1265, 80)
        actor.get_actor_scale3d.return_value = vector(1, 1, 1)
        actor.get_actor_rotation.return_value = SimpleNamespace(pitch=0, yaw=0, roll=0)
        return actor

    def test_scene_unique_suffix_is_recognized(self):
        with patch.dict("sys.modules", {"unreal": MagicMock()}), patch(
                "Scripts.OldTownFurnitureAudit.validate_bounds", side_effect=lambda b: b):
            result = audit_actors([self.mock_actor()])
        self.assertEqual(result["OTS_P5Prop_MainHomeShopShelf"][0][2], 10)

    def test_duplicate_actor_is_rejected(self):
        with patch.dict("sys.modules", {"unreal": MagicMock()}):
            with self.assertRaisesRegex(ValueError, "Duplicate furniture"):
                audit_actors([self.mock_actor(), self.mock_actor()])

    def test_old_overlapping_end_window_is_rejected(self):
        bounds = {
            "OTS_StreetEndWindow_North_01_01": ((5981, 1770, 264), (6099, 1785, 396)),
            "OTS_StreetEndWindow_South_01_01": ((6121, -1785, 264), (6239, -1770, 396)),
            "OTS_PerimeterWindowSouth04_R1_C3_01": ((6165, -1785, 200), (6285, -1770, 320)),
        }
        with self.assertRaisesRegex(ValueError, "Facade windows overlap"):
            validate_end_window_bounds(bounds)
        bounds["OTS_StreetEndWindow_South_01_01"] = ((5981, -1785, 264), (6099, -1770, 396))
        self.assertEqual(validate_end_window_bounds(bounds)["overlaps"], 0)


if __name__ == "__main__":
    unittest.main()
