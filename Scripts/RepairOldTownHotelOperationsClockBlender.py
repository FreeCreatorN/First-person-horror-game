"""Repair/export only the clock face, preserving the other fourteen FBX files."""

import copy
import hashlib
import json
import struct
from pathlib import Path

import bpy


ROOT = Path("D:/UE/Project/HorrorGame")
OUT = ROOT / "SourceArt/OldTownHotelOperations_20261006"
KIT = OUT / "OldTownHotelOperationsKit.blend"
WORKING = OUT / "ClockFaceRepairWorking.blend"
MANIFEST = OUT / "ImportManifest.json"
VERIFICATION = OUT / "IndependentFBXVerification.json"
KEY = "WallClock"
NAME = "SM_OTS_Ops_WallClock"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measured(obj):
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = [min(point[axis] for point in points) * 100.0 for axis in range(3)]
    high = [max(point[axis] for point in points) * 100.0 for axis in range(3)]
    return low, high, [high[axis] - low[axis] for axis in range(3)]


def geometry_signature(obj):
    hasher = hashlib.sha256()
    for vertex in obj.data.vertices:
        hasher.update(struct.pack("<3f", *vertex.co))
    for polygon in obj.data.polygons:
        hasher.update(struct.pack("<I", polygon.material_index))
        hasher.update(struct.pack("<I", len(polygon.vertices)))
        hasher.update(struct.pack("<" + "I" * len(polygon.vertices), *polygon.vertices))
    return {
        "geometry_sha256": hasher.hexdigest(),
        "location": tuple(obj.location), "rotation": tuple(obj.rotation_euler),
        "scale": tuple(obj.scale), "materials": [material.name for material in obj.data.materials],
    }


manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
row = next(asset for asset in manifest["assets"] if asset["key"] == KEY)
other_rows = copy.deepcopy([asset for asset in manifest["assets"] if asset["key"] != KEY])
other_verified = copy.deepcopy([asset for asset in verification["assets"] if asset["key"] != KEY])
other_hashes = {asset["key"]: digest(OUT / asset["file"]) for asset in other_rows}
assert len(other_rows) == 14 and len(other_verified) == 14
for asset in other_rows:
    assert other_hashes[asset["key"]] == asset["source_sha256"], asset["key"]

bpy.ops.wm.open_mainfile(filepath=str(KIT))
clock = bpy.data.objects[NAME]
assert clock.type == "MESH"
other_geometry = {asset["key"]: geometry_signature(bpy.data.objects[asset["name"]]) for asset in other_rows}
grid_location = tuple(clock.location)
mesh = clock.data

# Connected islands distinguish the case, Paper dial, ticks, hands and central hub.
adjacent = [[] for vertex in mesh.vertices]
for edge in mesh.edges:
    a, b = edge.vertices
    adjacent[a].append(b)
    adjacent[b].append(a)
islands = []
unvisited = set(range(len(mesh.vertices)))
while unvisited:
    seed = unvisited.pop()
    island, pending = [seed], [seed]
    while pending:
        current = pending.pop()
        for neighbor in adjacent[current]:
            if neighbor in unvisited:
                unvisited.remove(neighbor)
                pending.append(neighbor)
                island.append(neighbor)
    islands.append(island)
island_by_vertex = {vertex: index for index, island in enumerate(islands) for vertex in island}
island_materials = [set() for island in islands]
for polygon in mesh.polygons:
    index = island_by_vertex[polygon.vertices[0]]
    island_materials[index].add(mesh.materials[polygon.material_index].name)

paper_islands = 0
thin_islands = 0
case_islands = 0
for index, island in enumerate(islands):
    minimum_x = min(mesh.vertices[vertex].co.x for vertex in island)
    maximum_x = max(mesh.vertices[vertex].co.x for vertex in island)
    width_x = maximum_x - minimum_x
    if island_materials[index] == {"Paper"}:
        # Guard against running this repair twice on an already repaired source.
        assert -0.049 < minimum_x < -0.047, ("Unexpected dial position", minimum_x)
        shift = -0.008
        paper_islands += 1
    elif width_x < 0.005 and maximum_x < -0.045:
        assert -0.051 < minimum_x < -0.049, ("Unexpected hand/tick position", minimum_x)
        shift = -0.010
        thin_islands += 1
    else:
        assert 0.049 < width_x < 0.051, ("Unrecognized clock island", index, width_x)
        shift = 0.0
        case_islands += 1
    for vertex in island:
        mesh.vertices[vertex].co.x += shift
assert paper_islands == 1 and thin_islands == 15 and case_islands == 1, (
    paper_islands, thin_islands, case_islands,
)
mesh.update()

clock.location = (0, 0, 0)
bpy.context.view_layer.update()
low, high, dimensions = measured(clock)
assert all(abs(dimensions[axis] - [6, 35, 35][axis]) < 0.01 for axis in range(3)), dimensions
assert abs(low[0] + 6.0) < 0.01 and abs(high[0]) < 0.01, (low, high)
assert abs(low[2]) < 0.01
bpy.ops.object.select_all(action="DESELECT")
clock.select_set(True)
bpy.context.view_layer.objects.active = clock
clock_path = OUT / row["file"]
bpy.ops.export_scene.fbx(
    filepath=str(clock_path), use_selection=True, object_types={"MESH"},
    global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
    use_mesh_modifiers=True, use_triangles=True, bake_anim=False,
    axis_forward="-Y", axis_up="Z", bake_space_transform=False, add_leaf_bones=False,
)
clock.location = grid_location
clock["dimensions_cm"] = dimensions
clock["source_preview_position_m"] = grid_location
row["bounds_cm"] = [low, high]
row["dimensions_cm"] = dimensions
row["nominal_dimensions_cm"] = [6, 35, 35]
row["vertices"] = len(mesh.vertices)
row["source_sha256"] = digest(clock_path)
row["note"] = "Blank vertical YZ dial and stopped hands project ahead of case; front -X; local X [-6,0] cm."
assert [material.name for material in mesh.materials] == row["materials"]
bpy.ops.wm.save_as_mainfile(filepath=str(WORKING))

# A fresh scene/import independently checks this one exported FBX, never the others.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.ops.import_scene.fbx(filepath=str(clock_path))
imported = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
assert len(imported) == 1
import_low, import_high, import_dimensions = measured(imported[0])
for axis in range(3):
    assert abs(import_dimensions[axis] - dimensions[axis]) < 0.01, import_dimensions
    assert abs(import_low[axis] - low[axis]) < 0.01, import_low
    assert abs(import_high[axis] - high[axis]) < 0.01, import_high
assert imported[0].location.length < 0.0001
verified_clock = next(asset for asset in verification["assets"] if asset["key"] == KEY)
verified_clock["dimensions_cm"] = import_dimensions
verified_clock["bounds_cm"] = [import_low, import_high]

bpy.ops.wm.open_mainfile(filepath=str(WORKING))
clock = bpy.data.objects[NAME]
assert tuple(clock.location) == grid_location
assert [material.name for material in clock.data.materials] == row["materials"]
for material_name in ("Wood", "DarkMetal", "Linen", "Paper", "Ceramic", "Upholstery", "Letters"):
    bpy.data.materials[material_name].use_fake_user = True
for asset in other_rows:
    assert geometry_signature(bpy.data.objects[asset["name"]]) == other_geometry[asset["key"]], asset["key"]
    assert digest(OUT / asset["file"]) == other_hashes[asset["key"]], asset["key"]
assert [asset for asset in manifest["assets"] if asset["key"] != KEY] == other_rows
assert [asset for asset in verification["assets"] if asset["key"] != KEY] == other_verified
bpy.context.scene["independent_fbx_validation_passed"] = True
bpy.ops.wm.save_as_mainfile(filepath=str(KIT))
MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
VERIFICATION.write_text(json.dumps(verification, indent=2), encoding="utf-8")
report = {
    "passed": True, "key": KEY, "source_sha256": row["source_sha256"],
    "bounds_cm": [low, high], "dimensions_cm": dimensions,
    "paper_islands_shifted": paper_islands, "thin_islands_shifted": thin_islands,
    "case_islands_unchanged": case_islands, "source_grid_position_m": grid_location,
    "other_fbx_hashes_unchanged": other_hashes, "other_source_meshes_unchanged": True,
    "independent_fbx_reimport_passed": True,
}
(OUT / "ClockFaceRepairVerification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
assert WORKING.resolve().parent == OUT.resolve()
WORKING.unlink()
print("HOTEL_OPERATIONS_CLOCK_REPAIR_PASS " + json.dumps({
    "source_sha256": row["source_sha256"], "bounds_cm": [low, high], "dimensions_cm": dimensions,
}))
