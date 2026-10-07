import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT / "Scripts" / "ValidateOldTownSchoolStreet.py"
SCENE_BUILDER_PATH = (
    PROJECT_ROOT / "Scripts" / "CreateOldTownSchoolStreetScene.py"
)
EXPECTED_SOURCE_MAP_SHA256 = (
    "D15F1749800233495469ACB72E60A7C0D837319EECF57FB14BFF25FDBBD9DE09"
)


def _module_constants(tree):
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
    return constants


def _report_keys(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "report":
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        return {
            ast.literal_eval(key)
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    raise AssertionError("Validation report dictionary was not found")


class OldTownSchoolStreetValidatorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.builder_source = SCENE_BUILDER_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.constants = _module_constants(cls.tree)

    def test_player_start_contract_checks_location_and_yaw(self):
        self.assertIn(
            "abs(player_location.x + 1800.0) < 0.1",
            self.source,
        )
        self.assertIn(
            "abs(player_location.y) < 0.1",
            self.source,
        )
        self.assertIn(
            "abs(player_location.z - 105.0) < 0.1",
            self.source,
        )
        self.assertIn(
            "abs(float(player_rotation.yaw) - 10.0) < 0.1",
            self.source,
        )

    def test_protected_source_map_hash_is_exactly_asserted(self):
        self.assertEqual(
            EXPECTED_SOURCE_MAP_SHA256,
            self.constants["EXPECTED_SOURCE_MAP_SHA256"],
        )
        self.assertIn(
            "source_map_sha256.lower() == EXPECTED_SOURCE_MAP_SHA256.lower()",
            self.source,
        )

    def test_five_comparison_cameras_must_each_be_unique(self):
        self.assertEqual(
            (
                "CAM_OTS_Hero",
                "CAM_OTS_MainHome",
                "CAM_OTS_Alley",
                "CAM_OTS_StreetDiagonal",
                "CAM_OTS_TopDown",
            ),
            self.constants["CAMERA_LABELS"],
        )
        self.assertIn(
            "all(labels.count(label) == 1 for label in CAMERA_LABELS)",
            self.source,
        )

    def test_p2_contract_is_twenty_assets_and_sixty_one_instances(self):
        expected_counts = self.constants["EXPECTED_P2_MESH_COUNTS"]
        self.assertEqual(20, len(expected_counts))
        self.assertEqual(61, sum(expected_counts.values()))
        self.assertIn(
            "len(detailed_prop_assets) == len(EXPECTED_P2_MESH_COUNTS)",
            self.source,
        )
        self.assertIn(
            "len(detailed_prop_actors) == "
            "sum(EXPECTED_P2_MESH_COUNTS.values())",
            self.source,
        )

    def test_p3_contract_is_ten_assets_and_thirty_three_instances(self):
        expected_counts = self.constants["EXPECTED_P3_MESH_COUNTS"]
        self.assertEqual(10, len(expected_counts))
        self.assertEqual(33, sum(expected_counts.values()))
        self.assertEqual(
            {
                "SM_P3_SchoolGateLeaf",
                "SM_P3_SchoolGatePost",
            },
            self.constants["EXPECTED_P3_COLLISION_MESHES"],
        )
        self.assertIn(
            "len(p3_module_actors) == "
            "sum(EXPECTED_P3_MESH_COUNTS.values())",
            self.source,
        )

    def test_p5_contract_is_six_assets_and_fifteen_nonblocking_instances(self):
        expected_counts = self.constants["EXPECTED_P5_MESH_COUNTS"]
        self.assertEqual(6, len(expected_counts))
        self.assertEqual(15, sum(expected_counts.values()))
        self.assertEqual(
            {
                "SM_P5_LoadedLaundryRack": 5,
                "SM_P5_OldServiceDoorTransom": 3,
                "SM_P5_WallLampGooseneck": 3,
                "SM_P5_ShopShelfStocked": 1,
                "SM_P5_CounterDisplay": 2,
                "SM_P5_TallPharmacyCabinet": 1,
            },
            expected_counts,
        )
        self.assertIn(
            "len(p5_module_actors) == "
            "sum(EXPECTED_P5_MESH_COUNTS.values())",
            self.source,
        )
        self.assertIn(
            "P5 module must remain collision-free",
            self.source,
        )

    def test_p5_material_variants_require_twenty_eight_materials(self):
        self.assertEqual(28, self.constants["EXPECTED_MATERIAL_COUNT"])
        self.assertIn("M_OTS_FadedBlueMetal", self.builder_source)
        self.assertIn("M_OTS_FadedRedMetal", self.builder_source)

    def test_wall_antitiling_uses_shared_noise_instead_of_fixed_weight(self):
        self.assertNotIn(
            "scale_weight = constant_scalar(material, 0.34",
            self.builder_source,
        )
        for marker in (
            "OTS_WALL_BLEND_NOISE",
            "OTS_WALL_SCALE_ALPHA",
            "OTS_WALL_AGE_ALPHA",
            '"wall_anti_tiling_mode": "shared_world_noise_blend"',
        ):
            self.assertIn(marker, self.builder_source)

    def test_street_end_is_a_walkable_t_junction_not_a_flat_apartment(self):
        for marker in (
            "OTS_StreetEndTJunctionRoadCenter",
            "OTS_StreetEndTJunctionRoadNorth",
            "OTS_StreetEndTJunctionRoadSouth",
            "OTS_StreetEndFocalFacade",
            '"walkable_short_t_junction": True',
        ):
            self.assertIn(marker, self.builder_source)
        self.assertNotIn("\"OTS_StreetEndApartment\"", self.builder_source)

    def test_material_upgrade_requires_all_twelve_source_textures(self):
        expected_textures = self.constants["EXPECTED_SOURCE_TEXTURES"]
        self.assertEqual(12, len(expected_textures))
        self.assertTrue(
            {
                "T_OTS_PaintedPlaster_BaseColor",
                "T_OTS_PaintedPlaster_Normal",
                "T_OTS_PaintedPlaster_Roughness",
                "T_OTS_GreenMetalRust_BaseColor",
                "T_OTS_GreenMetalRust_Normal",
                "T_OTS_GreenMetalRust_Roughness",
            }.issubset(expected_textures)
        )

    def test_report_keeps_existing_fields_and_adds_new_audit_counts(self):
        report_keys = _report_keys(self.tree)
        existing_fields = {
            "status",
            "target_level",
            "world_path",
            "actor_count",
            "generated_actor_count",
            "player_start_location",
            "main_home_location",
            "main_home_components",
            "main_home_mesh_sections",
            "interaction_zones",
            "camera_count",
            "material_count",
            "texture_count",
            "pole_asset_count",
            "screenshots",
            "source_map_sha256",
        }
        self.assertTrue(existing_fields.issubset(report_keys))
        self.assertTrue(
            {
                "player_start_rotation_pitch_yaw_roll",
                "p2_detailed_prop_asset_count",
                "p2_detailed_prop_actor_count",
                "p2_detailed_prop_distribution",
                "p3_module_asset_count",
                "p3_module_actor_count",
                "p3_module_distribution",
                "p5_module_asset_count",
                "p5_module_actor_count",
                "p5_module_distribution",
            }.issubset(report_keys)
        )


if __name__ == "__main__":
    unittest.main()
