"""Build the editable V4 hotel source in an isolated Blender CLI process.

Run Blender --background --factory-startup --python this_file -- [--plan PATH]
[--out DIR]. World plan coordinates are centimetres; Blender geometry is metres.
Existing source libraries are appended read-only. This never imports UE assets.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "Saved/CodexOutputs/HotelRedesign_20261008_V4/ArchitecturePlan.json"
DEFAULT_OUT = ROOT / "SourceArt/OldTownHotelRedesign_20261008_V4"
LIBRARIES = {
    "architecture": ROOT / "SourceArt/OldTownHotelArchitecture_20261005/OldTownHotelArchitectureKit.blend",
    "operations": ROOT / "SourceArt/OldTownHotelOperations_20261006/OldTownHotelOperationsKit.blend",
    "modular": ROOT / "SourceArt/OldTownModular_20261002/OldTown_OriginalFurniture.blend",
    "openings": ROOT / "SourceArt/OldTownHotelOpenings_20261004/OldTownHotelOpenings.blend",
}
PREFIXES = ("SM_OTS_Arch_", "SM_OTS_Ops_", "SM_OTS_Blender_", "SM_OTS_")
COLORS = {
    "plaster": (.49, .47, .39, 1), "concrete": (.34, .34, .30, 1),
    "wood": (.18, .11, .065, 1), "green": (.16, .23, .18, 1),
    "dark": (.075, .085, .07, 1), "linen": (.48, .47, .37, 1),
    "ceramic": (.66, .64, .55, 1), "glass": (.27, .40, .39, .25),
    "proxy": (.64, .27, .13, 1), "route": (.12, .39, .65, 1),
}
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def new_collection(name, parent):
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def tag(obj, identifier, floor, role, source_kind):
    obj["plan_id"] = str(identifier)
    obj["floor_index"] = int(floor) if floor is not None else -1
    obj["role"] = str(role)
    obj["source_kind"] = source_kind


def mesh_box(name, size_m, collection, material, origin=(0, 0, 0)):
    x, y, z = [float(v) / 2 for v in size_m]
    vertices = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], FACES)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = origin
    mesh.materials.append(material)
    return obj


def world_box(row, collection, mats, prefix=""):
    lo, hi = row["world_min"], row["world_max"]
    assert all(hi[i] > lo[i] for i in range(3)), row
    size = [(hi[i] - lo[i]) / 100 for i in range(3)]
    pos = [(hi[i] + lo[i]) / 200 for i in range(3)]
    obj = mesh_box(prefix + row["id"], size, collection,
                   mats.get(row.get("material", "plaster"), mats["plaster"]), pos)
    tag(obj, row["id"], row.get("floor"), row.get("role", "box"), "plan_box")
    obj["expected_min_cm"] = lo
    obj["expected_max_cm"] = hi
    obj["collision_requested"] = bool(row.get("collision", True))
    return obj


def opening_basis(row):
    normal = Vector(row.get("inward", [1, 0, 0]))
    normal.z = 0
    normal.normalize()
    tangent = Vector((normal.y, -normal.x, 0))
    return tangent, normal


def opening_part(name, row, collection, mats, loc, size, mat="wood"):
    tangent, normal = opening_basis(row)
    obj = mesh_box(name, [s / 100 for s in size], collection, mats[mat])
    obj.matrix_world = Matrix((tangent, normal, Vector((0, 0, 1)))).transposed().to_4x4()
    base = Vector(row["position_cm"])
    obj.location = (base + tangent * loc[0] + normal * loc[1] + Vector((0, 0, loc[2]))) / 100
    tag(obj, row["id"], row.get("floor"), row.get("kind", "opening"), "opening_component")
    return obj


def make_door(row, collection, mats):
    name = "Door_" + str(row["id"])
    width, height = float(row["width"]), float(row.get("height", 220))
    depth = float(row.get("depth", 20))
    for side in (-1, 1):
        opening_part(name + "_FrameJamb_" + str(side), row, collection, mats,
                     (side * (width / 2 + 3), 0, height / 2), (6, depth, height), "green")
    opening_part(name + "_FrameHead", row, collection, mats,
                 (0, 0, height + 4), (width + 12, depth, 8), "green")
    kind = str(row.get("kind", "swing")).lower()
    slide = "slid" in kind or "slider" in kind
    leaf_count = int(row.get("leaf_count", 1))
    if slide:
        fraction = float(row.get("source_open_fraction", 0 if row.get("locked") else 1))
        for side in (-1, 1):
            part = opening_part(name + "_SlidingLeaf_" + str(side), row, collection, mats,
                                (side * width * (.25 + .5 * fraction), -2, height / 2),
                                (width / 2, 4, height), "glass" if width >= 180 else "wood")
            part["pose"] = "open reference pose; independently editable sliding leaf"
        return
    tangent, normal = opening_basis(row)
    base = Vector(row["position_cm"])
    for side in ((-1, 1) if leaf_count == 2 else (int(row.get("hinge_side", -1)),)):
        leaf_width = width / leaf_count
        hinge = bpy.data.objects.new(name + "_Hinge_" + str(side), None)
        collection.objects.link(hinge)
        hinge.location = (base + tangent * side * width / 2) / 100
        hinge.empty_display_type = "ARROWS"
        hinge.empty_display_size = .14
        angle = math.radians(float(row.get("source_open_angle_deg", row.get("open_angle_deg", 0 if row.get("locked") else 90))))
        along = tangent * (-side) * math.cos(angle) + normal * math.sin(angle)
        hinge.rotation_euler.z = math.atan2(along.y, along.x)
        tag(hinge, row["id"], row.get("floor"), "door_hinge", "opening_hinge")
        leaf = mesh_box(name + "_Leaf_" + str(side), (leaf_width / 100, .04, height / 100), collection,
                        mats["wood"], (leaf_width / 200, 0, height / 200))
        leaf.parent = hinge
        tag(leaf, row["id"], row.get("floor"), "door_leaf", "opening_component")
        leaf["pose_degrees"] = math.degrees(angle)
        handle = mesh_box(name + "_Handle_" + str(side), (.025, .095, .11), collection,
                          mats["dark"], ((leaf_width - 12) / 100, -.0475, 1))
        handle.parent = hinge
        tag(handle, row["id"], row.get("floor"), "door_handle", "opening_component")


def make_window(row, collection, mats):
    name = "Window_" + str(row["id"])
    width, height = float(row["width"]), float(row["height"])
    for side in (-1, 1):
        opening_part(name + "_Jamb_" + str(side), row, collection, mats,
                     (side * (width / 2 - 2.5), 0, height / 2), (5, 12, height), "green")
    for z, label in ((2.5, "Sill"), (height - 2.5, "Head")):
        opening_part(name + "_" + label, row, collection, mats,
                     (0, 0, z), (width - 10, 12, 5), "green")
    opening_part(name + "_Mullion", row, collection, mats,
                 (0, 0, height / 2), (4, 8, height - 10), "green")
    for side in (-1, 1):
        opening_part(name + "_Glass_" + str(side), row, collection, mats,
                     (side * width / 4, 0, height / 2), (width / 2 - 10, .7, height - 10), "glass")


def load_prototypes():
    prototypes, sources = {}, []
    for family, path in LIBRARIES.items():
        if not path.exists():
            continue
        with bpy.data.libraries.load(str(path), link=False) as (src, dest):
            dest.objects = [name for name in src.objects if name.startswith("SM_OTS_")]
        for obj in dest.objects:
            if obj is None or obj.type != "MESH":
                continue
            for prefix in PREFIXES:
                if obj.name.startswith(prefix):
                    key = obj.name[len(prefix):].split(".")[0]
                    prototypes.setdefault(key, (obj, family))
                    prototypes[family + ":" + key] = (obj, family)
                    break
            prototypes[obj.name.split(".")[0]] = (obj, family)
        sources.append(dict(family=family, path=str(path), sha256=sha(path)))
    return prototypes, sources


def prop_object(row, collection, prototypes, mats, floors):
    key = row.get("asset_key", "")
    family = row.get("source_family", "")
    candidate = prototypes.get(family + ":" + key) if family else None
    candidate = candidate or prototypes.get(key)
    if candidate is None:
        meshpath = row.get("asset_path", row.get("mesh_path", ""))
        candidate = prototypes.get(meshpath.split("/")[-1].split(".")[0])
    floor = row.get("floor", min(range(len(floors)), key=lambda i: abs(row["position_cm"][2] - floors[i])))
    if candidate:
        proto, source_family = candidate
        obj = proto.copy()
        obj.data = proto.data.copy()
        obj.name = row["id"]
        obj.hide_viewport = False
        obj.hide_render = False
        collection.objects.link(obj)
        obj.location = Vector(row["position_cm"]) / 100
        rotation = row.get("rotation")
        obj.rotation_euler = (0, 0, math.radians(float(row.get("yaw", 0))))
        if isinstance(rotation, list) and len(rotation) == 3:
            # Unreal plan rotation is [pitch,yaw,roll], as in saved ActorState.
            obj.rotation_euler = tuple(math.radians(float(v)) for v in (rotation[2], rotation[0], rotation[1]))
        obj.scale = row.get("scale", [1, 1, 1])
        obj["source_family"] = source_family
        obj["source_prototype"] = proto.name
        tag(obj, row["id"], floor, "prop", "appended_prop")
        return True
    obj = mesh_box("PROXY_" + row["id"], (.3, .3, .3), collection, mats["proxy"],
                   Vector(row["position_cm"]) / 100 + Vector((0, 0, .15)))
    tag(obj, row["id"], floor, "unresolved_asset_proxy", "proxy")
    obj["unresolved_asset_key"] = key
    return False


def add_reference(row, collection, points=None):
    identifier = str(row.get("id", "Reference"))
    if points:
        curve = bpy.data.curves.new(identifier + "_Path", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = .015
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for vertex, point in zip(spline.points, points):
            vertex.co = (*[float(v) / 100 for v in point], 1)
        obj = bpy.data.objects.new("Route_" + identifier, curve)
    else:
        obj = bpy.data.objects.new("Room_" + identifier, None)
        obj.empty_display_type = "CUBE"
        if "world_min" in row and "world_max" in row:
            lo, hi = row["world_min"], row["world_max"]
            obj.location = [(lo[i] + hi[i]) / 200 for i in range(3)]
            obj.scale = [(hi[i] - lo[i]) / 200 for i in range(3)]
    collection.objects.link(obj)
    obj.hide_render = True
    obj.show_name = True
    tag(obj, identifier, row.get("floor", row.get("from_floor")), "reference", "reference")
    obj["plan_record"] = json.dumps(row, ensure_ascii=False)
    return obj


def bounds_cm(obj):
    points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return [[min(p[i] for p in points) * 100 for i in range(3)],
            [max(p[i] for p in points) * 100 for i in range(3)]]


def verify_saved(plan, blend_path, plan_path, sources, unresolved):
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    measured, errors = [], []
    floor_counts, role_counts = Counter(), Counter()
    box_bounds = {}
    for obj in bpy.context.scene.objects:
        if "plan_id" not in obj:
            continue
        floor_counts[str(obj.get("floor_index", -1))] += 1
        role_counts[str(obj.get("role", ""))] += 1
        if obj.get("source_kind") != "plan_box":
            continue
        actual = bounds_cm(obj)
        wanted = [list(obj["expected_min_cm"]), list(obj["expected_max_cm"])]
        error = max(abs(actual[j][i] - wanted[j][i]) for j in range(2) for i in range(3))
        measured.append(dict(id=obj["plan_id"], max_bounds_error_cm=error, bounds_cm=actual))
        box_bounds[str(obj["plan_id"])] = actual
        if error > .05:
            errors.append("Box dimensions differ: " + obj["plan_id"])
    holes = list(plan.get("slab_voids", plan.get("floor_voids", [])))
    if not holes:
        holes = [dict(row, kind="lift") for row in plan.get("shafts", []) if row.get("floor", 0) > 0]
    hole_results = []
    for hole in holes:
        floor = hole.get("floor", hole.get("to_floor"))
        if floor is None or int(floor) <= 0:
            continue
        if "world_min" not in hole or "world_max" not in hole:
            continue
        lo, hi = hole["world_min"], hole["world_max"]
        covering = []
        for row in plan["boxes"]:
            if row.get("floor") != floor or row.get("role") not in ("floor", "floor_slab", "slab"):
                continue
            a, b = box_bounds[row["id"]]
            if min(b[0], hi[0]) - max(a[0], lo[0]) > .1 and min(b[1], hi[1]) - max(a[1], lo[1]) > .1:
                covering.append(row["id"])
        hole_results.append(dict(id=hole["id"], floor=floor, kind=hole.get("kind"),
                                 uncovered=not covering, covering_floor_boxes=covering))
        if covering:
            errors.append("Floor slab covers declared void: " + hole["id"])
    room_counts = Counter(str(row["floor"]) for row in plan["rooms"])
    if len(plan["floor_z_cm"]) != 4 or len(plan["rooms"]) != 27:
        errors.append("Expected four storeys and 27 rooms")
    stairs = plan.get("staircases", plan.get("stair_routes", []))
    report = dict(passed=not errors, status="PASS" if not errors and not unresolved else
                  ("PASS_WITH_PROXY_ASSETS" if not errors else "FAIL"),
                  plan=str(plan_path), plan_sha256=sha(plan_path), source=str(blend_path),
                  source_sha256=sha(blend_path), blender_version=bpy.app.version_string,
                  authoring_units="metres", plan_units="centimetres", world_axes="Plan XYZ preserved",
                  storeys=len(plan["floor_z_cm"]), rooms=len(plan["rooms"]), rooms_by_floor=dict(room_counts),
                  scene_objects=len(bpy.context.scene.objects), mesh_objects=sum(o.type == "MESH" for o in bpy.context.scene.objects),
                  tagged_objects_by_floor=dict(floor_counts), roles=dict(role_counts),
                  plan_boxes=len(plan["boxes"]), reloaded_measured_boxes=len(measured),
                  max_bounds_error_cm=max((row["max_bounds_error_cm"] for row in measured), default=0),
                  door_assemblies=len(plan.get("doors", [])), window_assemblies=len(plan.get("windows", [])),
                  appended_prop_instances=len(plan.get("props", [])) - len(unresolved), proxy_assets=unresolved,
                  stair_connections=len(stairs), stair_connection_ids=[s["id"] for s in stairs],
                  slab_void_checks=hole_results, actual_saved_box_measurements=measured,
                  source_libraries=sources, errors=errors,
                  limitations=["Editable source validation is independent from saved UE collision and runtime validation.",
                               "Door leaves use editable reference poses; game interaction is validated in UE separately."])
    return report


def main():
    args = arguments()
    plan_path, out = args.plan.resolve(), args.out.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    assert len(plan["floor_z_cm"]) == 4 and len(plan["rooms"]) == 27
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene["architecture_plan_sha256"] = sha(plan_path)
    scene["design_version"] = "Approved V4 hotel; all four floors"
    mats = {}
    for name, color in COLORS.items():
        material = bpy.data.materials.new("V4_" + name)
        material.diffuse_color = color
        material.use_nodes = True
        shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = .78 if name != "glass" else .2
        if name == "glass":
            shader.inputs["Transmission Weight"].default_value = .35
        mats[name] = material
    building = new_collection("OldTownHotel_V4", scene.collection)
    levels = {i: new_collection("Floor_%d_%s" % (i + 1, "Lobby" if i == 0 else "GuestRooms"), building) for i in range(4)}
    whole = new_collection("WholeBuilding_And_Exterior", building)
    groups = {(i, key): new_collection(key, coll) for i, coll in levels.items()
              for key in ("Structure", "Openings", "Furniture", "PlanReferences")}

    def group(row, key):
        floor = row.get("floor")
        if floor is None and "position_cm" in row:
            floor = min(range(4), key=lambda i: abs(row["position_cm"][2] - plan["floor_z_cm"][i]))
        return groups.get((floor, key), whole)

    for row in plan["boxes"]:
        world_box(row, group(row, "Structure"), mats)
    for row in plan.get("doors", []):
        make_door(row, group(row, "Openings"), mats)
    for row in plan.get("windows", []):
        make_window(row, group(row, "Openings"), mats)
    prototypes, sources = load_prototypes()
    unresolved = []
    for row in plan.get("props", []):
        if not prop_object(row, group(row, "Furniture"), prototypes, mats, plan["floor_z_cm"]):
            unresolved.append(dict(id=row["id"], asset_key=row.get("asset_key"), representation="orange 30cm proxy"))
    for row in plan["rooms"]:
        add_reference(row, group(row, "PlanReferences"))
    for row in plan.get("routes", []):
        add_reference(row, group(row, "PlanReferences"), row.get("points", row.get("foot_waypoints")))
    for row in plan.get("staircases", plan.get("stair_routes", [])):
        ref = dict(row, floor=row.get("from_floor", 0))
        add_reference(ref, group(ref, "PlanReferences"), row.get("foot_waypoints", row.get("points")))
    text = bpy.data.texts.new("ArchitecturePlan_V4.json")
    text.write(plan_path.read_text(encoding="utf-8-sig"))
    scene.cursor.location = (95.2, 0, 0)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_location = (95.2, 0, 7.5)
                area.spaces.active.region_3d.view_distance = 65
                area.spaces.active.shading.color_type = "MATERIAL"
    blend_path = out / "OldTownHotelV4.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = verify_saved(plan, blend_path, plan_path, sources, unresolved)
    (out / "SourceVerification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("Source verification failed: " + "; ".join(report["errors"]))
    print("OLD_TOWN_HOTEL_V4_SOURCE_PASS objects=%d rooms=%d proxies=%d" %
          (report["scene_objects"], report["rooms"], len(unresolved)))


if __name__ == "__main__":
    main()
