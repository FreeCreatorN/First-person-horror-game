import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "Scripts" / "CreateEnterableMainHome.py"
)


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "create_enterable_main_home", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load generator from {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EnterableMainHomeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_asset_path_is_isolated_from_old_shop(self):
        self.assertEqual(
            "/Game/MainHome/SM_MainHome_Enterable",
            self.generator.STATIC_MESH_ASSET_PATH,
        )

    def test_exact_envelope(self):
        boxes = self.generator.build_box_specs()
        self.generator.validate_design(boxes)
        self.assertEqual(
            ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
            self.generator.overall_bounds(boxes),
        )

    def test_two_real_doorway_clearances(self):
        doors = self.generator.build_doorway_specs()
        self.assertEqual(
            [
                ((-218.0, -400.0, 11.0), (-22.0, -350.0, 291.0)),
                ((22.0, -400.0, 11.0), (218.0, -350.0, 291.0)),
            ],
            [(door.minimum_cm, door.maximum_cm) for door in doors],
        )
        self.assertEqual([196.0, 196.0], [door.width_cm for door in doors])
        self.assertEqual([280.0, 280.0], [door.height_cm for door in doors])
        structural = [
            box for box in self.generator.build_box_specs() if box.collision
        ]
        for door in doors:
            self.assertFalse(
                any(
                    self.generator.boxes_overlap_open_volume(box, door)
                    for box in structural
                )
            )

    def test_interior_is_empty_and_left_right_connected(self):
        structural = [
            box for box in self.generator.build_box_specs() if box.collision
        ]
        for point in (
            (-150.0, 0.0, 120.0),
            (0.0, 0.0, 120.0),
            (150.0, 0.0, 120.0),
        ):
            self.assertFalse(
                any(
                    self.generator.point_inside_box(point, box)
                    for box in structural
                )
            )

    def test_only_structure_has_collision(self):
        boxes = self.generator.build_box_specs()
        self.assertTrue(
            all(box.collision for box in boxes if box.category == "structure")
        )
        self.assertTrue(
            all(not box.collision for box in boxes if box.category != "structure")
        )

    def test_inner_lining_uses_interior_material_on_four_surfaces(self):
        boxes_by_label = {
            box.label: box for box in self.generator.build_box_specs()
        }
        expected_bounds = {
            "Interior_Left": ((-230.0, -229.0), (-380.0, 380.0), (11.0, 351.0)),
            "Interior_Right": ((229.0, 230.0), (-380.0, 380.0), (11.0, 351.0)),
            "Interior_Back": ((-230.0, 230.0), (379.0, 380.0), (11.0, 351.0)),
            "Interior_Ceiling": ((-230.0, 230.0), (-380.0, 380.0), (350.0, 351.0)),
        }

        for label, bounds in expected_bounds.items():
            lining = boxes_by_label[label]
            self.assertEqual("M_MainHome_Interior", lining.material_name)
            self.assertEqual("lining", lining.category)
            self.assertFalse(lining.collision)
            self.assertEqual(bounds, self.generator.box_bounds(lining))

    def test_sign_contains_low_poly_chinese_letter_geometry(self):
        letters = [
            box
            for box in self.generator.build_box_specs()
            if box.category == "letter"
        ]
        self.assertGreaterEqual(len(letters), 45)
        self.assertEqual(len(letters), len({box.label for box in letters}))
        self.assertTrue(
            all(box.material_name == "M_MainHome_Letters" for box in letters)
        )

    def test_material_ids_are_contiguous(self):
        self.assertEqual(
            list(range(7)),
            list(self.generator.MATERIAL_ID_BY_NAME.values()),
        )

    def test_letters_are_dark_red_and_stains_remain_visible(self):
        settings = self.generator.MATERIAL_SETTINGS
        self.assertEqual(
            (0.30, 0.07, 0.045, 1.0),
            settings["M_MainHome_Letters"][0],
        )
        self.assertEqual(
            (0.22, 0.18, 0.14, 1.0),
            settings["M_MainHome_Stain"][0],
        )

    def test_geometry_script_enables_material_ids_before_append(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertLess(source.index("enable_material_ids"), source.index("append_box("))

    def test_collision_uses_separate_aligned_box_mesh(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("set_static_mesh_collision_from_mesh", source)
        self.assertIn("ALIGNED_BOXES", source)
        self.assertNotIn("append_box_with_collision", source)

    def test_existing_asset_is_updated_without_force_delete(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("copy_mesh_to_static_mesh", source)
        self.assertNotIn("delete_asset(STATIC_MESH_ASSET_PATH", source)

    def test_validation_rejects_duplicate_labels(self):
        boxes = self.generator.build_box_specs()
        with self.assertRaises(ValueError):
            self.generator.validate_design(boxes + [boxes[0]])

    def test_validation_rejects_unknown_materials(self):
        boxes = self.generator.build_box_specs()
        boxes[0] = replace(boxes[0], material_name="M_MainHome_Unknown")
        with self.assertRaises(ValueError):
            self.generator.validate_design(boxes)

    def test_validation_rejects_non_positive_sizes(self):
        boxes = self.generator.build_box_specs()
        boxes[0] = replace(boxes[0], size_cm=(0.0, 800.0, 10.0))
        with self.assertRaises(ValueError):
            self.generator.validate_design(boxes)

    def test_validation_rejects_envelope_overflow(self):
        boxes = self.generator.build_box_specs()
        boxes[0] = replace(boxes[0], location_cm=(1.0, 0.0, 6.0))
        with self.assertRaises(ValueError):
            self.generator.validate_design(boxes)

    def test_validation_rejects_structure_inside_a_doorway(self):
        boxes = self.generator.build_box_specs()
        boxes.append(
            self.generator.BoxSpec(
                "Door_Blocker",
                (-120.0, -375.0, 151.0),
                (10.0, 10.0, 10.0),
                "M_MainHome_Wall",
                "structure",
                True,
            )
        )
        with self.assertRaises(ValueError):
            self.generator.validate_design(boxes)


if __name__ == "__main__":
    unittest.main()
