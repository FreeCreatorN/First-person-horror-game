"""Build a separate, measured hotel operations prop kit. Run with Blender only.

All source geometry is in metres, unplaced, with the origin at (0, 0, 0).
The manifest records the measured FBX geometry in centimetres for Unreal import.
Existing hotel source files and Blender projects are never opened or changed.
"""

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path("D:/UE/Project/HorrorGame")
OUT = ROOT / "SourceArt/OldTownHotelOperations_20261006"
KIT = OUT / "OldTownHotelOperationsKit.blend"
PREFIX = "SM_OTS_Ops_"
COLORS = {
    "Wood": (0.18, 0.11, 0.065, 1.0),
    "DarkMetal": (0.12, 0.13, 0.10, 1.0),
    "Linen": (0.49, 0.47, 0.39, 1.0),
    "Paper": (0.74, 0.71, 0.61, 1.0),
    "Ceramic": (0.61, 0.58, 0.49, 1.0),
    "Upholstery": (0.27, 0.31, 0.24, 1.0),
    "Letters": (0.71, 0.67, 0.49, 1.0),
}

OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
mats = {}
for name, color in COLORS.items():
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    material.use_fake_user = True
    shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = 0.76
    mats[name] = material

parts = []
assets = []


def add_material(obj, material):
    obj.data.materials.append(mats[material])
    parts.append(obj)
    return obj


def bevel(obj, width, segments=2):
    if width:
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new("SoftEdges", "BEVEL")
        modifier.width = width
        modifier.segments = segments
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def cube(name, loc, size, material="Wood", edge=0.005):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    add_material(obj, material)
    return bevel(obj, min(edge, min(size) * 0.24))


def cylinder(name, loc, radius, depth, material="DarkMetal", rotation=None, edge=0.001):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    add_material(obj, material)
    bevel(obj, min(edge, depth * 0.2, radius * 0.2))
    if rotation:
        obj.rotation_euler = rotation
    return obj


def torus(name, loc, radius, minor, material="DarkMetal", rotation=None, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=48, minor_segments=12, location=loc,
        major_radius=radius, minor_radius=minor,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if rotation:
        obj.rotation_euler = rotation
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return add_material(obj, material)


def tube(name, points, radius, material="DarkMetal"):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 3
    data.use_fill_caps = True
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1.0)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return add_material(obj, material)


def beam(name, start, end, width, material="DarkMetal"):
    start, end = Vector(start), Vector(end)
    direction = end - start
    obj = cube(name, (start + end) / 2, (width, width, direction.length), material, 0.002)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def cone_between(name, start, end, radius_start, radius_end, material="Ceramic"):
    start, end = Vector(start), Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=radius_start, radius2=radius_end,
        depth=direction.length, location=(start + end) / 2,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return add_material(obj, material)


def lathe(name, profile, material, scale=(1, 1, 1), segments=48):
    """Closed ring profile in (radius, Z), with elliptical scaling if needed."""
    vertices = []
    for radius, z in profile:
        for index in range(segments):
            angle = index * 2.0 * math.pi / segments
            vertices.append((radius * math.cos(angle) * scale[0],
                             radius * math.sin(angle) * scale[1], z * scale[2]))
    faces = []
    for ring in range(len(profile) - 1):
        for index in range(segments):
            next_index = (index + 1) % segments
            faces.append((ring * segments + index, ring * segments + next_index,
                          (ring + 1) * segments + next_index, (ring + 1) * segments + index))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple((len(profile) - 1) * segments + i for i in range(segments)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return add_material(obj, material)


def measured(obj):
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = [min(point[axis] for point in points) * 100.0 for axis in range(3)]
    high = [max(point[axis] for point in points) * 100.0 for axis in range(3)]
    return low, high, [high[axis] - low[axis] for axis in range(3)]


def finish(key, expected_dimensions, tolerance_cm=0.03, note=""):
    assert parts, key
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = PREFIX + key
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Preserve explicit semantic slots, with no duplicate or auto-suffixed names.
    polygon_materials = [obj.data.materials[p.material_index].name for p in obj.data.polygons]
    slot_names = [name for name in COLORS if name in set(polygon_materials)]
    obj.data.materials.clear()
    for name in slot_names:
        obj.data.materials.append(mats[name])
    slots = {name: index for index, name in enumerate(slot_names)}
    for polygon, material_name in zip(obj.data.polygons, polygon_materials):
        polygon.material_index = slots[material_name]

    low, high, dimensions = measured(obj)
    assert all(abs(dimensions[i] - expected_dimensions[i]) <= tolerance_cm for i in range(3)), (
        key, dimensions, expected_dimensions,
    )
    assert abs(low[2]) < 0.03, (key, "base must be Z=0", low)
    assert tuple(obj.location) == (0.0, 0.0, 0.0), (key, obj.location[:])
    if key in ("LiftFace", "LiftCallPanel", "WallClock"):
        assert abs(high[0]) < 0.03, (key, "mounting plane must be X=0", high)
    elif key != "RotaryPhone":
        assert abs(low[1] + high[1]) < 0.03, (key, "must be centred along Y", low, high)

    path = OUT / (obj.name + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        use_mesh_modifiers=True, use_triangles=True, bake_anim=False,
        axis_forward="-Y", axis_up="Z", bake_space_transform=False,
        add_leaf_bones=False,
    )
    obj["asset_key"] = key
    obj["dimensions_cm"] = dimensions
    obj["origin_convention"] = "Unplaced; origin (0,0,0); base Z=0"
    assets.append({
        "key": key, "name": obj.name, "file": path.name,
        "bounds_cm": [low, high], "dimensions_cm": dimensions,
        "nominal_dimensions_cm": expected_dimensions,
        "vertices": len(obj.data.vertices), "materials": slot_names,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "note": note,
    })
    parts.clear()
    return obj


# Rotary telephone: ten real bored finger holes and a separate supported handset.
cube("TelephoneBase", (0, 0, 0.023), (0.28, 0.21, 0.046), "DarkMetal", 0.013)
cube("TelephoneUpperHousing", (0.015, 0, 0.050), (0.22, 0.175, 0.048), "DarkMetal", 0.012)
dial = cylinder("RotaryDial", (-0.045, 0, 0.077), 0.067, 0.012, "Letters", edge=0.001)
for index in range(10):
    angle = math.radians(25 + index * 30)
    x, y = -0.045 + 0.047 * math.cos(angle), 0.047 * math.sin(angle)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.0085, depth=0.035,
                                       location=(x, y, 0.077))
    cutter = bpy.context.object
    bpy.context.view_layer.objects.active = dial
    modifier = dial.modifiers.new("DialFingerHole", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    cylinder("DialNumberDot", (-0.045 + 0.060 * math.cos(angle), 0.060 * math.sin(angle),
                               0.0832), 0.0033, 0.0008, "Paper", edge=0)
cylinder("DialCentre", (-0.045, 0, 0.084), 0.025, 0.002, "Paper", edge=0)
torus("DialCentreRing", (-0.045, 0, 0.085), 0.026, 0.0015, "DarkMetal")
cube("DialFingerStop", (0.015, -0.043, 0.085), (0.013, 0.023, 0.004), "DarkMetal", 0.001)
for y in (-0.061, 0.061):
    cube("HandsetCradle", (0.074, y, 0.084), (0.038, 0.017, 0.040), "DarkMetal", 0.004)
    cube("HandsetReceiver", (0.074, y, 0.113), (0.062, 0.066, 0.039), "DarkMetal", 0.012)
cube("HandsetGrip", (0.074, 0, 0.126), (0.038, 0.139, 0.028), "DarkMetal", 0.009)
tube("PhoneCordLead", [(0.095, 0.092, 0.109), (0.103, 0.098, 0.075),
                       (0.080, 0.100, 0.040)], 0.003, "DarkMetal")
for index in range(9):
    torus("PhoneCordCoil", (0.080, 0.105 + index * 0.005, 0.040), 0.011, 0.003,
          "DarkMetal", rotation=(math.pi / 2, 0, 0))
tube("PhoneCordTail", [(0.060, 0.146, 0.035), (0.100, 0.146, 0.035)], 0.004, "DarkMetal")
finish("RotaryPhone", [28, 25.5, 14],
       note="Body 28x21 cm; cord extends to Y=+15 cm for an asymmetric import-axis witness; front -X; base Z=0.")

# Open reception ledger, with a low binding and individual ruled sheets.
cube("LedgerCover", (0, 0, 0.003), (0.42, 0.30, 0.006), "Wood", 0.002)
for x in (-0.106, 0.106):
    cube("PageStack", (x, 0, 0.0155), (0.196, 0.284, 0.019), "Paper", 0.001)
    cube("TopPage", (x, 0, 0.026), (0.195, 0.282, 0.002), "Paper", 0.0003)
    for row in range(14):
        cube("RuledLine", (x, -0.120 + row * 0.018, 0.0273),
             (0.173, 0.00065, 0.0004), "Letters", 0)
    for column in (-0.063, 0.040):
        cube("LedgerColumn", (x + column, 0, 0.0273),
             (0.00065, 0.260, 0.0004), "Letters", 0)
cube("LedgerBinding", (0, 0, 0.018), (0.012, 0.286, 0.024), "Wood", 0.002)
finish("Ledger", [42, 30, 3], note="Open ruled ledger; base Z=0.")

lathe("BellDome", [(0.048, 0.012), (0.050, 0.020), (0.046, 0.036),
                   (0.035, 0.056), (0.018, 0.068), (0.006, 0.072)], "Letters")
cylinder("BellBase", (0, 0, 0.007), 0.060, 0.014, "DarkMetal", edge=0.002)
cylinder("BellStem", (0, 0, 0.077), 0.006, 0.014, "DarkMetal")
cylinder("BellButton", (0, 0, 0.085), 0.016, 0.010, "Letters", edge=0.0015)
finish("DeskBell", [12, 12, 9])

# Chair: seat surface 44 cm above the floor; front -X, back +X.
for x in (-0.192, 0.192):
    for y in (-0.182, 0.182):
        cube("ChairLeg", (x, y, 0.196), (0.040, 0.040, 0.392), "Wood", 0.004)
cube("ChairSeatFrame", (0, 0, 0.405), (0.48, 0.46, 0.035), "Wood", 0.007)
cube("ChairSeatCushion", (-0.006, 0, 0.43125), (0.440, 0.420, 0.0175),
     "Upholstery", 0.004)
for y in (-0.193, 0.193):
    cube("ChairBackPost", (0.215, y, 0.610), (0.040, 0.040, 0.460), "Wood", 0.005)
cube("ChairBackTop", (0.215, 0, 0.790), (0.040, 0.46, 0.100), "Wood", 0.009)
cube("ChairBackRail", (0.215, 0, 0.616), (0.030, 0.372, 0.045), "Wood", 0.004)
for y in (-0.105, 0, 0.105):
    cube("ChairBackSlat", (0.215, y, 0.705), (0.026, 0.043, 0.145), "Wood", 0.004)
finish("Chair", [48, 46, 84], note="Seat top Z=44 cm; front -X; back +X.")

# Bench dressing only: rests on the existing bench top, including both end arms.
for x in (-0.865, 0, 0.865):
    cube("SofaSeatCushion", (x, -0.025, 0.060), (0.850, 0.650, 0.120),
         "Upholstery", 0.025)
cube("SofaBackCore", (0, 0.300, 0.255), (2.70, 0.10, 0.450), "Upholstery", 0.017)
for x in (-0.865, 0, 0.865):
    cube("SofaBackPad", (x, 0.246, 0.290), (0.850, 0.030, 0.325),
         "Upholstery", 0.010)
    for z in (0.235, 0.345):
        cylinder("SofaButton", (x, 0.228, z), 0.010, 0.006, "Linen",
                 rotation=(math.pi / 2, 0, 0), edge=0.001)
for x in (-1.35, 1.35):
    cube("SofaArm", (x, 0, 0.235), (0.10, 0.70, 0.47), "Upholstery", 0.017)
finish("SofaTop", [280, 70, 48], note="Dressing base Z=0 rests at bench-top Z=59 cm; back +Y; both arms.")

cube("CoffeeTableTop", (0, 0, 0.455), (1.40, 0.70, 0.050), "Wood", 0.010)
for x in (-0.605, 0.605):
    for y in (-0.260, 0.260):
        cube("CoffeeTableLeg", (x, y, 0.215), (0.060, 0.060, 0.430), "Wood", 0.005)
for y in (-0.2675, 0.2675):
    cube("CoffeeTableLongApron", (0, y, 0.402), (1.240, 0.035, 0.065), "Wood", 0.004)
for x in (-0.605, 0.605):
    cube("CoffeeTableEndApron", (x, 0, 0.402), (0.035, 0.52, 0.065), "Wood", 0.004)
finish("CoffeeTable", [140, 70, 48])

# Counter-mounted basin: entire basin stays above its mounting plane at Z=0.
cube("SinkBottom", (0, 0, 0.006), (0.70, 0.80, 0.012), "Ceramic", 0.004)
for x in (-0.320, 0.320):
    cube("SinkSideRim", (x, 0, 0.046), (0.060, 0.80, 0.068), "Ceramic", 0.007)
for y in (-0.370, 0.370):
    cube("SinkEndRim", (0, y, 0.046), (0.580, 0.060, 0.068), "Ceramic", 0.007)
cylinder("SinkDrain", (-0.06, 0, 0.013), 0.027, 0.003, "DarkMetal", edge=0)
torus("DrainRim", (-0.06, 0, 0.015), 0.029, 0.002, "Letters")
cylinder("TapBase", (0.270, 0, 0.084), 0.024, 0.014, "DarkMetal")
cylinder("TapStem", (0.270, 0, 0.159), 0.014, 0.150, "DarkMetal")
tube("TapRearElbow", [(0.270, 0, 0.215), (0.270, 0, 0.245), (0.255, 0, 0.265)], 0.014)
cylinder("TapTopPipe", (0.210, 0, 0.265), 0.015, 0.100, "DarkMetal",
         rotation=(0, math.pi / 2, 0), edge=0)
tube("TapFrontElbow", [(0.165, 0, 0.265), (0.150, 0, 0.248), (0.150, 0, 0.215)], 0.014)
cylinder("TapNozzle", (0.150, 0, 0.215), 0.017, 0.022, "DarkMetal")
for y in (-0.105, 0.105):
    cylinder("TapControl", (0.270, y, 0.088), 0.016, 0.022, "DarkMetal")
    cube("TapControlLever", (0.270, y, 0.101), (0.055, 0.010, 0.008), "Letters", 0.002)
finish("PantrySink", [70, 80, 28], note="Rim top Z=8 cm; tap top Z=28 cm; counter-mounted base Z=0.")

# 22 cm diameter kettle body; the spout extends beyond that body diameter.
lathe("KettleBody", [(0.084, 0.000), (0.099, 0.018), (0.110, 0.075),
                     (0.108, 0.175), (0.097, 0.215), (0.083, 0.235)], "Ceramic")
cylinder("KettleLid", (0, 0, 0.240), 0.088, 0.015, "Ceramic", edge=0.002)
cylinder("KettleKnob", (0, 0, 0.260), 0.020, 0.025, "DarkMetal", edge=0.004)
spout_end = Vector((-0.190, 0, 0.240))
spout_start = Vector((-0.075, 0, 0.130))
cone_between("KettleSpout", spout_start, spout_end, 0.031, 0.020, "Ceramic")
spout_rotation = (spout_end - spout_start).to_track_quat("Z", "Y").to_euler()
torus("KettleSpoutLip", spout_end, 0.020, 0.003, "Ceramic", rotation=spout_rotation)
cylinder("KettleSpoutOpening", spout_end - (spout_end - spout_start).normalized() * 0.002,
         0.016, 0.002, "DarkMetal", rotation=spout_rotation, edge=0)
for sign in (-1, 1):
    tube("KettleBailSide", [(0, sign * 0.095, 0.210), (0, sign * 0.095, 0.280),
                            (0, sign * 0.080, 0.326)], 0.014)
cylinder("KettleBailGrip", (0, 0, 0.326), 0.014, 0.160, "DarkMetal",
         rotation=(math.pi / 2, 0, 0), edge=0)
finish("Kettle", [32, 22, 34], tolerance_cm=1.0,
       note="Body diameter 22 cm; measured X includes spout; handle top Z=34 cm.")

for index in range(5):
    width = (0.55, 0.53, 0.545, 0.52, 0.53)[index]
    depth = (0.40, 0.38, 0.39, 0.37, 0.38)[index]
    z = index * 0.05 + 0.025
    cube("FoldedTowel", (0, 0, z), (width, depth, 0.05), "Linen", 0.012)
    cube("TowelFold", (-width / 2 + 0.010, 0, z - 0.009),
         (0.012, depth - 0.022, 0.020), "Linen", 0.004)
finish("TowelPile", [55, 40, 25])

lathe("LinenSack", [(0.70, 0.00), (0.91, 0.04), (1.00, 0.18), (1.00, 0.42),
                    (0.65, 0.52), (0.38, 0.565), (0.50, 0.59), (0.16, 0.60)],
      "Linen", scale=(0.25, 0.225, 1.0))
torus("BagTie", (0, 0, 0.566), 0.088, 0.008, "DarkMetal", scale=(1.06, 0.95, 1))
tube("BagLooseTie", [(-0.094, 0, 0.565), (-0.120, 0.014, 0.540),
                     (-0.126, 0.017, 0.507)], 0.004, "DarkMetal")
finish("LinenBag", [50, 45, 60])

# Open service cart: four wheels, three shelves, a front linen bag and mop pocket.
for x in (-0.290, 0.290):
    for y in (-0.500, 0.500):
        cylinder("CartWheel", (x, y, 0.065), 0.065, 0.050, "DarkMetal",
                 rotation=(math.pi / 2, 0, 0), edge=0.003)
        cylinder("CartWheelHub", (x, y, 0.065), 0.023, 0.048, "Letters",
                 rotation=(math.pi / 2, 0, 0), edge=0.001)
        cube("CartCasterStem", (x, y * 0.90, 0.125), (0.035, 0.035, 0.050), "DarkMetal", 0.004)
for x in (-0.330, 0.330):
    for y in (-0.460, 0.460):
        cube("CartUpright", (x, y, 0.565), (0.026, 0.026, 0.870), "DarkMetal", 0.003)
for z in (0.160, 0.490, 0.800):
    cube("CartShelf", (0, 0, z), (0.70, 0.98, 0.030), "Wood", 0.004)
    for y in (-0.467, 0.467):
        cube("CartShelfRail", (0, y, z + 0.035), (0.66, 0.020, 0.045), "DarkMetal", 0.003)
cylinder("CartHandle", (0.330, 0, 1.030), 0.020, 0.98, "DarkMetal",
         rotation=(math.pi / 2, 0, 0), edge=0)
for y in (-0.460, 0.460):
    cylinder("CartHandleStem", (0.330, y, 0.980), 0.014, 0.100, "DarkMetal", edge=0)
cube("CartHangingLinenBag", (-0.3325, 0.020, 0.505), (0.085, 0.460, 0.490), "Linen", 0.016)
for y in (-0.215, 0.255):
    cube("CartBagRim", (-0.333, y, 0.754), (0.076, 0.014, 0.018), "DarkMetal", 0.003)
cube("CartMopPocket", (0.3375, -0.335, 0.330), (0.075, 0.205, 0.320), "Linen", 0.011)
cylinder("CartMopPole", (0.310, -0.335, 0.610), 0.010, 0.720, "Wood", edge=0.001)
for y in (-0.365, -0.345, -0.325, -0.305):
    cube("MopFringe", (0.310, y, 0.218), (0.060, 0.020, 0.074), "Linen", 0.006)
for z in (0.550, 0.615, 0.680):
    cube("CartFoldedLinen", (0, 0.150, z), (0.50, 0.44, 0.060), "Linen", 0.009)
for y in (-0.280, 0.040, 0.330):
    cube("CartTopLinen", (0, y, 0.855), (0.44, 0.250, 0.080), "Linen", 0.011)
finish("HousekeepingCart", [75, 105, 105], note="Front -X; open frame, wheels, shelves, linen bag and mop pocket.")

for y in (-0.230, 0.230):
    beam("RackFoldingLeg", (-0.440, y, 0.040), (0.440, y, 0.385), 0.038)
    beam("RackFoldingLeg", (0.440, y, 0.040), (-0.440, y, 0.385), 0.038)
    for x in (-0.440, 0.440):
        cube("RackFoot", (x, y, 0.010), (0.080, 0.060, 0.020), "DarkMetal", 0.003)
for y in (-0.255, 0.255):
    cube("RackOuterRail", (0, y, 0.390), (1.00, 0.040, 0.040), "Wood", 0.005)
for x in (-0.420, -0.210, 0, 0.210, 0.420):
    cube("RackSlat", (x, 0, 0.395), (0.110, 0.470, 0.025), "Wood", 0.003)
cube("Suitcase", (0, 0, 0.5725), (0.800, 0.430, 0.315), "Wood", 0.021)
for y in (-0.140, 0.140):
    cube("SuitcaseStrap", (0, y, 0.5725), (0.807, 0.024, 0.322), "DarkMetal", 0.003)
    cube("SuitcaseLatch", (-0.408, y, 0.643), (0.012, 0.032, 0.037), "Letters", 0.003)
tube("SuitcaseHandle", [(-0.070, 0, 0.733), (-0.070, 0, 0.744),
                        (0.070, 0, 0.744), (0.070, 0, 0.733)], 0.006, "DarkMetal")
finish("LuggageRack", [100, 55, 75], tolerance_cm=0.2,
       note="Suitcase atop slatted folding luggage rack; base Z=0; curved handle is within 2mm nominal height.")

# Lift overlay: mounting plane X=0 and all visible geometry toward negative X.
cube("LiftBacking", (-0.0025, 0, 1.10), (0.005, 1.60, 2.20), "DarkMetal", 0)
for y in (-0.7725, 0.7725):
    cube("LiftJamb", (-0.024, y, 1.10), (0.032, 0.055, 2.20), "Letters", 0.003)
for z in (0.025, 2.175):
    cube("LiftHeaderSill", (-0.024, 0, z), (0.032, 1.49, 0.050), "Letters", 0.003)
for y in (-0.377, 0.377):
    cube("LiftDoorLeaf", (-0.018, y, 1.10), (0.022, 0.741, 2.10), "DarkMetal", 0.002)
    for z in (0.18, 0.66, 1.14, 1.62, 2.10):
        cube("LiftPanelJoint", (-0.0295, y, z), (0.001, 0.717, 0.002), "Letters", 0)
cube("LiftCentreSeam", (-0.016, 0, 1.10), (0.023, 0.010, 2.10), "DarkMetal", 0)
finish("LiftFace", [4, 160, 220], note="Local X [-4,0] cm; front -X; centre seam and two steel leaves.")

cube("LiftCallBacking", (-0.011, 0, 0.175), (0.022, 0.15, 0.35), "DarkMetal", 0.004)
cube("LiftCallFace", (-0.024, 0, 0.175), (0.005, 0.128, 0.328), "Letters", 0.001)
cylinder("LiftCallButton", (-0.0265, 0, 0.140), 0.025, 0.007, "DarkMetal",
         rotation=(0, math.pi / 2, 0), edge=0.0005)
cylinder("LiftCallIndicator", (-0.027, 0, 0.260), 0.008, 0.004, "DarkMetal",
         rotation=(0, math.pi / 2, 0), edge=0)
finish("LiftCallPanel", [3, 15, 35], note="Local X [-3,0] cm; front -X; round call button.")

clock_center_z = 0.175
cylinder("ClockCase", (-0.025, 0, clock_center_z), 0.175, 0.050, "DarkMetal",
         rotation=(0, math.pi / 2, 0), edge=0.002)
cylinder("ClockBlankDial", (-0.054, 0, clock_center_z), 0.154, 0.005, "Paper",
         rotation=(0, math.pi / 2, 0), edge=0)
for index in range(12):
    angle = index * math.pi / 6
    length = 0.017 if index % 3 == 0 else 0.012
    tick = cube("ClockTick", (-0.0595, -math.sin(angle) * 0.137,
                              clock_center_z + math.cos(angle) * 0.137),
                (0.001, 0.0035, length), "DarkMetal", 0)
    tick.rotation_euler[0] = angle
for length, angle, width in ((0.078, -math.pi / 3, 0.006), (0.111, 0.84, 0.004)):
    hand = cube("StoppedClockHand", (-0.0595, -math.sin(angle) * length / 2,
                                     clock_center_z + math.cos(angle) * length / 2),
                (0.001, width, length), "DarkMetal", 0)
    hand.rotation_euler[0] = angle
cylinder("ClockHandHub", (-0.0595, 0, clock_center_z), 0.009, 0.001, "DarkMetal",
         rotation=(0, math.pi / 2, 0), edge=0)
finish("WallClock", [6, 35, 35], note="Blank vertical YZ dial and stopped hands project ahead of case; front -X; local X [-6,0] cm.")

assert len(assets) == 15
assert len({row["key"] for row in assets}) == 15
assert all(obj.type == "MESH" for obj in bpy.context.scene.objects)
assert len(bpy.context.scene.objects) == 15
bpy.context.scene["kit_units"] = "metres"
bpy.context.scene["asset_count"] = len(assets)
bpy.context.scene["purpose"] = "Unplaced hotel operations prototypes; no collision or placements"
bpy.ops.wm.save_as_mainfile(filepath=str(KIT))
(OUT / "ImportManifest.json").write_text(json.dumps({
    "units": "cm", "source_units": "metres", "assets": assets,
}, indent=2), encoding="utf-8")

# Independent exported-file validation, using a disposable empty import scene.
verified = []
for row in assets:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    path = OUT / row["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["source_sha256"]
    bpy.ops.import_scene.fbx(filepath=str(path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert len(meshes) == 1, (row["key"], "expected one mesh", len(meshes))
    low, high, dimensions = measured(meshes[0])
    for axis in range(3):
        assert abs(dimensions[axis] - row["dimensions_cm"][axis]) < 0.01, (row["key"], dimensions)
        assert abs(low[axis] - row["bounds_cm"][0][axis]) < 0.01, (row["key"], low)
        assert abs(high[axis] - row["bounds_cm"][1][axis]) < 0.01, (row["key"], high)
    assert meshes[0].location.length < 0.0001, (row["key"], "imported origin drift")
    verified.append({"key": row["key"], "name": row["name"],
                     "dimensions_cm": dimensions, "bounds_cm": [low, high]})
(OUT / "IndependentFBXVerification.json").write_text(json.dumps({
    "passed": True, "asset_count": len(verified), "assets": verified,
}, indent=2), encoding="utf-8")

# Restore editable sources and reacquire materials after reload (old RNA refs die).
bpy.ops.wm.open_mainfile(filepath=str(KIT))
mats = {name: bpy.data.materials[name] for name in COLORS}
for material in mats.values():
    material.use_fake_user = True
for row in assets:
    obj = bpy.data.objects[row["name"]]
    assert obj.type == "MESH" and obj.location.length < 0.0001
    assert [material.name for material in obj.data.materials] == row["materials"]
    assert all(abs(value - 1.0) < 1e-6 for value in obj.scale)
# Source-only preview grid. Mesh-local origins and all exported FBXs remain at zero.
# These translations are inspection conveniences, not level placement instructions.
for index, row in enumerate(assets):
    obj = bpy.data.objects[row["name"]]
    obj.location = ((index % 3) * 3.5, (index // 3) * 3.2, 0.0)
    obj["source_preview_position_m"] = tuple(obj.location)
bpy.context.scene["source_preview_layout"] = "3 columns; 3.5m X spacing, 3.2m Y spacing; all FBX origins at zero"
bpy.context.scene["independent_fbx_validation_passed"] = True
bpy.ops.wm.save_as_mainfile(filepath=str(KIT))
print("HOTEL_OPERATIONS_SOURCE_PASS assets=%d" % len(assets))
