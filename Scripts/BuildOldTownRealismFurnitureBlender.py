"""Author V4 hotel furniture replacements without editing original assets or UE.

Run an isolated Blender --background --factory-startup --python this script.
Every mesh is authored in real centimetres, then normalized to the old 100 cm
cube coordinates. Existing actor locations, rotations and scales remain usable.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "Saved/CodexOutputs/SanitaryFinish_20261012"
OUT = ROOT / "SourceArt/OldTownRealism_20261012/Furniture"
ROLES = ("Wood", "PaintedWood", "Linen", "LinenSeam", "DarkMetal", "Chrome", "Ceramic", "Stone")
CUBE_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def source_rows():
    report = load_json(INPUT / "BuildReport.json")["hotel_v4"]
    snapshots = load_json(INPUT / "AfterSnapshot.json")["actors"]
    all_boxes = {r["id"]: r for r in report["placed_boxes"]}
    rows = []
    for row in all_boxes.values():
        ident, role = row["id"], row["role"]
        kind = None
        if "_Bed" in ident:
            kind = next((s for s in ("Base", "Mattress", "Head", "Pillow") if ident.endswith(s)), None)
            if kind:
                kind = "Bed" + kind
        elif ident.endswith("_Wardrobe"):
            kind = "WardrobeBody"
        elif ident.endswith("_Wardrobe_DoorTrim"):
            kind = "WardrobeDoors"
        elif role == "table":
            kind = "TableTop"
        elif role == "table_leg":
            kind = "TableLeg"
        elif role == "seat":
            kind = "SeatBase" if ident.endswith("_Base") else "SeatBack"
        elif role == "reception":
            kind = "ReceptionBody"
        elif role == "reception_top":
            kind = "ReceptionTop"
        if not kind:
            continue
        state = snapshots[row["actor"]]
        components = [c for c in state["components"] if c.get("mesh")]
        assert len(components) == 1 and components[0]["mesh"] == "/Engine/BasicShapes/Cube.Cube", row["actor"]
        dims = [round(row["world_max"][i] - row["world_min"][i], 5) for i in range(3)]
        assert all(abs(dims[i] / 100 - state["scale"][i]) < 1e-7 for i in range(3))
        orientation = None
        if kind in ("SeatBase", "SeatBack"):
            stem = ident.rsplit("_", 1)[0]
            base, back = all_boxes[stem + "_Base"], all_boxes[stem + "_Back"]
            delta = [(back["world_min"][i] + back["world_max"][i] - base["world_min"][i] - base["world_max"][i]) / 2 for i in range(2)]
            axis = max(range(2), key=lambda i: abs(delta[i]))
            orientation = ("X" if axis == 0 else "Y") + ("P" if delta[axis] > 0 else "N")
        key = kind + "_" + "x".join(("%g" % v).replace(".", "p") for v in dims)
        if orientation:
            key += "_" + orientation
        extension = 5.0 if kind == "BedBase" else 8.0 if kind == "SeatBase" else 0.0
        rows.append(dict(key=key, kind=kind, actor_label=row["actor"],
                         source_id=ident, world_dimensions_cm=dims,
                         position_cm=state["location"], rotation=state["rotation"],
                         actor_scale=state["scale"], original_world_bounds_cm=[row["world_min"], row["world_max"]],
                         orientation=orientation, grounded_extension_cm=extension,
                         collision_requested=row["collision"],
                         original_material_slots=components[0]["materials"]))
    assert len(rows) == 680, len(rows)
    return rows


def early_manifest(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["key"]].append(row)
    manifest = dict(schema_version=1, status="AUTHORING", actor_count=len(rows), variant_count=len(groups),
                    source_build_report_sha256=sha(INPUT / "BuildReport.json"),
                    source_snapshot_sha256=sha(INPUT / "AfterSnapshot.json"),
                    source_map_sha256=load_json(INPUT / "BuildReport.json")["map_sha256"],
                    source_script_sha256=sha(__file__),
                    coordinates="Blender +X/+Y/+Z = original UE actor local +X/+Y/+Z; FBX -Y forward Z up; normalized local [-50,50] centimetres nominal bounds",
                    export_units="metres converted to centimetres by FBX importer",
                    material_roles=list(ROLES), variants=[], actors=rows)
    for key, members in sorted(groups.items()):
        row = members[0]
        manifest["variants"].append(dict(key=key, kind=row["kind"], mesh_name="SM_OTS_Real_" + key,
            source_actor_labels=[r["actor_label"] for r in members], instance_count=len(members),
            world_dimensions_cm=row["world_dimensions_cm"], orientation=row["orientation"],
            grounded_extension_cm=row["grounded_extension_cm"],
            fbx_file="SM_OTS_Real_" + key + ".fbx"))
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "ModelDataManifest.json", manifest)
    return manifest


def blender_build(manifest):
    import bpy
    import bmesh
    from mathutils import Vector

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data in list(bpy.data.meshes):
        if not data.users:
            bpy.data.meshes.remove(data)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    colors = {"Wood": (.15, .079, .039, 1), "PaintedWood": (.115, .16, .13, 1),
              "Linen": (.35, .34, .265, 1), "LinenSeam": (.26, .25, .19, 1),
              "DarkMetal": (.065, .06, .045, 1), "Chrome": (.42, .43, .40, 1),
              "Ceramic": (.53, .51, .43, 1), "Stone": (.055, .06, .055, 1)}
    mats = {}
    for role in ROLES:
        mat = bpy.data.materials.new(role)
        mat.diffuse_color = colors[role]
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = colors[role]
        bsdf.inputs["Roughness"].default_value = .9 if "Linen" in role else .6
        bsdf.inputs["Metallic"].default_value = .8 if role in ("DarkMetal", "Chrome") else 0
        mats[role] = mat

    current_parts = []
    part_counter = 0

    def mesh(vertices, faces, role="Wood", smooth=False, bevel=0):
        nonlocal part_counter
        part_counter += 1
        name = "FurniturePart_%05d" % part_counter
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        data.materials.append(mats[role])
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if bevel > 0:
            mod = obj.modifiers.new("Real edge radius", "BEVEL")
            mod.width = bevel
            mod.segments = 3
            mod.limit_method = "ANGLE"
            bpy.ops.object.modifier_apply(modifier=mod.name)
            smooth = True
        for polygon in data.polygons:
            polygon.use_smooth = smooth
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
        if bevel:
            try:
                mod = obj.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
                mod.keep_sharp = True
                mod.weight = 50
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:
                pass
        obj.select_set(False)
        current_parts.append(obj)
        return obj

    def box(center, size, role="Wood", bevel=.18):
        x, y, z = [v / 2 for v in size]
        points = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                  (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
        return mesh([tuple(p[i] + center[i] for i in range(3)) for p in points], CUBE_FACES,
                    role, bevel=min(bevel, min(size) * .23))

    def frustum(center, bottom_xy, top_xy, height, role="Wood", bevel=.15):
        verts = []
        for dims, z in ((bottom_xy, -height / 2), (top_xy, height / 2)):
            for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                verts.append((center[0] + x * dims[0] / 2, center[1] + y * dims[1] / 2, center[2] + z))
        return mesh(verts, CUBE_FACES, role, bevel=bevel)

    def cylinder(start, end, radius, role="DarkMetal", sides=16):
        a, b = Vector(start), Vector(end)
        direction = (b - a).normalized()
        helper = Vector((0, 0, 1)) if abs(direction.z) < .9 else Vector((0, 1, 0))
        u = direction.cross(helper).normalized()
        v = direction.cross(u)
        vertices = [tuple(p + radius * (math.cos(2 * math.pi * i / sides) * u + math.sin(2 * math.pi * i / sides) * v))
                    for p in (a, b) for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
        faces.extend((i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides))
        return mesh(vertices, faces, role, smooth=True)

    def loop_tube(points, radius=.12, role="LinenSeam", sides=6):
        n = len(points)
        vertices = []
        for i, point in enumerate(points):
            tangent = (Vector(points[(i + 1) % n]) - Vector(points[(i - 1) % n])).normalized()
            normal = Vector((-tangent.y, tangent.x, 0)).normalized()
            vertical = tangent.cross(normal).normalized()
            for j in range(sides):
                ang = 2 * math.pi * j / sides
                vertices.append(tuple(Vector(point) + radius * (normal * math.cos(ang) + vertical * math.sin(ang))))
        faces = [(i * sides + j, i * sides + (j + 1) % sides,
                  ((i + 1) % n) * sides + (j + 1) % sides, ((i + 1) % n) * sides + j)
                 for i in range(n) for j in range(sides)]
        return mesh(vertices, faces, role, smooth=True)

    def cloth(center, size, pillow=False, role="Linen", nx=28, ny=28):
        """Closed grid casing with a stuffed crown, compressed edge and small folds."""
        x, y, z = size
        vertices = []
        for side in (1, -1):
            for j in range(ny + 1):
                v = 2 * j / ny - 1
                for i in range(nx + 1):
                    u = 2 * i / nx - 1
                    px = x / 2 * u * (1 - .055 * abs(v) ** 10)
                    py = y / 2 * v * (1 - .055 * abs(u) ** 10)
                    crown = max(0, (1 - u * u) * (1 - v * v))
                    if pillow:
                        pz = side * (z * (.11 + .39 * crown ** .54))
                        fold = .19 * math.sin(u * 22 + v * 3) * math.exp(-((abs(v) - .82) / .2) ** 2)
                        fold += .10 * math.sin(v * 31 - u * 2) * math.exp(-((abs(u) - .88) / .14) ** 2)
                        pz += side * fold * crown ** .15
                    else:
                        pz = side * (z * (.31 + .19 * crown ** .32))
                        # Cloth folds under 2 mm; the broad shape stays a mattress.
                        pz += side * .13 * math.sin(31 * u + 4 * v) * crown ** .35 * math.exp(-((abs(v) - .78) / .24) ** 2)
                    vertices.append((center[0] + px, center[1] + py, center[2] + pz))
        stride = nx + 1
        count = stride * (ny + 1)
        faces = []
        for side in range(2):
            offset = side * count
            for j in range(ny):
                for i in range(nx):
                    a = offset + j * stride + i
                    f = (a, a + 1, a + stride + 1, a + stride)
                    faces.append(f if side == 0 else tuple(reversed(f)))
        border = list(range(nx + 1))
        border += [j * stride + nx for j in range(1, ny + 1)]
        border += [ny * stride + i for i in range(nx - 1, -1, -1)]
        border += [j * stride for j in range(ny - 1, 0, -1)]
        for a, b in zip(border, border[1:] + border[:1]):
            faces.append((a + count, b + count, b, a))
        mesh(vertices, faces, role, smooth=True)
        seam = []
        for index in border:
            point = vertices[index]
            seam.append((center[0] + (point[0] - center[0]) * .992,
                         center[1] + (point[1] - center[1]) * .992, center[2]))
        loop_tube(seam, .095 if pillow else .12)
        if not pillow:
            for side in (-1, 1):
                pts = [(a, b, center[2] + side * z * .24) for a, b, _ in seam]
                loop_tube(pts, .08)

    def bed_base(d):
        x, y, h = d
        low, top = -h / 2 - 5, h / 2
        # Feet reach the original room floor; outside X/Y bounds remain exact.
        for a in (-1, 1):
            for b in (-1, 1):
                frustum((a * (x / 2 - 9), b * (y / 2 - 8), (low + top - 6) / 2),
                        (7, 7), (8, 8), top - 6 - low, "Wood", .35)
        for side in (-1, 1):
            box((0, side * (y / 2 - 3), top - 4), (x, 6, 8), "Wood", .45)
            box((side * (x / 2 - 3), 0, top - 4), (6, y - 12, 8), "Wood", .35)
        slat_count = max(12, round(x / 13))
        for i in range(slat_count):
            px = -x / 2 + 9 + i * (x - 18) / (slat_count - 1)
            box((px, 0, top - 1.2), (7.5, y - 12, 2.4), "PaintedWood", .15)
        for a in (-1, 1):
            for b in (-1, 1):
                box((a * (x / 2 - 5.8), b * (y / 2 - 3.08), top - 4.3), (5, .7, 5), "DarkMetal", .09)

    def bed_head(d):
        depth, width, height = d
        box((0, 0, 0), (depth - 2, width - 10, height - 8), "Wood", .4)
        for s in (-1, 1):
            box((0, s * (width / 2 - 3.5), 0), (depth, 7, height), "Wood", .5)
            box((0, 0, s * (height / 2 - 3.1)), (depth - .3, width - 9, 6), "Wood", .3)
        panels = 2 if width <= 100 else 3
        pw = (width - 18) / panels
        for i in range(panels):
            pos = -width / 2 + 9 + pw * (i + .5)
            box((-depth / 2 + 1.1, pos, 0), (1.6, pw - 3, height - 22), "PaintedWood", .24)
            for z in (-height / 2 + 12, height / 2 - 12):
                box((-depth / 2 + .5, pos, z), (1, pw - 4, 1.8), "Wood", .18)

    def wardrobe_body(d):
        x, y, z = d
        for side in (-1, 1):
            box((side * (x / 2 - 2.5), 0, 0), (5, y, z), "Wood", .35)
            box((0, 0, side * (z / 2 - 2)), (x - 10, y, 4), "Wood", .35)
        box((0, y / 2 - 1, 0), (x - 10, 2, z - 8), "PaintedWood", .16)
        box((0, 0, -z / 2 + 5), (x - 7, y - 2, 6), "Wood", .24)
        box((0, -y / 2 + 1.6, 0), (3, 3.2, z - 7), "Wood", .12)
        # The old door-trim envelope is 20 cm shorter than the cabinet case.
        # Fill both frontage bands rather than leave a dark open upper slot.
        for side in (-1, 1):
            box((0, -y / 2 + 1.6, side * (z / 2 - 7)), (x - 10, 3.2, 6), "Wood", .24)
        for height in (-z * .22, z * .27):
            box((0, 2, height), (x - 8, y - 8, 2.4), "PaintedWood", .16)
        cylinder((-x / 2 + 6, 0, z * .32), (x / 2 - 6, 0, z * .32), 1.15, "DarkMetal")

    def wardrobe_doors(d):
        x, y, z = d
        doorwidth = (x - 1.4) / 2
        for side in (-1, 1):
            cx = side * (doorwidth / 2 + .7)
            # The original trim permits only 17 mm depth. Raised relief is recessed.
            box((cx, .38, 0), (doorwidth, .94, z), "Wood", .15)
            for edge in (-1, 1):
                box((cx + edge * (doorwidth / 2 - 3), -.16, 0), (6, .95, z), "Wood", .1)
                box((cx, -.16, edge * (z / 2 - 3)), (doorwidth - 12, .95, 6), "Wood", .1)
            for panelz, panelheight in ((z * .14, z * .57), (-z * .34, z * .23)):
                box((cx, .0, panelz), (doorwidth - 15, .6, panelheight), "PaintedWood", .11)
            hx = cx - side * (doorwidth / 2 - 8)
            for hz in (-6, 6):
                cylinder((hx, -.3, hz), (hx, -.64, hz), .45, "DarkMetal")
            cylinder((hx, -.68, -6), (hx, -.68, 6), .16, "DarkMetal", 12)

    def table_top(d):
        x, y, z = d
        board_count = 4 if x >= 75 else 3
        width = x / board_count
        for i in range(board_count):
            actual_width = width - .08 if 0 < i < board_count - 1 else width - .04
            cx = -x / 2 + width * (i + .5)
            cx += -.02 if i == 0 else .02 if i == board_count - 1 else 0
            box((cx, 0, 0), (actual_width, y, z), "Wood", .3)
        # Small joinery witness plugs stay embedded on the underside.
        for s in (-1, 1):
            for t in (-1, 1):
                cylinder((s * (x / 2 - 6), t * (y / 2 - 7), -z / 2 + .12),
                         (s * (x / 2 - 6), t * (y / 2 - 7), -z / 2 + .4), .48, "DarkMetal", 12)

    def table_leg(d):
        x, y, z = d
        frustum((0, 0, .75), (x * .73, y * .73), (x, y), z - 1.5, "Wood", .2)
        box((0, 0, -z / 2 + .8), (x * .76, y * .76, 1.6), "DarkMetal", .13)
        box((0, 0, z / 2 - 2.2), (x, y, 2.2), "DarkMetal", .15)

    def seat_base(d, orient):
        x, y, z = d
        low, upper = -z / 2 - 8, z / 2
        axis = 0 if orient[0] == "X" else 1
        width, depth = d[1 - axis], d[axis]
        loveseat = width > 100
        def mapped(u, v, height):
            return (v, u, height) if axis == 0 else (u, v, height)
        def mapped_size(w, deep, height):
            return (deep, w, height) if axis == 0 else (w, deep, height)
        for a in (-1, 1):
            for b in (-1, 1):
                frustum((a * (x / 2 - 6), b * (y / 2 - 6), (low + upper - 11) / 2),
                        (4, 4), (5.8, 5.8), upper - 11 - low, "Wood", .3)
        for s in (-1, 1):
            box((s * (x / 2 - 3), 0, upper - 12), (6, y, 6), "Wood", .3)
            box((0, s * (y / 2 - 3), upper - 12), (x - 12, 6, 6), "Wood", .3)
        if loveseat:
            # Arm rests remain inside the base's old height envelope.
            for side in (-1, 1):
                box(mapped(side * (width / 2 - 5), 0, upper - 4), mapped_size(10, depth, 8), "Linen", 1.8)
            cushion_width = (width - 21) / 2
            before = len(current_parts)
            for side in (-1, 1):
                cloth((side * (cushion_width / 2 + .5), 0, upper - 5.8), (cushion_width, depth - 3, 11.6),
                      pillow=True, nx=24, ny=24)
            if axis == 0:
                for part in current_parts[before:]:
                    for vertex in part.data.vertices:
                        u, v, height = vertex.co
                        vertex.co = mapped(u, v, height)
        else:
            cloth((0, 0, upper - 5), (x, y, 10), pillow=True, nx=24, ny=24)

    def seat_back(d, orient):
        x, y, z = d
        axis = 0 if orient[0] == "X" else 1
        rear = 1 if orient[1] == "P" else -1
        thick = d[axis]
        width = d[1 - axis]
        # Wood posts form the physical support; a padded crown occupies the front.
        def mapped(u, v, height):
            return (v, u, height) if axis == 0 else (u, v, height)
        def mapped_size(w, depth, height):
            return (depth, w, height) if axis == 0 else (w, depth, height)
        for side in (-1, 1):
            box(mapped(side * (width / 2 - 2.8), rear * (thick / 2 - 2), 0),
                mapped_size(5.6, 4, z), "Wood", .45)
        for height in (-z / 2 + 3, z / 2 - 3):
            box(mapped(0, rear * (thick / 2 - 2), height), mapped_size(width - 8, 4, 6), "Wood", .4)
        # Padded back uses a stuffed cap turned from Z thickness into front depth.
        before = len(current_parts)
        segments = 2 if width > 100 else 1
        pw = (width - 11) / segments
        for i in range(segments):
            offset = -width / 2 + 5.5 + pw * (i + .5)
            cloth((offset, 0, 0), (pw - .8, z - 9, thick - 3.2), pillow=True, nx=24, ny=26)
        for part in current_parts[before:]:
            for vertex in part.data.vertices:
                u, height, normal = vertex.co
                center_depth = -rear * 1.05
                vertex.co = mapped(u, center_depth - rear * normal, height)
        for side in (-1, 1):
            cylinder(mapped(side * (width / 2 - 2.8), rear * (thick / 2 - .35), -z * .3),
                     mapped(side * (width / 2 - 2.8), rear * (thick / 2 - .35), -z * .3 + .3), .25, "DarkMetal", 10)

    def reception_body(d):
        x, y, z = d
        # Customer frontage is original -X; staff shelving is original +X.
        box((0, 0, -z / 2 + 5), (x, y, 10), "Wood", .3)
        box((0, 0, z / 2 - 2.5), (x, y, 5), "Wood", .35)
        for side in (-1, 1):
            box((0, side * (y / 2 - 2), 0), (x, 4, z - 8), "Wood", .35)
        box((-x / 2 + 3.2, 0, 0), (3.8, y - 7, z - 8), "Wood", .2)
        count = 6
        width = (y - 14) / count
        for i in range(count):
            center = -y / 2 + 7 + width * (i + .5)
            box((-x / 2 + 1.45, center, 0), (2.5, width - 4, z - 22), "PaintedWood", .28)
            for s in (-1, 1):
                box((-x / 2 + .7, center + s * (width / 2 - 2), 0), (1.4, 3, z - 12), "Wood", .16)
        for height in (-z * .18, z * .18):
            box((8, 0, height), (x - 25, y - 8, 2.8), "PaintedWood", .22)
        for yloc in (-y / 4, 0, y / 4):
            box((8, yloc, 0), (x - 25, 2.5, z - 12), "Wood", .2)

    collection = bpy.data.collections.new("V4_RealFurniture_NormalizedParts")
    bpy.context.scene.collection.children.link(collection)
    for variant in manifest["variants"]:
        current_parts.clear()
        kind, d = variant["kind"], variant["world_dimensions_cm"]
        if kind == "BedBase":
            bed_base(d)
        elif kind == "BedMattress":
            cloth((0, 0, 0), d, pillow=False, nx=36, ny=24)
        elif kind == "BedHead":
            bed_head(d)
        elif kind == "BedPillow":
            if d[1] > 100:
                width = (d[1] - 2.2) / 2
                for side in (-1, 1):
                    cloth((0, side * (width / 2 + 1.1), 0), (d[0], width, d[2]), pillow=True)
            else:
                cloth((0, 0, 0), d, pillow=True)
        elif kind == "WardrobeBody":
            wardrobe_body(d)
        elif kind == "WardrobeDoors":
            wardrobe_doors(d)
        elif kind == "TableTop":
            table_top(d)
        elif kind == "TableLeg":
            table_leg(d)
        elif kind == "SeatBase":
            seat_base(d, variant["orientation"])
        elif kind == "SeatBack":
            seat_back(d, variant["orientation"])
        elif kind == "ReceptionBody":
            reception_body(d)
        elif kind == "ReceptionTop":
            box((0, 0, 0), d, "Stone", .55)
        else:
            raise ValueError(kind)

        # Join closed parts explicitly; UVs are derived from real centimetres.
        vertices, faces, face_roles, exported_normals = [], [], [], []
        for obj in current_parts:
            # Compute normals while this part still has its physical proportions.
            # After axis normalization, custom normals undergo the inverse transpose.
            bm_part = bmesh.new()
            bm_part.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm_part, faces=list(bm_part.faces))
            bm_part.to_mesh(obj.data)
            bm_part.free()
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            mod = obj.modifiers.new("Physical proportion normals", "WEIGHTED_NORMAL")
            mod.keep_sharp = True
            mod.weight = 50
            bpy.ops.object.modifier_apply(modifier=mod.name)
            obj.select_set(False)
            obj.data.calc_loop_triangles()
            offset = len(vertices)
            vertices.extend(tuple(v.co) for v in obj.data.vertices)
            for tri in obj.data.loop_triangles:
                faces.append(tuple(offset + i for i in tri.vertices))
                face_roles.append(obj.data.materials[tri.material_index].name)
                for loop_index in tri.loops:
                    normal = obj.data.corner_normals[loop_index].vector
                    transformed = Vector(tuple(normal[i] * d[i] for i in range(3))).normalized()
                    exported_normals.append(tuple(transformed))
        extension = variant["grounded_extension_cm"]
        lo = [-v / 2 for v in d]
        lo[2] -= extension
        hi = [v / 2 for v in d]
        # Small stitches/bevels never exceed the approved geometric envelope.
        physical = [tuple(min(hi[i], max(lo[i], v[i])) for i in range(3)) for v in vertices]
        vertices = [tuple(v[i] / d[i] for i in range(3)) for v in physical]
        data = bpy.data.meshes.new(variant["mesh_name"])
        data.from_pydata(vertices, [], faces)
        data.update()
        used_roles = [role for role in ROLES if role in face_roles]
        for role in used_roles:
            data.materials.append(mats[role])
        for polygon, role in zip(data.polygons, face_roles):
            polygon.material_index = used_roles.index(role)
            polygon.use_smooth = True
        obj = bpy.data.objects.new(variant["mesh_name"], data)
        collection.objects.link(obj)
        # Planar real-scale UV projection, with each face using its dominant axis.
        layer = data.uv_layers.new(name="RealScaleUV")
        for polygon in data.polygons:
            points = [Vector(physical[i]) for i in polygon.vertices]
            normal = (points[1] - points[0]).cross(points[2] - points[0])
            dominant = max(range(3), key=lambda i: abs(normal[i]))
            axes = [i for i in range(3) if i != dominant]
            for loop_index, vertex_index in zip(polygon.loop_indices, polygon.vertices):
                point = physical[vertex_index]
                layer.data[loop_index].uv = (point[axes[0]] / 100, point[axes[1]] / 100)
        for old in list(current_parts):
            data_old = old.data
            bpy.data.objects.remove(old, do_unlink=True)
            if not data_old.users:
                bpy.data.meshes.remove(data_old)
        current_parts.clear()
        bm = bmesh.new()
        bm.from_mesh(data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        boundary = sum(not e.is_manifold for e in bm.edges)
        degenerate = sum(f.calc_area() <= 1e-14 for f in bm.faces)
        if degenerate:
            write_json(OUT / "DegenerateDebug.json", dict(variant=variant["key"],
                faces=[dict(vertices=[list(v.co) for v in f.verts], material=f.material_index)
                       for f in bm.faces if f.calc_area() <= 1e-14]))
        volume = bm.calc_volume(signed=True)
        bm.to_mesh(data)
        bm.free()
        data.normals_split_custom_set(exported_normals)
        data.update()
        data.calc_tangents(uvmap="RealScaleUV")
        bad_tangents = sum(not all(math.isfinite(v) for v in loop.tangent) or loop.tangent.length < .9 for loop in data.loops)
        assert bad_tangents == 0, (variant["key"], "invalid tangents", bad_tangents)
        assert len(data.vertices) and len(data.polygons) and boundary == 0 and degenerate == 0 and volume > 0, (variant["key"], boundary, degenerate, volume)
        local_bounds = [[min(v.co[i] * 100 for v in data.vertices) for i in range(3)],
                        [max(v.co[i] * 100 for v in data.vertices) for i in range(3)]]
        world_bounds = [[min(v[i] for v in physical) for i in range(3)], [max(v[i] for v in physical) for i in range(3)]]
        obj["variant_key"] = variant["key"]
        obj["original_actor_count"] = variant["instance_count"]
        obj["world_dimensions_cm"] = d
        obj["grounded_extension_cm"] = extension
        obj["local_pivot"] = "Original centered cube actor pivot"
        obj["material_roles"] = ",".join(used_roles)
        data.calc_loop_triangles()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        fbx_path = OUT / variant["fbx_file"]
        bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True,
            global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
            axis_forward="-Y", axis_up="Z", use_space_transform=True,
            bake_space_transform=False, object_types={"MESH"}, use_mesh_modifiers=True,
            mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False,
            bake_anim=False, path_mode="AUTO")
        variant.update(local_bounds_cm=local_bounds, physical_mesh_bounds_cm=world_bounds,
            world_bounds_delta_cm=[[world_bounds[0][i] + d[i] / 2 for i in range(3)],
                                   [world_bounds[1][i] - d[i] / 2 for i in range(3)]],
            vertices=len(data.vertices), faces=len(data.polygons), triangles=len(data.loop_triangles),
            material_roles=used_roles, material_slots=used_roles,
            uv_mapping="Per triangle dominant-normal planar projection of physical centimetre coordinates /100; 1 UV unit=1 metre; no normalized 0..1 rescaling",
            normals="Physical geometry weighted corner normals transformed by axis normalization inverse transpose",
            tangent_space_verified=True, invalid_tangent_count=bad_tangents,
            closed_manifold=True, boundary_or_nonmanifold_edges=boundary,
            degenerate_faces=degenerate, signed_local_volume_m3=volume,
            source_file_sha256=sha(fbx_path), fbx_path=str(fbx_path))
        obj.hide_set(True)
        obj.hide_render = True
        print("FURNITURE_VARIANT", variant["key"], len(data.vertices), len(data.loop_triangles), flush=True)
        write_json(OUT / "ModelDataManifest.json", manifest)
    blend_path = OUT / "OldTownRealFurniture.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    manifest.update(status="COMPLETE", blend_file=str(blend_path), blend_sha256=sha(blend_path),
                    source_script_sha256=sha(__file__),
                    total_variant_vertices=sum(v["vertices"] for v in manifest["variants"]),
                    total_variant_triangles=sum(v["triangles"] for v in manifest["variants"]),
                    total_instanced_triangles=sum(v["triangles"] * v["instance_count"] for v in manifest["variants"]),
                    closed_meshes_verified=True, no_original_files_modified=True)
    write_json(OUT / "ModelDataManifest.json", manifest)
    print("FURNITURE_COMPLETE", len(manifest["variants"]), len(manifest["actors"]), flush=True)


def render_previews(manifest):
    """Source geometry review, separate from the saved normalized asset library."""
    import bpy
    from mathutils import Vector
    bpy.ops.wm.open_mainfile(filepath=manifest["blend_file"])
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 880
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (.10, .12, .12, 1)
    background.inputs["Strength"].default_value = .35
    scene.view_settings.view_transform = "AgX"
    for original in bpy.data.objects:
        original.hide_set(True)
        original.hide_render = True
    bpy.ops.mesh.primitive_plane_add(size=18, location=(0, 0, -.006))
    ground = bpy.context.object
    ground.name = "SourceReviewGround"
    groundmat = bpy.data.materials.new("SourceReviewGround")
    groundmat.diffuse_color = (.14, .145, .13, 1)
    groundmat.use_nodes = True
    node = next(n for n in groundmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    node.inputs["Base Color"].default_value = groundmat.diffuse_color
    node.inputs["Roughness"].default_value = .85
    ground.data.materials.append(groundmat)
    for name, pos, energy, size in (("Key", (-3, -4, 5), 800, 4),
                                   ("Fill", (4, 2, 4), 600, 3),
                                   ("Rim", (0, 3, 5), 700, 3)):
        light = bpy.data.lights.new("SourceReview" + name, "AREA")
        light.energy = energy
        light.shape = "DISK"
        light.size = size
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (Vector((0, 0, .5)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    camdata = bpy.data.cameras.new("SourceReviewCamera")
    cam = bpy.data.objects.new(camdata.name, camdata)
    scene.collection.objects.link(cam)
    scene.camera = cam
    camdata.lens = 52
    actors = {r["actor_label"]: r for r in manifest["actors"]}
    variants = {v["key"]: v for v in manifest["variants"]}
    displayed = []

    def assembly(labels, center=(0, 0), anchor_label=None):
        anchor = actors[anchor_label or labels[0]]
        floor = anchor["original_world_bounds_cm"][0][2] - (8 if anchor["kind"] == "SeatBase" else 5 if anchor["kind"] == "BedBase" else 0)
        origin = [anchor["position_cm"][0], anchor["position_cm"][1], floor]
        for label in labels:
            row = actors[label]
            proto = bpy.data.objects[variants[row["key"]]["mesh_name"]]
            obj = proto.copy()
            scene.collection.objects.link(obj)
            obj.name = "Review_" + row["source_id"]
            obj.hide_set(False)
            obj.hide_render = False
            obj.scale = row["actor_scale"]
            obj.location = ((row["position_cm"][0] - origin[0]) / 100 + center[0],
                            (row["position_cm"][1] - origin[1]) / 100 + center[1],
                            (row["position_cm"][2] - origin[2]) / 100)
            displayed.append(obj)

    def render(name, camera_pos, target):
        cam.location = camera_pos
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = OUT / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return str(path)

    single = actors["OTS_HotelV4_Room201_Bed0Base"]
    double = next(r for r in manifest["actors"] if r["kind"] == "BedBase" and r["world_dimensions_cm"][1] == 160)
    for row, pos in ((single, (0, -1.08)), (double, (0, 1.05))):
        stem = row["actor_label"][:-4]
        assembly([stem + suffix for suffix in ("Base", "Mattress", "Head", "Pillow")], pos, stem + "Base")
    first = render("Preview_BedsSoftGoods_Final.png", (-4.8, -5.3, 4.0), (0, 0, .45))
    for obj in displayed:
        bpy.data.objects.remove(obj, do_unlink=True)
    displayed.clear()
    prefix = "OTS_HotelV4_Room201_"
    assembly([prefix + "Wardrobe", prefix + "Wardrobe_DoorTrim"], (0, 1.15), prefix + "Wardrobe")
    assembly([prefix + "Armchair_Base", prefix + "Armchair_Back"], (.35, -.95), prefix + "Armchair_Base")
    breakfast = next(r for r in manifest["actors"] if r["kind"] == "SeatBase" and r["world_dimensions_cm"][0] == 45 and r["orientation"] == "XP")
    stem = breakfast["actor_label"][:-5]
    assembly([stem + "_Base", stem + "_Back"], (-1.15, -.75), stem + "_Base")
    second = render("Preview_WardrobeChairs_Final.png", (-4.6, -5.8, 3.8), (0, .12, .9))
    manifest["source_geometry_previews"] = [first, second]
    manifest["preview_note"] = "Physical-scale source geometry rendered with simple role colors; final Unreal PBR materials are supplied by the main realism pipeline."
    manifest["source_script_sha256"] = sha(__file__)
    write_json(OUT / "ModelDataManifest.json", manifest)
    print("FURNITURE_PREVIEWS_COMPLETE", first, second, flush=True)


def export_axis_probe():
    import bpy
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    lo, hi = (-2, -7, -13), (3, 11, 17)
    vertices = [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]),
                (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]),
                (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]
    data = bpy.data.meshes.new("AxisProbe")
    data.from_pydata([tuple(c / 100 for c in v) for v in vertices], [], CUBE_FACES)
    data.update()
    obj = bpy.data.objects.new("AxisProbe", data)
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    path = OUT / "AxisProbe.fbx"
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Y", axis_up="Z", use_space_transform=True,
        bake_space_transform=False, object_types={"MESH"}, use_mesh_modifiers=True,
        mesh_smooth_type="FACE", use_tspace=False, add_leaf_bones=False,
        bake_anim=False, path_mode="AUTO")
    write_json(OUT / "AxisProbeManifest.json", dict(expected_UE_local_min_cm=lo,
        expected_UE_local_max_cm=hi, source_vertices_cm=vertices,
        fbx_file=str(path), fbx_sha256=sha(path),
        note="Asymmetric bounds identify signed axis permutation after UE FBX import; not part of33 formal model variants."))
    print("AXIS_PROBE_READY", str(path), flush=True)


if __name__ == "__main__":
    if "--axis-probe-only" in sys.argv:
        export_axis_probe()
    elif "--preview-only" in sys.argv:
        render_previews(load_json(OUT / "ModelDataManifest.json"))
    else:
        manifest = early_manifest(source_rows())
        if "--manifest-only" not in sys.argv:
            blender_build(manifest)
