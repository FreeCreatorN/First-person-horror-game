import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


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


class _FakeStaticMeshComponent:
    def __init__(self):
        self.static_mesh = None
        self.properties = {}
        self.collision_enabled = None

    def set_static_mesh(self, static_mesh):
        self.static_mesh = static_mesh

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def set_collision_enabled(self, value):
        self.collision_enabled = value


class _FakeActor:
    def __init__(self, tags=()):
        self.properties = {"tags": list(tags)}
        self.transform = None
        self.label = None
        self.folder_path = None

    def get_editor_property(self, name):
        return self.properties[name]

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def get_component_by_class(self, _component_class):
        return None

    def set_actor_transform(self, transform, _sweep, _teleport):
        self.transform = transform

    def set_actor_label(self, label):
        self.label = label

    def set_folder_path(self, folder_path):
        self.folder_path = folder_path


class _FakeStaticMeshActor(_FakeActor):
    def __init__(self, tags=()):
        super().__init__(tags)
        self.component = _FakeStaticMeshComponent()

    def get_component_by_class(self, component_class):
        if component_class is _FakeStaticMeshComponent:
            return self.component
        return None


class _FakeEditorActorSubsystem:
    def __init__(self, actors=()):
        self.actors = list(actors)
        self.destroyed = []
        self.spawned = []
        self.selected = []

    def get_all_level_actors(self):
        return list(self.actors)

    def destroy_actor(self, actor):
        self.destroyed.append(actor)
        if actor in self.actors:
            self.actors.remove(actor)
        return True

    def spawn_actor_from_class(
        self, actor_class, _location, _rotation, _transient=False
    ):
        actor = actor_class()
        self.actors.append(actor)
        self.spawned.append(actor)
        return actor

    def set_selected_level_actors(self, actors):
        self.selected = list(actors)


def _fake_unreal(actor_subsystem):
    return SimpleNamespace(
        CollisionEnabled=SimpleNamespace(QUERY_AND_PHYSICS="QueryAndPhysics"),
        ComponentMobility=SimpleNamespace(STATIC="Static"),
        EditorActorSubsystem=object(),
        Name=str,
        Rotator=lambda *values: tuple(float(value) for value in values),
        StaticMeshActor=_FakeStaticMeshActor,
        StaticMeshComponent=_FakeStaticMeshComponent,
        Transform=lambda **values: values,
        Vector=lambda *values: tuple(float(value) for value in values),
        get_editor_subsystem=lambda _subsystem_class: actor_subsystem,
    )


class EnterableMainHomeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def _patch_generator(self, name, replacement):
        original = getattr(self.generator, name)
        self.addCleanup(setattr, self.generator, name, original)
        setattr(self.generator, name, replacement)

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

    def test_single_instance_uses_dedicated_tag_and_actor_subsystem(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn('GENERATOR_TAG = "MainHome_Enterable"', source)
        self.assertIn("EditorActorSubsystem", source)
        self.assertIn("SM_MainHome_Enterable_Instance", source)
        self.assertIn("set_selected_level_actors", source)

    def test_active_path_never_spawns_cube_parts(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/Engine/BasicShapes/Cube.Cube", source)
        self.assertNotIn("spawn_actor_from_object", source)

    def test_active_path_never_saves_the_current_level(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("save_current_level", source)
        self.assertNotIn("save_map", source)

    def test_single_instance_reuses_first_valid_actor_and_removes_extras(self):
        primary = _FakeStaticMeshActor(["MainHome_Enterable"])
        extra = _FakeStaticMeshActor(["MainHome_Enterable"])
        similar = _FakeStaticMeshActor(["MainHome_Enterable_Copy"])
        subsystem = _FakeEditorActorSubsystem([primary, extra, similar])
        self._patch_generator("unreal", _fake_unreal(subsystem))
        static_mesh = object()

        first_result = self.generator.place_single_instance(static_mesh)
        second_result = self.generator.place_single_instance(static_mesh)

        self.assertIs(primary, first_result)
        self.assertIs(primary, second_result)
        self.assertEqual([extra], subsystem.destroyed)
        self.assertEqual([], subsystem.spawned)
        self.assertIn(similar, subsystem.actors)
        self.assertEqual([primary], subsystem.selected)
        self.assertEqual(
            (0.0, 0.0, 0.0), primary.transform["location"]
        )
        self.assertEqual("SM_MainHome_Enterable_Instance", primary.label)
        self.assertEqual("MainHome_Enterable", primary.folder_path)
        self.assertEqual(["MainHome_Enterable"], primary.properties["tags"])
        self.assertIs(static_mesh, primary.component.static_mesh)
        self.assertEqual("Static", primary.component.properties["mobility"])
        self.assertEqual(
            "QueryAndPhysics", primary.component.collision_enabled
        )

    def test_single_instance_replaces_wrong_type_tagged_actor(self):
        wrong_type = _FakeActor(["MainHome_Enterable"])
        subsystem = _FakeEditorActorSubsystem([wrong_type])
        self._patch_generator("unreal", _fake_unreal(subsystem))
        static_mesh = object()

        result = self.generator.place_single_instance(static_mesh)

        self.assertEqual([wrong_type], subsystem.destroyed)
        self.assertEqual([result], subsystem.spawned)
        self.assertIsInstance(result, _FakeStaticMeshActor)
        self.assertIs(static_mesh, result.component.static_mesh)
        self.assertEqual([result], subsystem.selected)

    def test_single_instance_reuses_valid_actor_after_wrong_type_actor(self):
        wrong_type = _FakeActor(["MainHome_Enterable"])
        valid_actor = _FakeStaticMeshActor(["MainHome_Enterable"])
        subsystem = _FakeEditorActorSubsystem([wrong_type, valid_actor])
        self._patch_generator("unreal", _fake_unreal(subsystem))

        result = self.generator.place_single_instance(object())

        self.assertIs(valid_actor, result)
        self.assertEqual([wrong_type], subsystem.destroyed)
        self.assertEqual([], subsystem.spawned)
        self.assertEqual([valid_actor], subsystem.selected)

    def test_single_instance_ignores_similar_but_not_exact_tag(self):
        similar = _FakeStaticMeshActor(["MainHome_Enterable_Copy"])
        subsystem = _FakeEditorActorSubsystem([similar])
        self._patch_generator("unreal", _fake_unreal(subsystem))

        result = self.generator.place_single_instance(object())

        self.assertEqual([], subsystem.destroyed)
        self.assertEqual([result], subsystem.spawned)
        self.assertIn(similar, subsystem.actors)
        self.assertEqual(["MainHome_Enterable_Copy"], similar.properties["tags"])

    def test_generation_runs_pipeline_in_order_and_logs_design_summary(self):
        boxes = self.generator.build_box_specs()
        static_mesh = object()
        placed_actor = object()
        visual_mesh = object()
        collision_mesh = object()
        calls = []
        logs = []

        def build_boxes():
            calls.append("build_box_specs")
            return boxes

        def validate(received_boxes):
            self.assertIs(boxes, received_boxes)
            calls.append("validate_design")

        def require_unreal():
            calls.append("_require_unreal")

        def ensure_material(name):
            calls.append("ensure_material:{}".format(name))
            return "material:{}".format(name)

        def create_visual(received_boxes):
            self.assertIs(boxes, received_boxes)
            calls.append("create_visual_dynamic_mesh")
            return visual_mesh

        def create_collision(received_boxes):
            self.assertIs(boxes, received_boxes)
            calls.append("create_collision_dynamic_mesh")
            return collision_mesh

        def create_static(received_mesh, materials):
            self.assertIs(visual_mesh, received_mesh)
            self.assertEqual(
                ["material:{}".format(name) for name in self.generator.MATERIAL_ORDER],
                materials,
            )
            calls.append("create_or_update_static_mesh")
            return static_mesh

        def apply_collision(received_collision, received_static):
            self.assertIs(collision_mesh, received_collision)
            self.assertIs(static_mesh, received_static)
            calls.append("apply_structural_collision")
            return static_mesh

        def place_instance(received_static):
            self.assertIs(static_mesh, received_static)
            calls.append("place_single_instance")
            return placed_actor

        self._patch_generator("build_box_specs", build_boxes)
        self._patch_generator("validate_design", validate)
        self._patch_generator("_require_unreal", require_unreal)
        self._patch_generator("ensure_material", ensure_material)
        self._patch_generator("create_visual_dynamic_mesh", create_visual)
        self._patch_generator("create_collision_dynamic_mesh", create_collision)
        self._patch_generator("create_or_update_static_mesh", create_static)
        self._patch_generator("apply_structural_collision", apply_collision)
        self._patch_generator("place_single_instance", place_instance)
        self._patch_generator("unreal", SimpleNamespace(log=logs.append))

        result = self.generator.generate_enterable_main_home()

        self.assertEqual((static_mesh, placed_actor), result)
        self.assertEqual(
            [
                "build_box_specs",
                "validate_design",
                "_require_unreal",
                *[
                    "ensure_material:{}".format(name)
                    for name in self.generator.MATERIAL_ORDER
                ],
                "create_visual_dynamic_mesh",
                "create_collision_dynamic_mesh",
                "create_or_update_static_mesh",
                "apply_structural_collision",
                "place_single_instance",
            ],
            calls,
        )
        joined_logs = "\n".join(logs)
        self.assertIn(self.generator.STATIC_MESH_ASSET_PATH, joined_logs)
        self.assertIn(
            "visual box count: {}".format(len(boxes)), joined_logs
        )
        self.assertIn(
            "collision box count: {}".format(
                sum(1 for box in boxes if box.collision)
            ),
            joined_logs,
        )
        self.assertIn(
            str(self.generator.overall_bounds(boxes)), joined_logs
        )
        for doorway in self.generator.build_doorway_specs():
            self.assertIn("{} clearance".format(doorway.label), joined_logs)

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
