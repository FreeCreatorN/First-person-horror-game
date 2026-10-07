"""Copy reusable OldTown meshes and separate semantic assemblies in UE 5.7.

Only the supplied level actors and new assets under the existing Meshes root
are modified. Original meshes and materials are never rebuilt or saved.
"""
from pathlib import Path
import importlib.util
import inspect
import hashlib
import json
import re

try:
    import unreal
except ImportError:
    unreal = None

ROOT = "/Game/Yastar/Meshes"
OLD_ROOT = "/Game/Yastar/OldTownSchoolStreet"
SOURCE_ROOTS = (OLD_ROOT + "/", "/Game/MainHome/")
PREFIX = "SM_OTS_Mod_"
SPLIT_NAMES = {"WallUtilityCluster", "LoadedLaundryRack", "ShopShelfStocked",
               "CounterDisplay", "TallPharmacyCabinet"}

def _path(asset):
    return asset.get_path_name().split(".", 1)[0]

def _require(condition, message):
    if not condition:
        raise RuntimeError(message)

def _category(name):
    if any(word in name for word in ("VendorTable", "CounterDisplay", "Bench", "Stool")):
        return "Table"
    if "Window" in name:
        return "hOUSE/Windows"
    if any(word in name for word in ("Door", "Shutter", "MainHome")):
        return "hOUSE/Doors" if "Door" in name else "hOUSE/BuildingParts"
    if any(word in name for word in ("Sign", "Awning", "Gate", "Crossbar")):
        return "hOUSE/Streetfront"
    if any(word in name for word in ("Lamp",)):
        return "Lighting"
    if any(word in name for word in ("ACUnit", "Meter", "Utility", "Laundry")):
        return "Utilities"
    if any(word in name for word in ("Shelf", "Cabinet", "Box", "Toolbox")):
        return "Storage"
    if any(word in name for word in ("Thermos", "Sink", "Basin", "Freezer", "GasCylinder")):
        return "Kitchenware"
    if "Plant" in name:
        return "Vegetation"
    return "StreetProps"

def _destination(name):
    stem = re.sub(r"^SM_(?:P[235]_)?", "", name)
    stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    return "{}/{}/{}{}".format(ROOT, _category(name), PREFIX, stem)

def _tag_asset(mesh, source, signature):
    unreal.EditorAssetLibrary.set_metadata_tag(mesh, "OldTownModularSource", source)
    unreal.EditorAssetLibrary.set_metadata_tag(mesh, "OldTownModularSignature", signature)

def _existing_owned(destination, source, signature):
    if not unreal.EditorAssetLibrary.does_asset_exist(destination):
        return None
    mesh = unreal.EditorAssetLibrary.load_asset(destination)
    _require(isinstance(mesh, unreal.StaticMesh), destination + " is not a StaticMesh")
    _require(unreal.EditorAssetLibrary.get_metadata_tag(mesh, "OldTownModularSource") == source,
             "Destination belongs to another asset: " + destination)
    _require(unreal.EditorAssetLibrary.get_metadata_tag(mesh, "OldTownModularSignature") == signature,
             "Destination was produced by another extraction version: " + destination)
    return mesh

def _copy_mesh(source_mesh):
    source = _path(source_mesh)
    destination = _destination(source_mesh.get_name())
    mesh = _existing_owned(destination, source, "copy-v1")
    if mesh is None:
        unreal.EditorAssetLibrary.make_directory(destination.rsplit("/", 1)[0])
        mesh = unreal.EditorAssetLibrary.duplicate_asset(source, destination)
        _require(isinstance(mesh, unreal.StaticMesh), "Mesh copy failed: " + source)
        _tag_asset(mesh, source, "copy-v1")
        _require(unreal.EditorAssetLibrary.save_loaded_asset(mesh, False), "Copy save failed")
    return mesh

def _load_prop_module():
    path = Path(__file__).with_name("CreateOldTownDetailedProps.py")
    spec = importlib.util.spec_from_file_location("ots_modular_source_props", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class _RecordingBuilder:
    """Record generator primitives without creating UE objects."""
    def __init__(self, logical_name):
        self.logical_name = logical_name
        self.operations = []

    def __getattr__(self, method):
        def record(*args, **kwargs):
            if method != "collision_box":
                self.operations.append({"method": method, "args": args,
                                        "kwargs": kwargs, "line": inspect.currentframe().f_back.f_lineno})
            return self
        return record

def _record(module, logical):
    builders = dict(module.PROP_BUILDERS, **module.P5_BUILDERS)
    function = builders[logical]
    original = module.PropMeshBuilder
    module.PropMeshBuilder = _RecordingBuilder
    try:
        recording = function()
    finally:
        module.PropMeshBuilder = original
    lines, start = inspect.getsourcelines(function)
    return recording.operations, [(start + index, line) for index, line in enumerate(lines)]

def _marker(lines, text):
    matches = [number for number, line in lines if text in line]
    _require(len(matches) == 1, "Semantic generator marker changed: " + text)
    return matches[0]

def _partitions(logical, operations, lines):
    """Use semantic source sections; never split one manufactured object by face."""
    groups = {}
    def add(name, op):
        groups.setdefault(name, []).append(op)
    if logical == "ShopShelfStocked":
        stock = _marker(lines, "Assorted packages")
        tins = _marker(lines, "A few cylindrical tins")
        package_index = tin_index = 0
        for op in operations:
            if op["line"] < stock:
                add("ShelfFrame", op)
            elif op["line"] < tins:
                add("StockPackage_{:02d}".format(package_index // 2 + 1), op)
                package_index += 1
            else:
                add("StockTin_{:02d}".format(tin_index // 2 + 1), op)
                tin_index += 1
        _require(package_index == 40 and tin_index == 10, "Shelf stock generator changed")
    elif logical == "CounterDisplay":
        scale = _marker(lines, "Counter scale and jars")
        jars = _marker(lines, "for x, radius, height in")
        jar_index = 0
        for index, op in enumerate(operations):
            if index == 0:
                add("CounterPlinth", op)
            elif op["line"] < scale:
                add("CashRegister", op)
            elif op["line"] < jars:
                add("CounterScale", op)
            else:
                add("DisplayJar_{:02d}".format(jar_index // 3 + 1), op)
                jar_index += 1
        _require(jar_index == 6, "Counter jars generator changed")
    elif logical == "LoadedLaundryRack":
        garments = _marker(lines, "Three differently proportioned garments")
        index = 0
        for op in operations:
            if op["line"] < garments:
                add("LaundryRackFrame", op)
            else:
                add("Garment_{:02d}".format(index // 6 + 1), op)
                index += 1
        _require(index == 18, "Laundry garment generator changed")
    elif logical == "TallPharmacyCabinet":
        frames = _marker(lines, "Open display frames")
        drawers = _marker(lines, "Four lower drawers")
        bottles = _marker(lines, "Uneven supported bottle rows")
        drawer_index = bottle_index = 0
        for op in operations:
            if op["line"] < frames:
                add("CabinetCase", op)
            elif op["line"] < drawers:
                add("CabinetFrontFrames", op)
            elif op["line"] < bottles:
                add("CabinetDrawer_{:02d}".format(drawer_index // 3 + 1), op)
                drawer_index += 1
            else:
                add("MedicineBottle_{:02d}".format(bottle_index // 2 + 1), op)
                bottle_index += 1
        _require(drawer_index == 12 and bottle_index == 24, "Pharmacy generator changed")
    elif logical == "WallUtilityCluster":
        meter = _marker(lines, "Deep meter cabinet")
        junction = _marker(lines, "Secondary junction box")
        cable = _marker(lines, "Coiled service cable")
        index = 0
        for op in operations:
            if op["line"] < meter:
                add("Downpipe", op)
            elif op["line"] < junction:
                add("MeterCabinet", op)
            elif op["line"] < cable:
                add("JunctionBox" if index < 2 else "ServiceConduits", op)
                index += 1
            else:
                add("ServiceCableAssembly", op)
        _require(index == 8, "Utility generator changed")
    _require(sum(map(len, groups.values())) == len(operations), "Lost geometry operations")
    _require(all(groups.values()), "Empty semantic part")
    return groups

def _material_tables(source_mesh):
    materials = {}
    slots = {}
    for index, slot in enumerate(source_mesh.get_editor_property("static_materials")):
        material = slot.get_editor_property("material_interface")
        for name in (str(slot.get_editor_property("material_slot_name")),
                     material.get_name() if material is not None else ""):
            if name:
                materials[name] = material
                slots[name] = index
    return materials, slots

def _xyz(vector):
    return (float(vector.x), float(vector.y), float(vector.z))

def _bounds_tuple(bounds):
    return (_xyz(bounds.min), _xyz(bounds.max))

def _prepare_parts(module, source_mesh, logical):
    operations, lines = _record(module, logical)
    partitions = _partitions(logical, operations, lines)
    materials, source_slots = _material_tables(source_mesh)
    source = _path(source_mesh)
    parts = []
    for part_name, group in partitions.items():
        builder = module.PropMeshBuilder(logical + "_" + part_name)
        for operation in group:
            getattr(builder, operation["method"])(*operation["args"], **operation["kwargs"])
        _require(all(name in source_slots for name in builder.material_names),
                 "Source material slots differ from generator for " + source)
        bounds = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(builder.mesh)
        minimum, maximum = _bounds_tuple(bounds)
        pivot = ((minimum[0] + maximum[0]) * 0.5,
                 (minimum[1] + maximum[1]) * 0.5, minimum[2])
        result = unreal.GeometryScript_MeshTransforms.translate_mesh(
            builder.mesh, unreal.Vector(x=-pivot[0], y=-pivot[1], z=-pivot[2]))
        if result is not None:
            builder.mesh = result[0] if isinstance(result, tuple) else result
        signature = "part-v1-" + hashlib.sha256(json.dumps(group, sort_keys=True).encode()).hexdigest()[:16]
        destination = _destination("SM_" + logical + "_" + part_name)
        mesh = _existing_owned(destination, source, signature)
        if mesh is None:
            folder, asset_name = destination.rsplit("/", 1)
            unreal.EditorAssetLibrary.make_directory(folder)
            mesh = module._create_or_update_asset(folder, asset_name, builder, materials)
            _tag_asset(mesh, source, signature)
            _require(unreal.EditorAssetLibrary.save_loaded_asset(mesh, False), "Part save failed")
        _require(mesh.get_num_triangles(0) > 0, "Empty semantic mesh: " + destination)
        parts.append({"mesh": mesh, "asset": destination, "name": part_name,
                      "pivot": pivot, "source_slots": [source_slots[n] for n in builder.material_names],
                      "bounds": (minimum, maximum), "operations": len(group)})
    source_minimum, source_maximum = _bounds_tuple(source_mesh.get_bounding_box())
    rebuilt_minimum = tuple(min(p["bounds"][0][i] for p in parts) for i in range(3))
    rebuilt_maximum = tuple(max(p["bounds"][1][i] for p in parts) for i in range(3))
    _require(all(abs(a - b) < 0.15 for a, b in zip(source_minimum + source_maximum,
                                                 rebuilt_minimum + rebuilt_maximum)),
             "Replayed geometry bounds differ from current source: " + source)
    total_triangles = sum(part["mesh"].get_num_triangles(0) for part in parts)
    _require(total_triangles == source_mesh.get_num_triangles(0),
             "Replayed geometry triangle count differs from current source: " + source)
    return parts

def _spawn_parts(actor_subsystem, actor, component, parts, collision_mesh):
    transform = component.get_world_transform()
    overrides = [component.get_material(i) for i in range(component.get_num_materials())]
    spawned = []
    try:
        for part in parts:
            position = transform.transform_location(unreal.Vector(
                x=part["pivot"][0], y=part["pivot"][1], z=part["pivot"][2]))
            new_actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, position)
            _require(new_actor is not None, "Could not spawn " + part["name"])
            spawned.append(new_actor)
            new_actor.set_actor_rotation(component.get_world_rotation(), False)
            new_actor.set_actor_scale3d(component.get_world_scale())
            new_actor.set_actor_label(actor.get_actor_label() + "_" + part["name"])
            new_actor.set_folder_path(actor.get_folder_path())
            new_actor.set_editor_property("tags", list(actor.get_editor_property("tags")) + [unreal.Name("OTS_ModularPart")])
            target = new_actor.get_component_by_class(unreal.StaticMeshComponent)
            target.set_mobility(component.get_editor_property("mobility"))
            target.set_static_mesh(part["mesh"])
            target.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            for property_name in ("cast_shadow", "receives_decals", "visible", "hidden_in_game",
                                  "affect_distance_field_lighting", "render_custom_depth",
                                  "custom_depth_stencil_value"):
                target.set_editor_property(property_name, component.get_editor_property(property_name))
            for index, original_slot in enumerate(part["source_slots"]):
                target.set_material(index, overrides[original_slot])
                _require(target.get_material(index) == overrides[original_slot],
                         "Part material override was not preserved")
            _require(all(abs(a - b) < 0.01 for a, b in zip(_xyz(new_actor.get_actor_location()), _xyz(position))),
                     "Part world position was not preserved")
        # Keep a collision carrier only when the source mesh has actual simple
        # shapes. Generated P5/utility assemblies normally have none.
        # StaticMeshEditorSubsystem is not created in Python commandlets.
        simple_collision = unreal.GeometryScript_Collision.get_simple_collision_from_static_mesh(
            component.get_editor_property("static_mesh"))
        shapes = unreal.GeometryScript_Collision.get_simple_collision_shape_count(simple_collision)
        complex_collision = False
        body_setup = component.get_editor_property("static_mesh").get_editor_property("body_setup")
        if body_setup is not None:
            flag = body_setup.get_editor_property("collision_trace_flag")
            complex_collision = "COMPLEX_AS_SIMPLE" in str(flag).upper()
        if (shapes > 0 or complex_collision) and component.get_collision_enabled().value != unreal.CollisionEnabled.NO_COLLISION.value:
            component.set_static_mesh(collision_mesh)
            component.set_visibility(False)
            component.set_hidden_in_game(True)
            actor.set_actor_label(actor.get_actor_label() + "_CollisionCarrier")
        else:
            _require(actor_subsystem.destroy_actor(actor), "Failed to remove combined visual actor")
    except Exception:
        for new_actor in spawned:
            actor_subsystem.destroy_actor(new_actor)
        raise
    return len(spawned)

def extract_reusable_assets(actor_subsystem):
    """Convert supplied level actor mesh references; return a serializable report."""
    _require(unreal is not None, "Run this function inside Unreal Editor")
    _require(unreal.EditorAssetLibrary.does_directory_exist(ROOT),
             "Required existing asset root was not found: " + ROOT)
    report = {"root": ROOT, "copied_assets": [], "split_assets": [],
              "swapped_components": 0, "split_source_actors": 0,
              "spawned_parts": 0, "warnings": [], "unconverted_references": []}
    cache = {}
    split_cache = {}
    module = None
    for actor in list(actor_subsystem.get_all_level_actors()):
        components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        for component in components:
            source_mesh = component.get_editor_property("static_mesh")
            if source_mesh is None or not _path(source_mesh).startswith(SOURCE_ROOTS):
                continue
            source = _path(source_mesh)
            if source not in cache:
                cache[source] = _copy_mesh(source_mesh)
                report["copied_assets"].append({"source": source, "asset": _path(cache[source])})
            logical = re.sub(r"^SM_P[25]_", "", source_mesh.get_name())
            if logical in SPLIT_NAMES and actor.get_class().get_name() == "StaticMeshActor" and len(components) == 1:
                if source not in split_cache:
                    if module is None:
                        module = _load_prop_module()
                    split_cache[source] = _prepare_parts(module, source_mesh, logical)
                    report["split_assets"].append({
                        "source": source,
                        "parts": [{key: value for key, value in part.items() if key != "mesh"}
                                  for part in split_cache[source]],
                        "source_triangle_count": source_mesh.get_num_triangles(0),
                        "part_triangle_count": sum(p["mesh"].get_num_triangles(0) for p in split_cache[source]),
                    })
                report["spawned_parts"] += _spawn_parts(actor_subsystem, actor, component,
                                                        split_cache[source], cache[source])
                report["split_source_actors"] += 1
                break
            component.set_static_mesh(cache[source])
            report["swapped_components"] += 1
    for actor in actor_subsystem.get_all_level_actors():
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = component.get_editor_property("static_mesh")
            if mesh is not None and _path(mesh).startswith(SOURCE_ROOTS):
                report["unconverted_references"].append({"actor": actor.get_actor_label(), "mesh": _path(mesh)})
    _require(not report["unconverted_references"], "OldTown source mesh references remain after conversion")
    report["asset_count"] = len(report["copied_assets"]) + sum(len(group["parts"]) for group in report["split_assets"])
    report["semantic_geometry_validated"] = True
    return report
