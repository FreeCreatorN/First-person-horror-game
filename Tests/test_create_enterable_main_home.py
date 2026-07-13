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

    def _fake_material_graph(self):
        class FakeExpression:
            def __init__(self):
                self.properties = {}

            def get_editor_property(self, name):
                return self.properties.get(name)

            def set_editor_property(self, name, value):
                self.properties[name] = value

        class FakeMaterialExpressionConstant3Vector(FakeExpression):
            pass

        class FakeMaterialExpressionConstant(FakeExpression):
            pass

        class FakeMaterialExpressionTextureSample(FakeExpression):
            pass

        class FakeMaterialExpressionMultiply(FakeExpression):
            pass

        class FakeMaterialExpressionWorldPosition(FakeExpression):
            pass

        class FakeMaterialExpressionNoise(FakeExpression):
            pass

        class FakeMaterialExpressionLinearInterpolate(FakeExpression):
            pass

        color_node = FakeMaterialExpressionConstant3Vector()
        roughness_node = FakeMaterialExpressionConstant()
        expressions = [color_node, roughness_node]

        class FakeExpressionCollection:
            def get_editor_property(self, name):
                if name != "expressions":
                    raise AttributeError(name)
                return list(expressions)

        class FakeEditorOnlyData:
            def get_editor_property(self, name):
                if name != "expression_collection":
                    raise AttributeError(name)
                return FakeExpressionCollection()

        class FakeMaterial:
            def get_editor_property(self, name):
                if name != "editor_only_data":
                    raise AttributeError(name)
                return FakeEditorOnlyData()

        material = FakeMaterial()
        base_color_property = object()
        normal_property = object()
        roughness_property = object()
        property_inputs = {
            base_color_property: color_node,
            normal_property: None,
            roughness_property: roughness_node,
        }
        created_expression_types = []
        expression_connections = []
        property_connections = []
        deleted_materials = []
        recompiled_materials = []
        saved_assets = []

        def create_material_expression(
            received_material,
            expression_type,
            _node_x,
            _node_y,
        ):
            self.assertIs(material, received_material)
            created_expression_types.append(expression_type)
            expression = expression_type()
            expressions.append(expression)
            return expression

        def connect_material_expressions(
            source,
            output_name,
            target,
            input_name,
        ):
            expression_connections.append(
                (source, output_name, target, input_name)
            )
            return True

        def connect_material_property(node, output_name, material_property):
            property_connections.append(
                (node, output_name, material_property)
            )
            property_inputs[material_property] = node
            return True

        normal_sampler_type = object()
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
            MaterialExpressionMultiply=FakeMaterialExpressionMultiply,
            MaterialExpressionWorldPosition=(
                FakeMaterialExpressionWorldPosition
            ),
            MaterialExpressionNoise=FakeMaterialExpressionNoise,
            MaterialExpressionLinearInterpolate=(
                FakeMaterialExpressionLinearInterpolate
            ),
            MaterialExpressionTextureSample=(
                FakeMaterialExpressionTextureSample
            ),
            MaterialProperty=SimpleNamespace(
                MP_BASE_COLOR=base_color_property,
                MP_NORMAL=normal_property,
                MP_ROUGHNESS=roughness_property,
            ),
            MaterialSamplerType=SimpleNamespace(
                SAMPLERTYPE_NORMAL=normal_sampler_type,
            ),
            MaterialEditingLibrary=SimpleNamespace(
                get_material_property_input_node=(
                    lambda received_material, material_property: (
                        self.assertIs(material, received_material)
                        or property_inputs[material_property]
                    )
                ),
                delete_all_material_expressions=lambda received_material: (
                    deleted_materials.append(received_material)
                ),
                create_material_expression=create_material_expression,
                connect_material_expressions=connect_material_expressions,
                connect_material_property=connect_material_property,
                recompile_material=lambda received_material: (
                    recompiled_materials.append(received_material)
                ),
            ),
        )
        state = SimpleNamespace(
            material=material,
            color_node=color_node,
            roughness_node=roughness_node,
            expressions=expressions,
            property_inputs=property_inputs,
            base_color_property=base_color_property,
            normal_property=normal_property,
            roughness_property=roughness_property,
            normal_sampler_type=normal_sampler_type,
            created_expression_types=created_expression_types,
            expression_connections=expression_connections,
            property_connections=property_connections,
            deleted_materials=deleted_materials,
            recompiled_materials=recompiled_materials,
            saved_assets=saved_assets,
        )
        return fake_unreal, state

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

    def test_fab_texture_paths_node_tags_and_material_mapping_are_stable(self):
        self.assertEqual(
            {
                "plaster": {
                    "base_color": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_ConstructionPlaster_BaseColor"
                    ),
                    "normal": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_ConstructionPlaster_Normal"
                    ),
                    "roughness": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_ConstructionPlaster_Roughness"
                    ),
                },
                "metal": {
                    "base_color": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_RustyMetalSheet_BaseColor"
                    ),
                    "normal": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_RustyMetalSheet_Normal"
                    ),
                    "roughness": (
                        "/Game/MainHome/Textures/"
                        "T_Fab_RustyMetalSheet_Roughness"
                    ),
                },
            },
            self.generator.FAB_TEXTURE_ASSET_PATHS,
        )
        self.assertEqual(
            {
                "base_color": "MainHome_Fab_BaseColor",
                "normal": "MainHome_Fab_Normal",
                "roughness": "MainHome_Fab_Roughness",
                "tint": "MainHome_Fab_Tint",
                "multiply": "MainHome_Fab_TintMultiply",
            },
            self.generator.FAB_NODE_DESCRIPTIONS,
        )
        self.assertEqual(
            {
                "M_MainHome_Wall": "plaster",
                "M_MainHome_Sign": "plaster",
                "M_MainHome_FadedGreenMetal": "metal",
            },
            self.generator.FAB_TEXTURE_SET_BY_MATERIAL,
        )
        self.assertIs(
            dict,
            self.generator.load_fab_texture_sets.__annotations__.get(
                "return"
            ),
        )

    def test_material_expressions_fall_back_to_outer_filtered_object_iterator(
        self,
    ):
        class FakeMaterialExpression:
            def __init__(self, outer):
                self.outer = outer

            def get_outer(self):
                return self.outer

        class FakeMaterial:
            def get_editor_property(self, _name):
                raise AttributeError("UE5.7 hides expression collections")

        material = FakeMaterial()
        owned_expression = FakeMaterialExpression(material)
        foreign_expression = FakeMaterialExpression(object())
        fake_unreal = SimpleNamespace(
            MaterialEditingLibrary=SimpleNamespace(),
            MaterialExpression=FakeMaterialExpression,
            ObjectIterator=lambda _expression_type: (
                owned_expression,
                foreign_expression,
            ),
        )
        self._patch_generator("unreal", fake_unreal)

        self.assertEqual(
            [owned_expression],
            self.generator._material_expressions(material),
        )

    def test_procedural_fallback_settings_are_limited_to_aged_surfaces(self):
        self.assertEqual(
            {
                "world_position": "MainHome_Aged_WorldPosition",
                "noise": "MainHome_Aged_Noise",
                "aged_tint": "MainHome_Aged_DarkTint",
                "lerp": "MainHome_Aged_ColorLerp",
            },
            self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS,
        )
        self.assertEqual(
            {
                "M_MainHome_Wall",
                "M_MainHome_Sign",
                "M_MainHome_FadedGreenMetal",
            },
            set(self.generator.PROCEDURAL_FALLBACK_SETTINGS),
        )
        wall = self.generator.PROCEDURAL_FALLBACK_SETTINGS[
            "M_MainHome_Wall"
        ]
        metal = self.generator.PROCEDURAL_FALLBACK_SETTINGS[
            "M_MainHome_FadedGreenMetal"
        ]
        self.assertGreater(wall["noise_size_cm"], metal["noise_size_cm"])
        self.assertGreaterEqual(wall["roughness"], 0.9)
        self.assertGreaterEqual(metal["roughness"], 0.85)

    def test_missing_fab_builds_idempotent_procedural_aged_color_graph(self):
        fake_unreal, state = self._fake_material_graph()
        self._patch_generator("unreal", fake_unreal)
        self._patch_generator(
            "_load_asset_if_exists",
            lambda _asset_path: state.material,
        )

        self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={},
        )
        expression_count = len(state.expressions)
        self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={},
        )

        tagged = {
            description: [
                expression
                for expression in state.expressions
                if expression.properties.get("desc") == description
            ]
            for description in (
                self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS.values()
            )
        }
        self.assertEqual(expression_count, len(state.expressions))
        self.assertTrue(all(len(nodes) == 1 for nodes in tagged.values()))
        world_position = tagged[
            self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS[
                "world_position"
            ]
        ][0]
        noise = tagged[
            self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS["noise"]
        ][0]
        aged_tint = tagged[
            self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS[
                "aged_tint"
            ]
        ][0]
        lerp = tagged[
            self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS["lerp"]
        ][0]
        tint = next(
            expression
            for expression in state.expressions
            if expression.properties.get("desc")
            == self.generator.FAB_NODE_DESCRIPTIONS["tint"]
        )
        self.assertIs(lerp, state.property_inputs[state.base_color_property])
        self.assertIn(
            (world_position, "", noise, "World Position"),
            state.expression_connections,
        )
        self.assertIn((tint, "", lerp, "A"), state.expression_connections)
        self.assertIn(
            (aged_tint, "", lerp, "B"),
            state.expression_connections,
        )
        self.assertIn((noise, "", lerp, "Alpha"), state.expression_connections)
        self.assertEqual(
            1.0
            / self.generator.PROCEDURAL_FALLBACK_SETTINGS[
                "M_MainHome_Wall"
            ]["noise_size_cm"],
            noise.properties["scale"],
        )

    def test_load_fab_texture_sets_returns_only_complete_sets_and_warns_once(self):
        paths = {
            set_name: dict(texture_paths)
            for set_name, texture_paths in (
                self.generator.FAB_TEXTURE_ASSET_PATHS.items()
            )
        }
        available_paths = set(paths["plaster"].values()) | {
            paths["metal"]["base_color"],
            paths["metal"]["normal"],
        }
        loaded_assets = {
            path: object()
            for path in available_paths
        }
        checked_paths = []
        loaded_paths = []
        warnings = []

        def asset_exists(path):
            checked_paths.append(path)
            return path in available_paths

        def load_asset(path):
            loaded_paths.append(path)
            return loaded_assets[path]

        self._patch_generator(
            "unreal",
            SimpleNamespace(log_warning=warnings.append),
        )

        result = self.generator.load_fab_texture_sets(
            asset_exists=asset_exists,
            load_asset=load_asset,
        )

        self.assertEqual(
            {
                "plaster": {
                    map_name: loaded_assets[path]
                    for map_name, path in paths["plaster"].items()
                }
            },
            result,
        )
        self.assertEqual(
            set(
                path
                for texture_paths in paths.values()
                for path in texture_paths.values()
            ),
            set(checked_paths),
        )
        self.assertEqual(set(paths["plaster"].values()), set(loaded_paths))
        self.assertEqual(1, len(warnings))
        self.assertIn(paths["metal"]["roughness"], warnings[0])
        self.assertNotIn(paths["metal"]["base_color"], warnings[0])

    def test_complete_fab_set_binds_tagged_nodes_and_reuses_them(self):
        fake_unreal, state = self._fake_material_graph()
        self._patch_generator("unreal", fake_unreal)
        self._patch_generator(
            "_load_asset_if_exists",
            lambda _asset_path: state.material,
        )
        plaster_textures = {
            "base_color": object(),
            "normal": object(),
            "roughness": object(),
        }

        first_result = self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={"plaster": plaster_textures},
        )
        expression_count = len(state.expressions)
        second_result = self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={"plaster": plaster_textures},
        )

        tagged_nodes = {
            description: [
                expression
                for expression in state.expressions
                if expression.properties.get("desc") == description
            ]
            for description in self.generator.FAB_NODE_DESCRIPTIONS.values()
        }
        self.assertIs(state.material, first_result)
        self.assertIs(state.material, second_result)
        self.assertEqual(expression_count, len(state.expressions))
        self.assertTrue(
            all(len(nodes) == 1 for nodes in tagged_nodes.values())
        )
        base_color_node = tagged_nodes[
            self.generator.FAB_NODE_DESCRIPTIONS["base_color"]
        ][0]
        normal_node = tagged_nodes[
            self.generator.FAB_NODE_DESCRIPTIONS["normal"]
        ][0]
        roughness_node = tagged_nodes[
            self.generator.FAB_NODE_DESCRIPTIONS["roughness"]
        ][0]
        tint_node = tagged_nodes[
            self.generator.FAB_NODE_DESCRIPTIONS["tint"]
        ][0]
        multiply_node = tagged_nodes[
            self.generator.FAB_NODE_DESCRIPTIONS["multiply"]
        ][0]
        self.assertIs(
            plaster_textures["base_color"],
            base_color_node.properties["texture"],
        )
        self.assertIs(
            plaster_textures["normal"],
            normal_node.properties["texture"],
        )
        self.assertIs(
            plaster_textures["roughness"],
            roughness_node.properties["texture"],
        )
        self.assertIs(
            state.normal_sampler_type,
            normal_node.properties["sampler_type"],
        )
        self.assertEqual(
            (0.46, 0.39, 0.29, 1.0),
            tint_node.properties["constant"],
        )
        self.assertIs(
            multiply_node,
            state.property_inputs[state.base_color_property],
        )
        self.assertIs(
            normal_node,
            state.property_inputs[state.normal_property],
        )
        self.assertIs(
            roughness_node,
            state.property_inputs[state.roughness_property],
        )
        self.assertIn(
            (base_color_node, "RGB", multiply_node, "A"),
            state.expression_connections,
        )
        self.assertIn(
            (tint_node, "", multiply_node, "B"),
            state.expression_connections,
        )
        self.assertFalse(
            any(
                expression.properties.get("desc")
                in self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS.values()
                for expression in state.expressions
            )
        )
        self.assertEqual([], state.deleted_materials)

    def test_missing_fab_set_reconnects_constants_and_keeps_fab_nodes(self):
        fake_unreal, state = self._fake_material_graph()
        self._patch_generator("unreal", fake_unreal)
        self._patch_generator(
            "_load_asset_if_exists",
            lambda _asset_path: state.material,
        )
        plaster_textures = {
            "base_color": object(),
            "normal": object(),
            "roughness": object(),
        }
        self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={"plaster": plaster_textures},
        )
        tagged_fab_nodes = {
            description: next(
                expression
                for expression in state.expressions
                if expression.properties.get("desc") == description
            )
            for description in self.generator.FAB_NODE_DESCRIPTIONS.values()
        }
        fab_expression_count = len(state.expressions)

        self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={},
        )

        fallback_expression_count = len(state.expressions)
        self.generator.ensure_material(
            "M_MainHome_Wall",
            texture_sets={},
        )

        self.assertGreater(fallback_expression_count, fab_expression_count)
        self.assertEqual(fallback_expression_count, len(state.expressions))
        for node in tagged_fab_nodes.values():
            self.assertIn(node, state.expressions)
        fallback_lerp_node = next(
            expression
            for expression in state.expressions
            if expression.properties.get("desc")
            == self.generator.PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS["lerp"]
        )
        self.assertIs(
            fallback_lerp_node,
            state.property_inputs[state.base_color_property],
        )
        self.assertIs(
            state.roughness_node,
            state.property_inputs[state.roughness_property],
        )
        fallback_normal_node = next(
            expression
            for expression in state.expressions
            if expression.properties.get("desc")
            == self.generator.FAB_FALLBACK_NODE_DESCRIPTIONS["normal"]
        )
        self.assertIs(
            fallback_normal_node,
            state.property_inputs[state.normal_property],
        )
        self.assertEqual(
            (0.0, 0.0, 1.0, 1.0),
            fallback_normal_node.properties["constant"],
        )
        self.assertEqual([], state.deleted_materials)

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
            "M_MainHome_Trim",
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
            (76.0, -394.0, 121.0),
            self.generator.LEFT_HINGE_CM,
        )
        self.assertEqual(
            (212.0, -394.0, 121.0),
            self.generator.RIGHT_HINGE_CM,
        )

    def test_closed_partitions_underlap_fixed_frames_without_light_leaks(self):
        shutter_asset = self._asset_definition(
            self.generator.SHUTTER_STATIC_MESH_ASSET_PATH
        )
        shutter = next(
            box
            for box in shutter_asset.visual_boxes
            if box.label == "Shutter_Panel"
        )
        self.assertEqual(
            ((-213.0, 21.0), (-394.5, -391.5), (14.0, 277.0)),
            self._translated_bounds(
                shutter, shutter_asset.actor_relative_transform.location_cm
            ),
        )

        expected = {
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Left_Panel",
                (75.0, 143.75),
            ),
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Right_Panel",
                (144.25, 213.0),
            ),
        }
        for asset_path, (label, expected_x) in expected.items():
            asset = self._asset_definition(asset_path)
            panel = next(
                box for box in asset.visual_boxes if box.label == label
            )
            bounds = self._translated_bounds(
                panel, asset.actor_relative_transform.location_cm
            )
            self.assertEqual(expected_x, bounds[0])
            self.assertEqual((14.0, 228.0), bounds[2])

    def test_transom_glass_is_concealed_behind_all_four_frame_edges(self):
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        glass = next(
            box
            for box in shell.visual_boxes
            if box.label == "DoorTransom_Glass"
        )
        self.assertEqual(
            ((75.0, 213.0), (-393.5, -392.5), (236.0, 282.0)),
            self.generator.box_bounds(glass),
        )

    def test_shutter_panel_has_required_local_and_closed_bounds(self):
        shutter = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Shutter"
        )
        panel = next(
            box for box in shutter.visual_boxes if box.label == "Shutter_Panel"
        )
        self.assertEqual(
            ((-117.0, 117.0), (0.0, 3.0), (-263.0, 0.0)),
            self.generator.box_bounds(panel),
        )
        self.assertEqual((234.0, 3.0, 263.0), panel.size_cm)
        closed_bounds = self._translated_bounds(
            panel,
            shutter.actor_relative_transform.location_cm,
        )
        self.assertEqual(
            ((-213.0, 21.0), (-394.5, -391.5), (14.0, 277.0)),
            closed_bounds,
        )
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        top_box = next(
            box
            for box in shell.visual_boxes
            if box.label == "ShutterFrame_TopBox"
        )
        self.assertEqual(
            1.5,
            closed_bounds[1][0] - self.generator.box_bounds(top_box)[1][1],
        )

    def test_raised_shutter_strip_keeps_player_sized_clearance(self):
        shutter = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Shutter"
        )
        panel = next(
            box for box in shutter.visual_boxes if box.label == "Shutter_Panel"
        )
        self.assertEqual(0.04, self.generator.SHUTTER_OPEN_SCALE_Z)
        retained_height_cm = (
            panel.size_cm[2] * self.generator.SHUTTER_OPEN_SCALE_Z
        )
        clear_height_cm = panel.size_cm[2] - retained_height_cm
        self.assertAlmostEqual(10.52, retained_height_cm)
        self.assertAlmostEqual(252.48, clear_height_cm)
        self.assertGreaterEqual(panel.size_cm[0], 230.0)
        self.assertGreaterEqual(clear_height_cm, 250.0)

    def test_raised_shutter_strip_is_not_occluded_by_fixed_top_box(self):
        shutter = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Shutter"
        )
        panel = next(
            box for box in shutter.visual_boxes if box.label == "Shutter_Panel"
        )
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        top_box = next(
            box
            for box in shell.visual_boxes
            if box.label == "ShutterFrame_TopBox"
        )
        panel_local_bounds = self.generator.box_bounds(panel)
        pivot_z = shutter.actor_relative_transform.location_cm[2]
        open_strip_z = (
            pivot_z
            + panel_local_bounds[2][0] * self.generator.SHUTTER_OPEN_SCALE_Z,
            pivot_z,
        )
        top_box_z = self.generator.box_bounds(top_box)[2]

        self.assertEqual((266.48, 277.0), open_strip_z)
        self.assertEqual((277.0, 291.0), top_box_z)
        self.assertFalse(
            max(open_strip_z[0], top_box_z[0])
            < min(open_strip_z[1], top_box_z[1])
        )

    def test_shutter_mesh_adds_offset_slats_and_bottom_rail_without_extra_collision(
        self,
    ):
        shutter = self._asset_definition(
            "/Game/MainHome/SM_MainHome_Shutter"
        )
        boxes = {box.label: box for box in shutter.visual_boxes}
        panel = boxes["Shutter_Panel"]
        slats = [
            box
            for box in shutter.visual_boxes
            if box.label.startswith("Shutter_Slat_")
        ]
        self.assertGreaterEqual(len(slats), 16)
        self.assertIn("Shutter_BottomRail", boxes)

        panel_bounds = self.generator.box_bounds(panel)
        for detail in slats + [boxes["Shutter_BottomRail"]]:
            with self.subTest(detail=detail.label):
                detail_bounds = self.generator.box_bounds(detail)
                self.assertFalse(detail.collision)
                self.assertEqual("M_MainHome_Trim", detail.material_name)
                self.assertLessEqual(
                    detail_bounds[1][1], panel_bounds[1][0] - 0.5
                )
                self.assertGreaterEqual(
                    detail_bounds[0][0], panel_bounds[0][0]
                )
                self.assertLessEqual(
                    detail_bounds[0][1], panel_bounds[0][1]
                )
                self.assertGreaterEqual(
                    detail_bounds[2][0], panel_bounds[2][0]
                )
                self.assertLessEqual(
                    detail_bounds[2][1], panel_bounds[2][1]
                )

        self.assertEqual(
            {"Shutter_Panel"},
            {box.label for box in shutter.collision_boxes},
        )
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        frame_top = next(
            box
            for box in shell.visual_boxes
            if box.label == "ShutterFrame_TopBox"
        )
        first_slat_world_bounds = self._translated_bounds(
            slats[0], shutter.actor_relative_transform.location_cm
        )
        self.assertEqual(
            self.generator.box_bounds(frame_top)[1][1],
            first_slat_world_bounds[1][0],
        )

    def test_door_leaves_have_required_local_and_closed_bounds(self):
        expected = {
            "/Game/MainHome/SM_MainHome_Door_Left": (
                "Door_Left_Panel",
                ((-1.0, 67.75), (-1.5, 1.5), (-107.0, 107.0)),
                ((75.0, 143.75), (-395.5, -392.5), (14.0, 228.0)),
            ),
            "/Game/MainHome/SM_MainHome_Door_Right": (
                "Door_Right_Panel",
                ((-67.75, 1.0), (-1.5, 1.5), (-107.0, 107.0)),
                ((144.25, 213.0), (-395.5, -392.5), (14.0, 228.0)),
            ),
        }
        for asset_path, (label, local_bounds, closed_bounds) in expected.items():
            with self.subTest(asset_path=asset_path):
                definition = self._asset_definition(asset_path)
                panel = next(
                    box for box in definition.visual_boxes if box.label == label
                )
                self.assertEqual(local_bounds, self.generator.box_bounds(panel))
                self.assertEqual(68.75, panel.size_cm[0])
                self.assertEqual(
                    closed_bounds,
                    self._translated_bounds(
                        panel,
                        definition.actor_relative_transform.location_cm,
                    ),
                )

    def test_closed_double_door_center_gap_is_half_centimeter(self):
        left = self._asset_definition(
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH
        )
        right = self._asset_definition(
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH
        )
        left_panel = next(
            box for box in left.visual_boxes if box.label == "Door_Left_Panel"
        )
        right_panel = next(
            box for box in right.visual_boxes if box.label == "Door_Right_Panel"
        )
        left_bounds = self._translated_bounds(
            left_panel, left.actor_relative_transform.location_cm
        )
        right_bounds = self._translated_bounds(
            right_panel, right.actor_relative_transform.location_cm
        )

        self.assertEqual(68.75, left_panel.size_cm[0])
        self.assertEqual(68.75, right_panel.size_cm[0])
        self.assertAlmostEqual(0.5, right_bounds[0][0] - left_bounds[0][1])
        self.assertEqual((75.0, 143.75), left_bounds[0])
        self.assertEqual((144.25, 213.0), right_bounds[0])
        self.assertIn(
            "Door_Left_CenterStile",
            {box.label for box in left.visual_boxes},
        )
        self.assertIn(
            "Door_Right_CenterStile",
            {box.label for box in right.visual_boxes},
        )

    def test_each_door_uses_green_panel_with_offset_glass_and_lower_insets(self):
        expected = (
            (
                "/Game/MainHome/SM_MainHome_Door_Left",
                "Door_Left",
                33.875,
            ),
            (
                "/Game/MainHome/SM_MainHome_Door_Right",
                "Door_Right",
                -33.875,
            ),
        )
        for asset_path, prefix, inset_x in expected:
            with self.subTest(asset_path=asset_path):
                definition = self._asset_definition(asset_path)
                boxes = {box.label: box for box in definition.visual_boxes}
                required_labels = {
                    prefix + "_Panel",
                    prefix + "_GlassInset",
                    prefix + "_LowerInset",
                    prefix + "_Handle",
                }
                self.assertTrue(required_labels.issubset(boxes))
                panel = boxes[prefix + "_Panel"]
                glass = boxes[prefix + "_GlassInset"]
                lower = boxes[prefix + "_LowerInset"]
                handle = boxes[prefix + "_Handle"]

                self.assertEqual(
                    "M_MainHome_FadedGreenMetal", panel.material_name
                )
                self.assertEqual("M_MainHome_DarkGlass", glass.material_name)
                self.assertEqual(
                    "M_MainHome_FadedGreenMetal", lower.material_name
                )
                self.assertEqual("M_MainHome_Trim", handle.material_name)
                self.assertEqual(inset_x, glass.location_cm[0])
                self.assertEqual(inset_x, lower.location_cm[0])

                panel_bounds = self.generator.box_bounds(panel)
                for detail in (glass, lower, handle):
                    detail_bounds = self.generator.box_bounds(detail)
                    self.assertFalse(detail.collision)
                    self.assertLessEqual(
                        detail_bounds[1][1], panel_bounds[1][0] - 0.5
                    )
                    self.assertFalse(
                        self._overlaps_positive_volume(
                            detail_bounds, panel_bounds
                        )
                    )

                self.assertFalse(
                    self._overlaps_positive_volume(
                        self.generator.box_bounds(handle),
                        self.generator.box_bounds(glass),
                    )
                )
                self.assertFalse(
                    self._overlaps_positive_volume(
                        self.generator.box_bounds(handle),
                        self.generator.box_bounds(lower),
                    )
                )
                self.assertEqual(
                    {prefix + "_Panel"},
                    {box.label for box in definition.collision_boxes},
                )

    def test_door_handles_keep_existing_world_centers(self):
        expected = {
            self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Left_Handle",
                (138.0, -397.5, 125.0),
            ),
            self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: (
                "Door_Right_Handle",
                (150.0, -397.5, 125.0),
            ),
        }
        for asset_path, (label, expected_world_center) in expected.items():
            with self.subTest(asset_path=asset_path):
                definition = self._asset_definition(asset_path)
                handle = next(
                    box
                    for box in definition.visual_boxes
                    if box.label == label
                )
                world_center = tuple(
                    coordinate_cm + offset_cm
                    for coordinate_cm, offset_cm in zip(
                        handle.location_cm,
                        definition.actor_relative_transform.location_cm,
                    )
                )
                self.assertEqual(expected_world_center, world_center)

    def test_fixed_transom_and_storefront_frame_own_shell_collision(self):
        shell = self._asset_definition(
            self.generator.STATIC_MESH_ASSET_PATH
        )
        shell_boxes = {box.label: box for box in shell.visual_boxes}
        expected_frame_bounds = {
            "ShutterFrame_Threshold": (
                (-220.0, 28.0), (-400.0, -396.0), (11.0, 15.0)
            ),
            "ShutterFrame_LeftGuide": (
                (-220.0, -212.0), (-400.0, -396.0), (15.0, 267.0)
            ),
            "ShutterFrame_RightGuide": (
                (20.0, 28.0), (-400.0, -396.0), (15.0, 267.0)
            ),
            "ShutterFrame_TopBox": (
                (-220.0, 28.0), (-400.0, -396.0), (277.0, 291.0)
            ),
            "DoorFrame_Threshold": (
                (68.0, 220.0), (-400.0, -396.0), (11.0, 15.0)
            ),
            "DoorFrame_Left": (
                (68.0, 76.0), (-400.0, -396.0), (15.0, 281.0)
            ),
            "DoorFrame_Right": (
                (212.0, 220.0), (-400.0, -396.0), (15.0, 281.0)
            ),
            "DoorFrame_Top": (
                (68.0, 220.0), (-400.0, -396.0), (281.0, 291.0)
            ),
            "DoorTransom_Bar": (
                (76.0, 212.0), (-400.0, -396.0), (227.0, 237.0)
            ),
            "DoorTransom_Glass": (
                (75.0, 213.0), (-393.5, -392.5), (236.0, 282.0)
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

    def test_right_side_old_city_details_are_offset_noncollision_cubes(self):
        boxes = {
            box.label: box for box in self.generator.build_shell_box_specs()
        }
        required = {
            "Side_Stain_Lower",
            "Side_Drainpipe",
            "Side_ElectricBox",
        }
        self.assertTrue(required.issubset(boxes))
        self.assertEqual(
            (230.0, 248.5),
            self.generator.box_bounds(boxes["Wall_Right"])[0],
        )
        self.assertEqual(
            (-248.5, -230.0),
            self.generator.box_bounds(boxes["Wall_Left"])[0],
        )

        wall_outer_x = self.generator.box_bounds(boxes["Wall_Right"])[0][1]
        details = [boxes[label] for label in sorted(required)]
        for detail in details:
            with self.subTest(detail=detail.label):
                bounds = self.generator.box_bounds(detail)
                self.assertEqual("side_detail", detail.category)
                self.assertFalse(detail.collision)
                self.assertGreaterEqual(detail.size_cm[0], 1.0)
                self.assertEqual((249.0, 250.0), bounds[0])
                self.assertEqual(0.5, bounds[0][0] - wall_outer_x)
                for axis_bounds, design_bounds in zip(
                    bounds, self.generator.DESIGN_BOUNDS
                ):
                    self.assertGreaterEqual(axis_bounds[0], design_bounds[0])
                    self.assertLessEqual(axis_bounds[1], design_bounds[1])

        self.assertEqual(
            "M_MainHome_Stain", boxes["Side_Stain_Lower"].material_name
        )
        for index, first in enumerate(details):
            for second in details[index + 1 :]:
                self.assertFalse(
                    self._overlaps_positive_volume(
                        self.generator.box_bounds(first),
                        self.generator.box_bounds(second),
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

    def test_fixed_shell_visible_layers_touch_without_positive_volume_overlap(
        self,
    ):
        shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
        boxes = {box.label: box for box in shell.visual_boxes}
        lintel_bounds = self.generator.box_bounds(boxes["FrontLintel"])

        for label in (
            "FrontPillar_Left",
            "FrontPillar_Between",
            "FrontPillar_Right",
        ):
            with self.subTest(label=label):
                pillar_bounds = self.generator.box_bounds(boxes[label])
                self.assertEqual((11.0, 291.0), pillar_bounds[2])
                self.assertFalse(
                    self._overlaps_positive_volume(
                        pillar_bounds, lintel_bounds
                    )
                )

        bottom_trim_bounds = self.generator.box_bounds(
            boxes["SignTrim_Bottom"]
        )
        self.assertEqual(291.0, bottom_trim_bounds[2][0])
        for label in ("ShutterFrame_TopBox", "DoorFrame_Top"):
            with self.subTest(label=label):
                self.assertFalse(
                    self._overlaps_positive_volume(
                        self.generator.box_bounds(boxes[label]),
                        bottom_trim_bounds,
                    )
                )

        layered_boxes = [
            box
            for box in shell.visual_boxes
            if box.category not in {"structure", "lining"}
        ]
        overlaps = [
            (first.label, second.label)
            for index, first in enumerate(layered_boxes)
            for second in layered_boxes[index + 1 :]
            if self._overlaps_positive_volume(
                self.generator.box_bounds(first),
                self.generator.box_bounds(second),
            )
        ]
        self.assertEqual([], overlaps)

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
            (0.24, 0.19, 0.145, 1.0),
            settings["M_MainHome_Stain"][0],
        )

    def test_missing_fab_textures_use_lighter_aged_fallback_palette(self):
        self.assertEqual(
            {
                "M_MainHome_Wall": ((0.46, 0.39, 0.29, 1.0), 0.94),
                "M_MainHome_Sign": ((0.40, 0.32, 0.23, 1.0), 0.92),
                "M_MainHome_FadedGreenMetal": (
                    (0.20, 0.30, 0.21, 1.0),
                    0.88,
                ),
                "M_MainHome_Stain": ((0.24, 0.19, 0.145, 1.0), 0.97),
            },
            {
                material_name: self.generator.MATERIAL_SETTINGS[material_name]
                for material_name in (
                    "M_MainHome_Wall",
                    "M_MainHome_Sign",
                    "M_MainHome_FadedGreenMetal",
                    "M_MainHome_Stain",
                )
            },
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
        texture_sets = {
            "plaster": {
                "base_color": object(),
                "normal": object(),
                "roughness": object(),
            }
        }
        received_texture_sets = []

        def build_boxes():
            calls.append("build_box_specs")
            return boxes

        def validate(received_boxes):
            self.assertIs(boxes, received_boxes)
            calls.append("validate_design")

        def require_unreal():
            calls.append("_require_unreal")

        def ensure_material(name, texture_sets=None):
            received_texture_sets.append(texture_sets)
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
        original_loader = getattr(
            self.generator,
            "load_fab_texture_sets",
            None,
        )
        setattr(
            self.generator,
            "load_fab_texture_sets",
            lambda: calls.append("load_fab_texture_sets") or texture_sets,
        )
        if original_loader is None:
            self.addCleanup(
                delattr,
                self.generator,
                "load_fab_texture_sets",
            )
        else:
            self.addCleanup(
                setattr,
                self.generator,
                "load_fab_texture_sets",
                original_loader,
            )
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
                "load_fab_texture_sets",
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
        self.assertEqual(
            [texture_sets] * len(self.generator.MATERIAL_ORDER),
            received_texture_sets,
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
