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


class _FakeMainHomeInteractiveActor(_FakeActor):
    def __init__(self, tags=()):
        super().__init__(tags)
        self.meshes = None

    def set_main_home_meshes(
        self,
        fixed_shell,
        shutter,
        left_door,
        right_door,
    ):
        self.meshes = (fixed_shell, shutter, left_door, right_door)


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


def _fake_unreal(
    actor_subsystem,
    interactive_actor_class=None,
    warnings=None,
):
    namespace = SimpleNamespace(
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
        log_warning=(warnings if warnings is not None else []).append,
    )
    if interactive_actor_class is not None:
        namespace.MainHomeInteractiveActor = interactive_actor_class
    return namespace


class EnterableMainHomeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def _patch_generator(self, name, replacement):
        original = getattr(self.generator, name)
        self.addCleanup(setattr, self.generator, name, original)
        setattr(self.generator, name, replacement)

    def _asset_definition(self, asset_path):
        return next(
            definition
            for definition in self.generator.MESH_ASSET_DEFINITIONS
            if definition.asset_path == asset_path
        )

    def _translated_bounds(self, box, translation_cm):
        return tuple(
            (minimum_cm + offset_cm, maximum_cm + offset_cm)
            for (minimum_cm, maximum_cm), offset_cm in zip(
                self.generator.box_bounds(box), translation_cm
            )
        )

    @staticmethod
    def _overlaps_positive_volume(first, second):
        return all(
            max(first_axis[0], second_axis[0])
            < min(first_axis[1], second_axis[1])
            for first_axis, second_axis in zip(first, second)
        )

    def test_all_generated_asset_paths_are_isolated_from_old_shop(self):
        asset_paths = [
            definition.asset_path
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        ]
        asset_paths.extend(
            "{}/{}".format(self.generator.MATERIAL_FOLDER, material_name)
            for material_name in self.generator.MATERIAL_ORDER
        )

        self.assertEqual(
            "/Game/MainHome/SM_MainHome_Enterable",
            self.generator.STATIC_MESH_ASSET_PATH,
        )
        for asset_path in asset_paths:
            with self.subTest(asset_path=asset_path):
                self.assertNotIn(
                    "/Game/OldShop_500x800x400", asset_path
                )

    def test_load_asset_if_exists_skips_missing_and_loads_existing_asset(self):
        missing_path = "/Game/MainHome/Missing"
        existing_path = "/Game/MainHome/Existing"
        existing_asset = object()
        checked_paths = []
        loaded_paths = []

        def does_asset_exist(asset_path):
            checked_paths.append(asset_path)
            return asset_path == existing_path

        def load_asset(asset_path):
            loaded_paths.append(asset_path)
            return existing_asset

        fake_unreal = SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=does_asset_exist,
                load_asset=load_asset,
            )
        )
        self._patch_generator("unreal", fake_unreal)

        load_asset_if_exists = getattr(
            self.generator, "_load_asset_if_exists", None
        )
        self.assertIsNotNone(load_asset_if_exists)
        self.assertIsNone(load_asset_if_exists(missing_path))
        self.assertEqual([], loaded_paths)
        self.assertIs(
            existing_asset,
            load_asset_if_exists(existing_path),
        )
        self.assertEqual([missing_path, existing_path], checked_paths)
        self.assertEqual([existing_path], loaded_paths)

    def test_ensure_material_reuses_existing_input_nodes_without_deleting_expressions(
        self,
    ):
        class FakeMaterialExpressionConstant3Vector:
            def __init__(self):
                self.properties = {}

            def set_editor_property(self, name, value):
                self.properties[name] = value

        class FakeMaterialExpressionConstant:
            def __init__(self):
                self.properties = {}

            def set_editor_property(self, name, value):
                self.properties[name] = value

        material = object()
        color_node = FakeMaterialExpressionConstant3Vector()
        roughness_node = FakeMaterialExpressionConstant()
        base_color_property = object()
        roughness_property = object()
        queried_properties = []
        deleted_materials = []
        created_expression_types = []
        connections = []
        recompiled_materials = []
        saved_assets = []

        def get_material_property_input_node(received_material, material_property):
            self.assertIs(material, received_material)
            queried_properties.append(material_property)
            if material_property is base_color_property:
                return color_node
            if material_property is roughness_property:
                return roughness_node
            self.fail("Unexpected material property lookup")

        def create_material_expression(
            received_material,
            expression_type,
            _node_x,
            _node_y,
        ):
            self.assertIs(material, received_material)
            created_expression_types.append(expression_type)
            return expression_type()

        def connect_material_property(node, output_name, material_property):
            connections.append((node, output_name, material_property))
            return True

        fake_unreal = SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                save_loaded_asset=lambda asset, _only_if_dirty: (
                    saved_assets.append(asset) or True
                )
            ),
            LinearColor=lambda *values: tuple(values),
            MaterialExpressionConstant=FakeMaterialExpressionConstant,
            MaterialExpressionConstant3Vector=(
                FakeMaterialExpressionConstant3Vector
            ),
            MaterialProperty=SimpleNamespace(
                MP_BASE_COLOR=base_color_property,
                MP_ROUGHNESS=roughness_property,
            ),
            MaterialEditingLibrary=SimpleNamespace(
                get_material_property_input_node=(
                    get_material_property_input_node
                ),
                delete_all_material_expressions=lambda received_material: (
                    deleted_materials.append(received_material)
                ),
                create_material_expression=create_material_expression,
                connect_material_property=connect_material_property,
                recompile_material=lambda received_material: (
                    recompiled_materials.append(received_material)
                ),
            ),
        )
        self._patch_generator("unreal", fake_unreal)
        self._patch_generator(
            "_load_asset_if_exists",
            lambda _asset_path: material,
        )

        result = self.generator.ensure_material(
            "M_MainHome_Wall",
            color=(0.11, 0.22, 0.33, 1.0),
            roughness=0.73,
        )

        self.assertIs(material, result)
        self.assertEqual(
            [base_color_property, roughness_property], queried_properties
        )
        self.assertEqual([], deleted_materials)
        self.assertEqual([], created_expression_types)
        self.assertEqual(
            (0.11, 0.22, 0.33, 1.0),
            color_node.properties["constant"],
        )
        self.assertEqual(0.73, roughness_node.properties["r"])
        self.assertEqual([], connections)
        self.assertEqual([material], recompiled_materials)
        self.assertEqual([material], saved_assets)

    def test_exact_envelope(self):
        boxes = self.generator.build_box_specs()
        self.generator.validate_design(boxes)
        self.assertEqual(
            ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
            self.generator.overall_bounds(boxes),
        )

    def test_storefront_uses_reference_width_ratio(self):
        openings = self.generator.build_doorway_specs()
        self.assertEqual(
            (248.0, 152.0),
            tuple(item.width_cm for item in openings),
        )

    def test_openings_use_exact_closed_reference_bounds(self):
        doors = self.generator.build_doorway_specs()
        self.assertEqual(
            [
                ((-220.0, -400.0, 11.0), (28.0, -350.0, 291.0)),
                ((68.0, -400.0, 11.0), (220.0, -350.0, 291.0)),
            ],
            [(door.minimum_cm, door.maximum_cm) for door in doors],
        )
        self.assertEqual([280.0, 280.0], [door.height_cm for door in doors])
        structural = [
            box
            for box in self.generator.build_shell_box_specs()
            if box.category == "structure"
        ]
        for door in doors:
            self.assertFalse(
                any(
                    self.generator.boxes_overlap_open_volume(box, door)
                    for box in structural
                )
            )

    def test_movable_meshes_are_three_independent_partitions(self):
        definitions = self.generator.MESH_ASSET_DEFINITIONS
        self.assertEqual(
            {
                "/Game/MainHome/SM_MainHome_Shutter",
                "/Game/MainHome/SM_MainHome_Door_Left",
                "/Game/MainHome/SM_MainHome_Door_Right",
            },
            {item.asset_path for item in definitions if not item.fixed},
        )

    def test_shutter_and_door_meshes_use_required_pivots(self):
        self.assertEqual(
            (-96.0, -394.5, 277.0),
            self.generator.SHUTTER_PIVOT_CM,
        )
        self.assertEqual(
            (78.0, -394.0, 120.0),
            self.generator.LEFT_HINGE_CM,
        )
        self.assertEqual(
            (210.0, -394.0, 120.0),
            self.generator.RIGHT_HINGE_CM,
        )

    def test_shutter_panel_has_required_local_and_closed_bounds(self):
        shutter = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Shutter"
        )
        panel = next(
            box for box in shutter.visual_boxes if box.label == "Shutter_Panel"
        )
        self.assertEqual(
            ((-115.0, 115.0), (0.0, 3.0), (-262.0, 0.0)),
            self.generator.box_bounds(panel),
        )
        self.assertEqual((230.0, 3.0, 262.0), panel.size_cm)
        closed_bounds = self._translated_bounds(
            panel,
            shutter.actor_relative_transform.location_cm,
        )
        self.assertEqual(
            ((-211.0, 19.0), (-394.5, -391.5), (15.0, 277.0)),
            closed_bounds,
        )
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        top_box = next(
            box
            for box in shell.visual_boxes
            if box.label == "ShutterFrame_TopBox"
        )
        self.assertEqual(
            0.5,
            closed_bounds[1][0] - self.generator.box_bounds(top_box)[1][1],
        )

    def test_door_leaves_have_required_local_and_closed_bounds(self):
        expected = {
            "/Game/MainHome/SM_MainHome_Door_Left": (
                "Door_Left_Panel",
                ((0.0, 65.0), (-1.5, 1.5), (-105.0, 105.0)),
                ((78.0, 143.0), (-395.5, -392.5), (15.0, 225.0)),
            ),
            "/Game/MainHome/SM_MainHome_Door_Right": (
                "Door_Right_Panel",
                ((-65.0, 0.0), (-1.5, 1.5), (-105.0, 105.0)),
                ((145.0, 210.0), (-395.5, -392.5), (15.0, 225.0)),
            ),
        }
        for asset_path, (label, local_bounds, closed_bounds) in expected.items():
            with self.subTest(asset_path=asset_path):
                definition = self._asset_definition(asset_path)
                panel = next(
                    box for box in definition.visual_boxes if box.label == label
                )
                self.assertEqual(local_bounds, self.generator.box_bounds(panel))
                self.assertEqual(65.0, panel.size_cm[0])
                self.assertEqual(
                    closed_bounds,
                    self._translated_bounds(
                        panel,
                        definition.actor_relative_transform.location_cm,
                    ),
                )

    def test_fixed_transom_and_storefront_frame_own_shell_collision(self):
        shell = self._asset_definition(
            self.generator.STATIC_MESH_ASSET_PATH
        )
        shell_boxes = {box.label: box for box in shell.visual_boxes}
        expected_frame_bounds = {
            "ShutterFrame_Threshold": (
                (-220.0, 28.0), (-400.0, -395.0), (11.0, 15.0)
            ),
            "ShutterFrame_LeftGuide": (
                (-220.0, -212.0), (-400.0, -395.0), (15.0, 267.0)
            ),
            "ShutterFrame_RightGuide": (
                (20.0, 28.0), (-400.0, -395.0), (15.0, 267.0)
            ),
            "ShutterFrame_TopBox": (
                (-220.0, 28.0), (-400.0, -395.0), (267.0, 291.0)
            ),
            "DoorFrame_Threshold": (
                (68.0, 220.0), (-400.0, -395.0), (11.0, 15.0)
            ),
            "DoorFrame_Left": (
                (68.0, 76.0), (-400.0, -395.0), (15.0, 281.0)
            ),
            "DoorFrame_Right": (
                (212.0, 220.0), (-400.0, -395.0), (15.0, 281.0)
            ),
            "DoorFrame_Top": (
                (68.0, 220.0), (-400.0, -395.0), (281.0, 291.0)
            ),
            "DoorTransom_Bar": (
                (76.0, 212.0), (-400.0, -395.0), (227.0, 237.0)
            ),
            "DoorTransom_Glass": (
                (80.0, 208.0), (-393.5, -392.5), (239.0, 279.0)
            ),
        }
        frame_labels = set(expected_frame_bounds)
        self.assertTrue(frame_labels.issubset(shell_boxes))
        for label, expected_bounds in expected_frame_bounds.items():
            self.assertEqual(
                expected_bounds, self.generator.box_bounds(shell_boxes[label])
            )
        self.assertTrue(
            all(shell_boxes[label].collision for label in frame_labels)
        )
        self.assertTrue(
            frame_labels.issubset(
                {box.label for box in shell.collision_boxes}
            )
        )

    def test_each_movable_partition_owns_only_its_panel_collision(self):
        expected_collision_labels = {
            "/Game/MainHome/SM_MainHome_Shutter": {"Shutter_Panel"},
            "/Game/MainHome/SM_MainHome_Door_Left": {"Door_Left_Panel"},
            "/Game/MainHome/SM_MainHome_Door_Right": {"Door_Right_Panel"},
        }
        all_collision_labels = set()
        for asset_path, labels in expected_collision_labels.items():
            with self.subTest(asset_path=asset_path):
                definition = self._asset_definition(asset_path)
                actual = {box.label for box in definition.collision_boxes}
                self.assertEqual(labels, actual)
                self.assertTrue(all(box.collision for box in definition.collision_boxes))
                self.assertTrue(all_collision_labels.isdisjoint(actual))
                all_collision_labels.update(actual)

        left = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Door_Left"
        )
        right = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Door_Right"
        )
        self.assertIn("Door_Left_Handle", {box.label for box in left.visual_boxes})
        self.assertIn("Door_Right_Handle", {box.label for box in right.visual_boxes})

    def test_partition_visuals_do_not_overlap_and_handles_are_depth_offset(self):
        world_partitions = []
        for definition in self.generator.MESH_ASSET_DEFINITIONS:
            world_partitions.append(
                (
                    definition.asset_path,
                    [
                        (
                            box,
                            self._translated_bounds(
                                box,
                                definition.actor_relative_transform.location_cm,
                            ),
                        )
                        for box in definition.visual_boxes
                    ],
                )
            )

        cross_asset_overlaps = []
        for index, (first_path, first_boxes) in enumerate(world_partitions):
            for second_path, second_boxes in world_partitions[index + 1 :]:
                for first, first_bounds in first_boxes:
                    for second, second_bounds in second_boxes:
                        if not self._overlaps_positive_volume(
                            first_bounds, second_bounds
                        ):
                            continue
                        overlap_size = tuple(
                            min(first_axis[1], second_axis[1])
                            - max(first_axis[0], second_axis[0])
                            for first_axis, second_axis in zip(
                                first_bounds, second_bounds
                            )
                        )
                        cross_asset_overlaps.append(
                            (
                                first_path,
                                first.label,
                                second_path,
                                second.label,
                                overlap_size,
                            )
                        )

        self.assertEqual([], cross_asset_overlaps)

        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        frame_boxes = [
            box for box in shell.visual_boxes if box.category == "frame"
        ]
        for index, first in enumerate(frame_boxes):
            for second in frame_boxes[index + 1 :]:
                with self.subTest(first=first.label, second=second.label):
                    self.assertFalse(
                        self._overlaps_positive_volume(
                            self.generator.box_bounds(first),
                            self.generator.box_bounds(second),
                        )
                    )

        for asset_path, panel_label, handle_label in (
            (
                "/Game/MainHome/SM_MainHome_Door_Left",
                "Door_Left_Panel",
                "Door_Left_Handle",
            ),
            (
                "/Game/MainHome/SM_MainHome_Door_Right",
                "Door_Right_Panel",
                "Door_Right_Handle",
            ),
        ):
            definition = self._asset_definition(asset_path)
            boxes = {box.label: box for box in definition.visual_boxes}
            panel_y = self.generator.box_bounds(boxes[panel_label])[1]
            handle_y = self.generator.box_bounds(boxes[handle_label])[1]
            self.assertLess(handle_y[1], panel_y[0])

    def test_partition_materials_include_faded_green_metal_and_dark_glass(self):
        self.assertIn(
            "M_MainHome_FadedGreenMetal", self.generator.MATERIAL_SETTINGS
        )
        self.assertIn("M_MainHome_DarkGlass", self.generator.MATERIAL_SETTINGS)
        movable_materials = {
            box.material_name
            for definition in self.generator.MESH_ASSET_DEFINITIONS
            if not definition.fixed
            for box in definition.visual_boxes
        }
        self.assertTrue(
            {
                "M_MainHome_FadedGreenMetal",
                "M_MainHome_DarkGlass",
            }.issubset(movable_materials)
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

    def test_only_structure_and_fixed_frame_have_shell_collision(self):
        boxes = self.generator.build_shell_box_specs()
        self.assertTrue(
            all(
                box.collision
                for box in boxes
                if box.category in {"structure", "frame"}
            )
        )
        self.assertTrue(
            all(
                not box.collision
                for box in boxes
                if box.category not in {"structure", "frame"}
            )
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

    def test_sign_and_trim_have_no_positive_volume_overlap_with_roof(self):
        boxes_by_label = {
            box.label: box for box in self.generator.build_box_specs()
        }
        roof = boxes_by_label["RoofSlab"]
        roof_bounds = self.generator.box_bounds(roof)
        sign_labels = [
            label
            for label in boxes_by_label
            if label == "Sign_Panel" or label.startswith("SignTrim_")
        ]

        def overlaps_positive_volume(first, second):
            return all(
                max(first_axis[0], second_axis[0])
                < min(first_axis[1], second_axis[1])
                for first_axis, second_axis in zip(first, second)
            )

        for label in sign_labels:
            with self.subTest(label=label):
                self.assertFalse(
                    overlaps_positive_volume(
                        self.generator.box_bounds(boxes_by_label[label]),
                        roof_bounds,
                    ),
                    "{} overlaps RoofSlab".format(label),
                )

        trim_labels = [
            label for label in sign_labels if label.startswith("SignTrim_")
        ]
        for index, first_label in enumerate(trim_labels):
            for second_label in trim_labels[index + 1 :]:
                with self.subTest(
                    first_label=first_label,
                    second_label=second_label,
                ):
                    self.assertFalse(
                        overlaps_positive_volume(
                            self.generator.box_bounds(
                                boxes_by_label[first_label]
                            ),
                            self.generator.box_bounds(
                                boxes_by_label[second_label]
                            ),
                        ),
                        "{} overlaps {}".format(first_label, second_label),
                    )

    def test_material_ids_are_contiguous(self):
        self.assertEqual(
            list(range(len(self.generator.MATERIAL_ORDER))),
            list(self.generator.MATERIAL_ID_BY_NAME.values()),
        )

    def test_legacy_material_ids_zero_through_six_are_stable(self):
        expected_legacy_ids = {
            "M_MainHome_Wall": 0,
            "M_MainHome_Interior": 1,
            "M_MainHome_Floor": 2,
            "M_MainHome_Sign": 3,
            "M_MainHome_Trim": 4,
            "M_MainHome_Letters": 5,
            "M_MainHome_Stain": 6,
        }
        self.assertEqual(
            expected_legacy_ids,
            {
                material_name: self.generator.MATERIAL_ID_BY_NAME[material_name]
                for material_name in expected_legacy_ids
            },
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

    def test_ue57_material_ids_are_enabled_before_first_box_append(self):
        events = []

        class FakeDynamicMesh:
            material_ids_enabled = False

        class FakePrimitiveOptions:
            def set_editor_property(self, _name, _value):
                pass

        def enable_material_i_ds(dynamic_mesh):
            dynamic_mesh.material_ids_enabled = True
            events.append("enable_material_i_ds")

        def append_box(dynamic_mesh, *_args):
            self.assertTrue(dynamic_mesh.material_ids_enabled)
            events.append("append_box")
            return dynamic_mesh

        fake_unreal = SimpleNamespace(
            DynamicMesh=FakeDynamicMesh,
            GeometryScript_Materials=SimpleNamespace(
                enable_material_i_ds=enable_material_i_ds
            ),
            GeometryScript_Primitives=SimpleNamespace(append_box=append_box),
            GeometryScriptPrimitiveOptions=FakePrimitiveOptions,
            GeometryScriptPrimitiveOriginMode=SimpleNamespace(CENTER="Center"),
            Rotator=lambda *values: values,
            Transform=lambda **values: values,
            Vector=lambda *values: values,
        )
        self._patch_generator("unreal", fake_unreal)

        result = self.generator._create_dynamic_mesh(
            [self.generator.build_box_specs()[0]]
        )

        self.assertIsInstance(result, FakeDynamicMesh)
        self.assertEqual(["enable_material_i_ds", "append_box"], events)

    def test_geometry_script_enables_material_ids_before_append(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertLess(source.index("enable_material_ids"), source.index("append_box("))

    def test_collision_uses_separate_aligned_box_mesh(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("set_static_mesh_collision_from_mesh", source)
        self.assertIn("ALIGNED_BOXES", source)
        self.assertNotIn("append_box_with_collision", source)

    def test_each_asset_builds_separate_visual_and_collision_meshes_and_saves(self):
        class FakeOptions:
            def set_editor_property(self, _name, _value):
                pass

        static_meshes = {
            definition.asset_path: object()
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        }
        visual_meshes = {}
        collision_meshes = {}
        copies = []
        collision_applications = []
        saved_assets = []
        materials = [
            "material:{}".format(name)
            for name in self.generator.MATERIAL_ORDER
        ]

        def create_visual(boxes):
            labels = tuple(box.label for box in boxes)
            visual_mesh = object()
            visual_meshes[labels] = visual_mesh
            return visual_mesh

        def create_collision(boxes):
            labels = tuple(box.label for box in boxes)
            collision_mesh = object()
            collision_meshes[labels] = collision_mesh
            return collision_mesh

        def load_asset(asset_path):
            return static_meshes[asset_path]

        def copy_visual(visual_mesh, static_mesh, received_materials):
            self.assertEqual(materials, received_materials)
            copies.append((visual_mesh, static_mesh))

        def set_collision(collision_mesh, static_mesh, *_options):
            collision_applications.append((collision_mesh, static_mesh))

        def save_loaded_asset(static_mesh, _only_if_dirty):
            saved_assets.append(static_mesh)
            return True

        fake_unreal = SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                save_loaded_asset=save_loaded_asset,
            ),
            GeometryScriptCollisionFromMeshOptions=FakeOptions,
            GeometryScriptCollisionGenerationMethod=SimpleNamespace(
                ALIGNED_BOXES="AlignedBoxes",
            ),
            GeometryScriptSetStaticMeshCollisionOptions=FakeOptions,
            GeometryScript_Collision=SimpleNamespace(
                set_static_mesh_collision_from_mesh=set_collision,
            ),
        )
        self._patch_generator("unreal", fake_unreal)
        self._patch_generator("create_visual_dynamic_mesh", create_visual)
        self._patch_generator("create_collision_dynamic_mesh", create_collision)
        self._patch_generator("_load_asset_if_exists", load_asset)
        self._patch_generator("_copy_visual_mesh_to_static_mesh", copy_visual)

        results = [
            self.generator.create_or_update_static_mesh(definition, materials)
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        ]

        self.assertEqual(
            [static_meshes[item.asset_path] for item in self.generator.MESH_ASSET_DEFINITIONS],
            results,
        )
        self.assertEqual(len(self.generator.MESH_ASSET_DEFINITIONS), len(visual_meshes))
        self.assertEqual(len(self.generator.MESH_ASSET_DEFINITIONS), len(collision_meshes))
        self.assertEqual(
            [
                (
                    visual_meshes[tuple(box.label for box in definition.visual_boxes)],
                    static_meshes[definition.asset_path],
                )
                for definition in self.generator.MESH_ASSET_DEFINITIONS
            ],
            copies,
        )
        self.assertEqual(
            [
                (
                    collision_meshes[
                        tuple(box.label for box in definition.collision_boxes)
                    ],
                    static_meshes[definition.asset_path],
                )
                for definition in self.generator.MESH_ASSET_DEFINITIONS
            ],
            collision_applications,
        )
        self.assertEqual(
            [static_meshes[item.asset_path] for item in self.generator.MESH_ASSET_DEFINITIONS],
            saved_assets,
        )

    def test_each_asset_builds_local_meshes_after_strict_world_validation(self):
        definitions = self.generator.MESH_ASSET_DEFINITIONS
        static_meshes = {
            definition.asset_path: object() for definition in definitions
        }
        world_validation_calls = []
        generated_local_box_sets = []
        original_validate_design = self.generator.validate_design

        def validate_world_boxes(boxes):
            boxes = tuple(boxes)
            original_validate_design(boxes)
            world_validation_calls.append(boxes)

        def create_dynamic_mesh(boxes):
            boxes = tuple(boxes)
            generated_local_box_sets.append(boxes)
            return object()

        self._patch_generator("unreal", SimpleNamespace())
        self._patch_generator("validate_design", validate_world_boxes)
        self._patch_generator("_create_dynamic_mesh", create_dynamic_mesh)
        self._patch_generator(
            "_load_asset_if_exists",
            lambda asset_path: static_meshes[asset_path],
        )
        self._patch_generator(
            "_copy_visual_mesh_to_static_mesh",
            lambda *_args: None,
        )
        self._patch_generator(
            "apply_structural_collision",
            lambda _collision_mesh, static_mesh, _asset_path: static_mesh,
        )

        try:
            results = [
                self.generator.create_or_update_static_mesh(
                    definition,
                    [object() for _name in self.generator.MATERIAL_ORDER],
                )
                for definition in definitions
            ]
        except ValueError as error:
            self.fail(
                "Mesh-local boxes must be generatable after their actor-translated "
                "world boxes pass design validation: {}".format(error)
            )

        self.assertEqual(
            [static_meshes[definition.asset_path] for definition in definitions],
            results,
        )
        self.assertEqual(
            [
                tuple(
                    self.generator._translated_box(
                        box,
                        definition.actor_relative_transform.location_cm,
                    )
                    for box in definition.visual_boxes
                )
                for definition in definitions
            ],
            world_validation_calls,
        )
        self.assertEqual(
            [
                tuple(boxes)
                for definition in definitions
                for boxes in (
                    definition.visual_boxes,
                    definition.collision_boxes,
                )
            ],
            generated_local_box_sets,
        )

    def test_existing_asset_is_updated_without_force_delete(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("copy_mesh_to_static_mesh", source)
        self.assertNotIn("delete_asset(STATIC_MESH_ASSET_PATH", source)

    def test_single_instance_uses_dedicated_tag_and_actor_subsystem(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn('GENERATOR_TAG = "MainHome_Interactive"', source)
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

    def test_interactive_placement_prefers_plugin_actor_and_assigns_four_meshes(self):
        subsystem = _FakeEditorActorSubsystem()
        self._patch_generator(
            "unreal",
            _fake_unreal(subsystem, _FakeMainHomeInteractiveActor),
        )
        meshes = {
            self.generator.STATIC_MESH_ASSET_PATH: object(),
            self.generator.SHUTTER_STATIC_MESH_ASSET_PATH: object(),
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH: object(),
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: object(),
        }

        first_result = self.generator.place_single_instance(meshes)
        second_result = self.generator.place_single_instance(meshes)

        self.assertIs(first_result, second_result)
        self.assertIsInstance(first_result, _FakeMainHomeInteractiveActor)
        self.assertEqual([first_result], subsystem.spawned)
        self.assertEqual(
            (
                meshes[self.generator.STATIC_MESH_ASSET_PATH],
                meshes[self.generator.SHUTTER_STATIC_MESH_ASSET_PATH],
                meshes[self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH],
                meshes[self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH],
            ),
            first_result.meshes,
        )
        self.assertEqual(
            ["MainHome_Interactive"],
            first_result.properties["tags"],
        )

    def test_interactive_placement_removes_exact_tag_duplicates_and_wrong_types(self):
        wrong_type = _FakeStaticMeshActor(["MainHome_Interactive"])
        primary = _FakeMainHomeInteractiveActor(["MainHome_Interactive"])
        extra = _FakeMainHomeInteractiveActor(["MainHome_Interactive"])
        similar = _FakeMainHomeInteractiveActor(["MainHome_Interactive_Copy"])
        subsystem = _FakeEditorActorSubsystem(
            [wrong_type, primary, extra, similar]
        )
        self._patch_generator(
            "unreal",
            _fake_unreal(subsystem, _FakeMainHomeInteractiveActor),
        )
        meshes = {
            definition.asset_path: object()
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        }

        result = self.generator.place_single_instance(meshes)

        self.assertIs(primary, result)
        self.assertEqual([wrong_type, extra], subsystem.destroyed)
        self.assertEqual([], subsystem.spawned)
        self.assertIn(similar, subsystem.actors)

    def test_plugin_unavailable_falls_back_to_fixed_static_mesh_actor(self):
        subsystem = _FakeEditorActorSubsystem()
        warnings = []
        self._patch_generator(
            "unreal",
            _fake_unreal(subsystem, warnings=warnings),
        )
        meshes = {
            definition.asset_path: object()
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        }

        result = self.generator.place_single_instance(meshes)

        self.assertIsInstance(result, _FakeStaticMeshActor)
        self.assertIs(
            meshes[self.generator.STATIC_MESH_ASSET_PATH],
            result.component.static_mesh,
        )
        self.assertEqual(["MainHome_Interactive"], result.properties["tags"])
        self.assertTrue(
            any("MainHomeInteractiveActor" in warning for warning in warnings)
        )

    def test_single_instance_reuses_first_valid_actor_and_removes_extras(self):
        primary = _FakeStaticMeshActor(["MainHome_Interactive"])
        extra = _FakeStaticMeshActor(["MainHome_Interactive"])
        similar = _FakeStaticMeshActor(["MainHome_Interactive_Copy"])
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
        self.assertEqual(["MainHome_Interactive"], primary.properties["tags"])
        self.assertIs(static_mesh, primary.component.static_mesh)
        self.assertEqual("Static", primary.component.properties["mobility"])
        self.assertEqual(
            "QueryAndPhysics", primary.component.collision_enabled
        )

    def test_single_instance_replaces_wrong_type_tagged_actor(self):
        wrong_type = _FakeActor(["MainHome_Interactive"])
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
        wrong_type = _FakeActor(["MainHome_Interactive"])
        valid_actor = _FakeStaticMeshActor(["MainHome_Interactive"])
        subsystem = _FakeEditorActorSubsystem([wrong_type, valid_actor])
        self._patch_generator("unreal", _fake_unreal(subsystem))

        result = self.generator.place_single_instance(object())

        self.assertIs(valid_actor, result)
        self.assertEqual([wrong_type], subsystem.destroyed)
        self.assertEqual([], subsystem.spawned)
        self.assertEqual([valid_actor], subsystem.selected)

    def test_single_instance_ignores_similar_but_not_exact_tag(self):
        similar = _FakeStaticMeshActor(["MainHome_Interactive_Copy"])
        subsystem = _FakeEditorActorSubsystem([similar])
        self._patch_generator("unreal", _fake_unreal(subsystem))

        result = self.generator.place_single_instance(object())

        self.assertEqual([], subsystem.destroyed)
        self.assertEqual([result], subsystem.spawned)
        self.assertIn(similar, subsystem.actors)
        self.assertEqual(["MainHome_Interactive_Copy"], similar.properties["tags"])

    def test_generation_iterates_all_asset_definitions_and_logs_design_summary(self):
        boxes = self.generator.build_box_specs()
        static_meshes = {
            definition.asset_path: object()
            for definition in self.generator.MESH_ASSET_DEFINITIONS
        }
        placed_actor = object()
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

        def create_static(definition, materials):
            self.assertEqual(
                ["material:{}".format(name) for name in self.generator.MATERIAL_ORDER],
                materials,
            )
            calls.append("create_or_update_static_mesh:{}".format(definition.asset_path))
            return static_meshes[definition.asset_path]

        def place_instance(received_meshes):
            self.assertEqual(static_meshes, received_meshes)
            calls.append("place_single_instance")
            return placed_actor

        self._patch_generator("build_box_specs", build_boxes)
        self._patch_generator("validate_design", validate)
        self._patch_generator("_require_unreal", require_unreal)
        self._patch_generator("ensure_material", ensure_material)
        self._patch_generator("create_or_update_static_mesh", create_static)
        self._patch_generator("place_single_instance", place_instance)
        self._patch_generator("unreal", SimpleNamespace(log=logs.append))

        result = self.generator.generate_enterable_main_home()

        self.assertEqual(
            (
                static_meshes[self.generator.STATIC_MESH_ASSET_PATH],
                placed_actor,
            ),
            result,
        )
        self.assertEqual(
            [
                "build_box_specs",
                "validate_design",
                "_require_unreal",
                *[
                    "ensure_material:{}".format(name)
                    for name in self.generator.MATERIAL_ORDER
                ],
                *[
                    "create_or_update_static_mesh:{}".format(definition.asset_path)
                    for definition in self.generator.MESH_ASSET_DEFINITIONS
                ],
                "place_single_instance",
            ],
            calls,
        )
        joined_logs = "\n".join(logs)
        for definition in self.generator.MESH_ASSET_DEFINITIONS:
            self.assertIn(definition.asset_path, joined_logs)
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
