import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Scripts"
    / "CreateOldShopGreybox.py"
)


def load_generator():
    spec = importlib.util.spec_from_file_location("old_shop_generator", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GeometryScriptAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_outputs_expected_static_mesh_asset_path(self):
        self.assertEqual(
            "/Game/OldShop_500x800x400/SM_OldShop_500x800x400",
            self.generator.STATIC_MESH_ASSET_PATH,
        )

    def test_default_layout_has_unique_mesh_boxes_not_actor_parts(self):
        boxes = self.generator.build_box_specs()
        labels = [box.label for box in boxes]

        self.assertGreaterEqual(len(boxes), 68)
        self.assertEqual(len(boxes), len(set(labels)))
        self.assertEqual(15, sum("_Slat_" in label for label in labels))

    def test_default_layout_stays_inside_hard_envelope(self):
        boxes = self.generator.build_box_specs()
        envelope = self.generator.expected_envelope()

        self.generator.validate_box_specs(boxes, envelope)
        self.assertEqual(
            ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
            self.generator.overall_bounds(boxes),
        )

    def test_material_order_provides_seven_region_ids(self):
        self.assertEqual(
            [
                "M_OldWall",
                "M_DarkWall",
                "M_Shutter",
                "M_Sign",
                "M_DarkGlass",
                "M_Trim",
                "M_Stain",
            ],
            self.generator.MATERIAL_ORDER,
        )

        for material_index, material_name in enumerate(self.generator.MATERIAL_ORDER):
            self.assertEqual(
                material_index,
                self.generator.MATERIAL_ID_BY_NAME[material_name],
            )

    def test_key_shop_features_are_in_the_single_mesh_geometry(self):
        labels = {box.label for box in self.generator.build_box_specs()}

        required_labels = {
            "SM_OldShop_MainBlock",
            "SM_OldShop_Storefront",
            "SM_OldShop_Shutter",
            "SM_OldShop_RoofEdge_Front",
            "SM_OldShop_DoorFrame_Left",
            "SM_OldShop_Sign",
            "SM_OldShop_WindowGlass",
            "SM_OldShop_Side_DrainPipe",
            "SM_OldShop_Side_WindowGlass",
            "SM_OldShop_Side_ACUnit",
            "SM_OldShop_Side_WireBox",
            "SM_OldShop_Side_Stain_01",
        }

        self.assertTrue(required_labels.issubset(labels))

    def test_sign_uses_more_faded_dark_old_red(self):
        self.assertEqual(
            (0.20, 0.055, 0.045, 1.0),
            self.generator.MATERIAL_COLORS["M_Sign"],
        )

    def test_stain_material_is_gray_brown_not_near_black(self):
        red, green, blue, alpha = self.generator.MATERIAL_COLORS["M_Stain"]

        self.assertEqual(1.0, alpha)
        self.assertGreaterEqual(red + green + blue, 0.55)
        self.assertGreater(red, blue)
        self.assertGreater(green, blue)

    def test_stain_and_dirt_patches_are_at_least_one_cm_thick(self):
        boxes = self.generator.build_box_specs()
        patch_tokens = ("Stain", "FadedPatch", "Rust", "Dirt")

        for box in boxes:
            if any(token in box.label for token in patch_tokens):
                self.assertGreaterEqual(
                    min(box.size_cm),
                    1.0,
                    f"{box.label} is thinner than 1 cm",
                )

    def test_visible_outer_faces_do_not_share_coplanar_overlapping_surfaces(self):
        boxes = self.generator.build_box_specs()
        conflicts = []

        checks = [
            (1, "minimum", (0, 2), lambda b: self.generator.box_bounds(b)[1][0] <= -378.0),
            (1, "maximum", (0, 2), lambda b: self.generator.box_bounds(b)[1][1] >= 398.0),
            (0, "maximum", (1, 2), lambda b: self.generator.box_bounds(b)[0][1] >= 248.0),
            (0, "minimum", (1, 2), lambda b: self.generator.box_bounds(b)[0][0] <= -248.0),
            (2, "maximum", (0, 1), lambda b: self.generator.box_bounds(b)[2][1] >= 397.0),
        ]

        for plane_axis, visible_side, projection_axes, selector in checks:
            conflicts.extend(
                self._find_visible_plane_conflicts(
                    [box for box in boxes if selector(box)],
                    plane_axis=plane_axis,
                    visible_side=visible_side,
                    projection_axes=projection_axes,
                )
            )

        self.assertEqual([], conflicts)

    def _find_visible_plane_conflicts(
        self,
        boxes,
        plane_axis,
        visible_side,
        projection_axes,
    ):
        conflicts = []
        bounds_by_label = {
            box.label: self.generator.box_bounds(box)
            for box in boxes
        }

        for index, first in enumerate(boxes):
            first_bounds = bounds_by_label[first.label]
            first_plane = first_bounds[plane_axis][
                0 if visible_side == "minimum" else 1
            ]

            for second in boxes[index + 1:]:
                second_bounds = bounds_by_label[second.label]
                second_plane = second_bounds[plane_axis][
                    0 if visible_side == "minimum" else 1
                ]
                if abs(first_plane - second_plane) > 0.001:
                    continue

                if all(
                    self._interval_overlap(
                        first_bounds[axis],
                        second_bounds[axis],
                    )
                    > 0.001
                    for axis in projection_axes
                ):
                    conflicts.append(
                        f"{first.label} <-> {second.label} at {first_plane}"
                    )

        return conflicts

    @staticmethod
    def _interval_overlap(first, second):
        return min(first[1], second[1]) - max(first[0], second[0])

    def test_overall_parameters_scale_every_box_and_keep_base_z(self):
        boxes = self.generator.build_box_specs(
            width_cm=1000.0,
            depth_cm=400.0,
            height_cm=200.0,
            origin_x_cm=50.0,
            origin_y_cm=-25.0,
            base_z_cm=11.0,
        )
        bounds = self.generator.overall_bounds(boxes)

        self.assertEqual(
            ((-450.0, 550.0), (-225.0, 175.0), (11.0, 211.0)),
            bounds,
        )

    def test_duplicate_label_is_rejected_before_editor_work(self):
        boxes = self.generator.build_box_specs()
        duplicate = list(boxes) + [boxes[0]]

        with self.assertRaisesRegex(ValueError, "重复"):
            self.generator.validate_box_specs(
                duplicate,
                self.generator.expected_envelope(),
            )

    def test_out_of_bounds_box_reports_label_and_axis(self):
        boxes = self.generator.build_box_specs()
        bad_box = self.generator.MeshBoxSpec(
            label="SM_OldShop_Bad",
            location_cm=(251.0, 0.0, 100.0),
            size_cm=(2.0, 2.0, 2.0),
            material_name="M_Trim",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"SM_OldShop_Bad.*X.*250",
        ):
            self.generator.validate_box_specs(
                boxes + [bad_box],
                self.generator.expected_envelope(),
            )


if __name__ == "__main__":
    unittest.main()
