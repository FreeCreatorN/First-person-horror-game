import importlib.util
from pathlib import Path
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "Scripts" / "CreateEnterableMainHome.py"
SCENE_PATH = PROJECT_ROOT / "Scripts" / "CreateOldTownSchoolStreetScene.py"
ACTOR_HEADER_PATH = (
    PROJECT_ROOT
    / "Plugins"
    / "MainHomeInteractive"
    / "Source"
    / "MainHomeInteractive"
    / "Public"
    / "MainHomeInteractiveActor.h"
)
ACTOR_CPP_PATH = (
    PROJECT_ROOT
    / "Plugins"
    / "MainHomeInteractive"
    / "Source"
    / "MainHomeInteractive"
    / "Private"
    / "MainHomeInteractiveActor.cpp"
)
ACTOR_TEST_PATH = (
    PROJECT_ROOT
    / "Plugins"
    / "MainHomeInteractive"
    / "Source"
    / "MainHomeInteractive"
    / "Private"
    / "Tests"
    / "MainHomeInteractiveActorTests.cpp"
)
BLUEPRINT_FILE = (
    PROJECT_ROOT
    / "Content"
    / "Yastar"
    / "Blockout"
    / "Buildings"
    / "BP_MainHomeInteractive.uasset"
)


def _load_generator():
    module_name = "_main_home_interaction_upgrade_contract_generator"
    spec = importlib.util.spec_from_file_location(module_name, GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _translated_bounds(generator, box, translation):
    return tuple(
        (
            bounds[0] + offset,
            bounds[1] + offset,
        )
        for bounds, offset in zip(generator.box_bounds(box), translation)
    )


class MainHomeInteractionUpgradeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = _load_generator()
        cls.scene_source = SCENE_PATH.read_text(encoding="utf-8")
        cls.header_source = ACTOR_HEADER_PATH.read_text(encoding="utf-8")
        cls.cpp_source = ACTOR_CPP_PATH.read_text(encoding="utf-8")
        cls.cpp_test_source = ACTOR_TEST_PATH.read_text(encoding="utf-8")
        scale_match = re.search(
            r"FMath::Lerp\(\s*1\.0f,\s*([0-9.]+)f,\s*"
            r"FMath::Clamp\(Alpha",
            cls.cpp_source,
        )
        if scale_match is None:
            raise AssertionError("Runtime shutter open scale was not found")
        cls.runtime_open_scale = float(scale_match.group(1))
        cls.definitions = {
            definition.asset_path: definition
            for definition in cls.generator.MESH_ASSET_DEFINITIONS
        }

    def test_blueprint_and_four_mesh_asset_paths_stay_stable(self):
        self.assertTrue(BLUEPRINT_FILE.is_file())
        self.assertIn(
            'MAIN_HOME_BP = "/Game/Yastar/Blockout/Buildings/'
            'BP_MainHomeInteractive"',
            self.scene_source,
        )
        expected_paths = (
            "/Game/MainHome/SM_MainHome_Enterable",
            "/Game/MainHome/SM_MainHome_Shutter",
            "/Game/MainHome/SM_MainHome_Door_Left",
            "/Game/MainHome/SM_MainHome_Door_Right",
        )
        self.assertEqual(
            expected_paths,
            (
                self.generator.STATIC_MESH_ASSET_PATH,
                self.generator.SHUTTER_STATIC_MESH_ASSET_PATH,
                self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH,
                self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH,
            ),
        )
        for asset_path in expected_paths:
            self.assertIn('TEXT("{}")'.format(asset_path), self.cpp_source)

    def test_component_names_and_attachment_hierarchy_are_stable(self):
        component_names = (
            "FixedShell",
            "Shutter",
            "LeftHinge",
            "LeftDoorLeaf",
            "RightHinge",
            "RightDoorLeaf",
            "ShutterInteractionZone",
            "DoorInteractionZone",
        )
        for name in component_names:
            self.assertIn(
                'CreateDefaultSubobject<',
                self.cpp_source,
            )
            self.assertIn('TEXT("{}")'.format(name), self.cpp_source)
            self.assertIn(name, self.header_source)
        self.assertIn("Shutter->SetupAttachment(SceneRoot);", self.cpp_source)
        self.assertIn("LeftHinge->SetupAttachment(SceneRoot);", self.cpp_source)
        self.assertIn(
            "LeftDoorLeaf->SetupAttachment(LeftHinge);",
            self.cpp_source,
        )
        self.assertIn("RightHinge->SetupAttachment(SceneRoot);", self.cpp_source)
        self.assertIn(
            "RightDoorLeaf->SetupAttachment(RightHinge);",
            self.cpp_source,
        )

    def test_python_mesh_pivots_match_runtime_component_pivots(self):
        expected_pivots = {
            "SHUTTER_PIVOT_CM": (-96.0, -394.5, 277.0),
            "LEFT_HINGE_CM": (76.0, -394.0, 121.0),
            "RIGHT_HINGE_CM": (212.0, -394.0, 121.0),
        }
        for constant_name, pivot in expected_pivots.items():
            self.assertEqual(pivot, getattr(self.generator, constant_name))
            vector = "FVector({:.1f}f, {:.1f}f, {:.1f}f)".format(*pivot)
            self.assertIn(vector, self.cpp_source)
        self.assertIn(
            "LeftDoorLeaf->SetRelativeTransform(FTransform::Identity);",
            self.cpp_source,
        )
        self.assertIn(
            "RightDoorLeaf->SetRelativeTransform(FTransform::Identity);",
            self.cpp_source,
        )

    def test_movable_collision_proxies_keep_exact_local_and_closed_bounds(self):
        expected = {
            self.generator.SHUTTER_STATIC_MESH_ASSET_PATH: (
                "Shutter_Panel",
                ((-117.0, 117.0), (0.0, 3.0), (-263.0, 0.0)),
                ((-213.0, 21.0), (-394.5, -391.5), (14.0, 277.0)),
            ),
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Left_Panel",
                ((-1.0, 67.75), (-1.5, 1.5), (-107.0, 107.0)),
                ((75.0, 143.75), (-395.5, -392.5), (14.0, 228.0)),
            ),
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Right_Panel",
                ((-67.75, 1.0), (-1.5, 1.5), (-107.0, 107.0)),
                ((144.25, 213.0), (-395.5, -392.5), (14.0, 228.0)),
            ),
        }
        for asset_path, (label, local_bounds, closed_bounds) in expected.items():
            with self.subTest(asset_path=asset_path):
                definition = self.definitions[asset_path]
                self.assertEqual(
                    {label},
                    {box.label for box in definition.collision_boxes},
                )
                proxy = definition.collision_boxes[0]
                self.assertEqual(local_bounds, self.generator.box_bounds(proxy))
                self.assertEqual(
                    closed_bounds,
                    _translated_bounds(
                        self.generator,
                        proxy,
                        definition.actor_relative_transform.location_cm,
                    ),
                )

    def test_closed_double_door_gap_and_frame_underlap_are_stable(self):
        left_definition = self.definitions[
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH
        ]
        right_definition = self.definitions[
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH
        ]
        left = left_definition.collision_boxes[0]
        right = right_definition.collision_boxes[0]
        left_world = _translated_bounds(
            self.generator,
            left,
            left_definition.actor_relative_transform.location_cm,
        )
        right_world = _translated_bounds(
            self.generator,
            right,
            right_definition.actor_relative_transform.location_cm,
        )
        self.assertAlmostEqual(0.5, right_world[0][0] - left_world[0][1])
        self.assertEqual((75.0, 143.75), left_world[0])
        self.assertEqual((144.25, 213.0), right_world[0])
        self.assertEqual(1.0, self.generator.FRAME_UNDERLAP_CM)

    def test_runtime_animation_endpoints_remain_closed_zero_open_one(self):
        self.assertIn("DoorOpenDirection = EMainHomeDoorOpenDirection::Outward;", self.cpp_source)
        self.assertIn("DoorAngleDegrees = 95.0f;", self.cpp_source)
        self.assertIn("AnimationDurationSeconds = 0.65f;", self.cpp_source)
        self.assertIn("InteractionDistanceCm = 350.0f;", self.cpp_source)
        self.assertEqual(0.12, self.runtime_open_scale)
        self.assertIn(
            "State.ShutterTarget = State.ShutterTarget >= 0.5f ? 0.0f : 1.0f;",
            self.cpp_source,
        )
        self.assertIn(
            "Target = Target >= 0.5f ? 0.0f : 1.0f;",
            self.cpp_source,
        )
        self.assertIn(
            "const float SideSign = bIsLeftDoor ? -1.0f : 1.0f;",
            self.cpp_source,
        )
        self.assertIn(
            "Direction == EMainHomeDoorOpenDirection::Outward ? 1.0f : -1.0f;",
            self.cpp_source,
        )

    def test_interaction_trace_dispatches_only_the_three_movable_components(self):
        self.assertIn("QueryParams.AddIgnoredActor(Pawn);", self.cpp_source)
        self.assertIn("ECC_Visibility,", self.cpp_source)
        self.assertIn("Hit.GetActor() != this", self.cpp_source)
        self.assertIn("Hit.GetComponent(),", self.cpp_source)
        self.assertIn("Shutter,", self.cpp_source)
        self.assertIn("LeftDoorLeaf,", self.cpp_source)
        self.assertIn("RightDoorLeaf", self.cpp_source)
        self.assertIn("if (HitComponent == ShutterComponent)", self.cpp_source)
        self.assertIn("if (HitComponent == LeftDoorComponent)", self.cpp_source)
        self.assertIn("if (HitComponent == RightDoorComponent)", self.cpp_source)
        self.assertIn("return EHitPart::None;", self.cpp_source)

    def test_open_shutter_remains_visibility_traceable_but_not_pawn_blocking(self):
        self.assertIn(
            "? ECollisionEnabled::QueryOnly",
            self.cpp_source,
        )
        self.assertIn(
            "bSettledOpen ? ECR_Ignore : ECR_Block",
            self.cpp_source,
        )
        self.assertIn(
            "Shutter->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);",
            self.cpp_source,
        )
        self.assertIn(
            "FMath::IsNearlyEqual(Alpha, 1.0f)",
            self.cpp_source,
        )
        self.assertIn(
            "FMath::IsNearlyEqual(Target, 1.0f)",
            self.cpp_source,
        )

    def test_interior_close_target_height_and_activation_volume_remain_reachable(self):
        shutter_definition = self.definitions[
            self.generator.SHUTTER_STATIC_MESH_ASSET_PATH
        ]
        panel = shutter_definition.collision_boxes[0]
        panel_local_z = self.generator.box_bounds(panel)[2]
        pivot_z = shutter_definition.actor_relative_transform.location_cm[2]
        open_strip_z = (
            pivot_z + panel_local_z[0] * self.runtime_open_scale,
            pivot_z + panel_local_z[1] * self.runtime_open_scale,
        )
        self.assertAlmostEqual(245.44, open_strip_z[0], places=2)
        self.assertAlmostEqual(277.0, open_strip_z[1], places=2)
        self.assertLessEqual(open_strip_z[0], 250.0)
        self.assertGreaterEqual(open_strip_z[1], 250.0)

        shutter_zone_center = (-96.0, -394.5, 151.0)
        shutter_zone_extent = (125.0, 350.0, 150.0)
        interior_trace_start = (-96.0, -100.0, 250.0)
        for coordinate, center, extent in zip(
            interior_trace_start,
            shutter_zone_center,
            shutter_zone_extent,
        ):
            self.assertGreaterEqual(coordinate, center - extent)
            self.assertLessEqual(coordinate, center + extent)
        self.assertIn(
            "FVector(-96.0f, -100.0f, 250.0f)",
            self.cpp_test_source,
        )
        self.assertIn(
            "FVector(-96.0f, -450.0f, 250.0f)",
            self.cpp_test_source,
        )
        self.assertIn(
            'TEXT("Raised shutter is first blocking component from inside")',
            self.cpp_test_source,
        )


if __name__ == "__main__":
    unittest.main()
