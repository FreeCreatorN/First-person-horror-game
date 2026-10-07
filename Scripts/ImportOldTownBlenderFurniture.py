"""Import this round's Blender FBX files without editing shared materials."""
import json
import itertools
import hashlib
import math
from pathlib import Path
import unreal
from OldTownHumanScalePlan import PLACEMENT, target_parts

ROOT = "/Game/Yastar/Meshes"
TAG = "OldTownBlenderFurniture_20261002"
HUMAN_NAME = "SM_OTS_HumanReference_180x50"
LAST_PLACEMENT_DIAGNOSTICS = []


def _manifest_path(path=None):
    if path is None:
        return Path(unreal.Paths.project_dir()) / "SourceArt/OldTownModular_20261002/ImportManifest.json"
    path = Path(path)
    return path if path.is_absolute() else Path(unreal.Paths.project_dir()) / path


def _new_materials(specs):
    folder = ROOT + "/hOUSE/Materials"
    unreal.EditorAssetLibrary.make_directory(folder)
    result = {}
    for key, spec in specs.items():
        name = "M_OTS_Blender_" + key
        path = folder + "/" + name
        material = unreal.load_asset(path)
        if material is None:
            material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
            color = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -300, 0)
            color.set_editor_property("constant", unreal.LinearColor(*spec["color"], 1.0))
            unreal.MaterialEditingLibrary.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
            for index, (property_name, property_enum) in enumerate((("roughness", unreal.MaterialProperty.MP_ROUGHNESS), ("metallic", unreal.MaterialProperty.MP_METALLIC))):
                node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 150 + index * 100)
                node.set_editor_property("r", float(spec.get(property_name, 0.0)))
                unreal.MaterialEditingLibrary.connect_material_property(node, "", property_enum)
            unreal.MaterialEditingLibrary.recompile_material(material)
            unreal.EditorAssetLibrary.save_loaded_asset(material, False)
        result[key] = material
    return result


def _infer_axes(entries, assets):
    candidates = []
    for order in ((0, 1, 2), (1, 0, 2)):
        for sx, sy in itertools.product((-1., 1.), repeat=2):
            signs = (sx, sy, 1.)
            error = 0.0
            for entry in entries:
                b = assets[entry["name"]].get_bounds()
                actual = [[float(b.origin.x-b.box_extent.x), float(b.origin.y-b.box_extent.y), float(b.origin.z-b.box_extent.z)],
                          [float(b.origin.x+b.box_extent.x), float(b.origin.y+b.box_extent.y), float(b.origin.z+b.box_extent.z)]]
                source = entry["bounds_cm"]
                expected = [[min(signs[i]*source[0][order[i]], signs[i]*source[1][order[i]]) for i in range(3)],
                            [max(signs[i]*source[0][order[i]], signs[i]*source[1][order[i]]) for i in range(3)]]
                error += sum(abs(actual[j][i]-expected[j][i]) for j in (0,1) for i in range(3))
            candidates.append((error, order, signs))
    error, order, signs = min(candidates)
    assert error < 6.0, "FBX pivots/axes differ from authored objects: " + str(candidates)
    return {"order": order, "signs": signs, "bounds_error_cm": error}


def _ue_offset(entry, axes):
    offset = entry.get("offset_cm", [0.,0.,0.])
    return [axes["signs"][i] * offset[axes["order"][i]] for i in range(3)]


def import_furniture(manifest_path=None, force_reimport=None):
    """An explicit manifest reimports this round's owned meshes at scale 1."""
    assert unreal.EditorAssetLibrary.does_directory_exist(ROOT), "Existing Meshes directory missing"
    # UE 5.7's Interchange completion path can access Slate in a commandlet.
    # Use the legacy FBX importer matching the FbxImportUI options below.
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "Interchange.FeatureFlags.Import.FBX 0")
    reimport = manifest_path is not None if force_reimport is None else bool(force_reimport)
    manifest_path = _manifest_path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["assets"]
    materials = _new_materials(manifest["materials"])
    assets = {}
    report = []
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    targets = {part["name"]: part["target_dimensions_cm"] for part in target_parts()}
    for entry in entries:
        destination = entry["destination"]
        assert destination.startswith(ROOT + "/"), destination
        name = entry["name"]
        assert name.startswith("SM_OTS_Blender_") or name == HUMAN_NAME, "Refusing an unrelated mesh: " + name
        if reimport and name in targets:
            assert all(abs(a - b) < 0.2 for a, b in zip(entry["dimensions_cm"], targets[name])), (name, entry["dimensions_cm"], targets[name])
        if name == HUMAN_NAME:
            assert abs(entry["dimensions_cm"][0] - 50.0) < 0.2 and abs(entry["dimensions_cm"][2] - 180.0) < 0.2, "Human reference must be 180 cm tall and 50 cm wide"
        asset_path = destination + "/" + name
        mesh = unreal.load_asset(asset_path)
        if mesh is None or reimport:
            assert mesh is None or isinstance(mesh, unreal.StaticMesh), "Existing destination is not a StaticMesh"
            if mesh is not None:
                # FbxFactory delegates existing meshes to its reimport handler,
                # which reads stored import data before this task's new UI.
                existing_data = mesh.get_editor_property("asset_import_data")
                existing_data.set_editor_property("convert_scene", True)
                existing_data.set_editor_property("convert_scene_unit", True)
                existing_data.set_editor_property("import_uniform_scale", 1.0)
            options = unreal.FbxImportUI()
            options.set_editor_property("import_mesh", True)
            options.set_editor_property("import_as_skeletal", False)
            options.set_editor_property("import_animations", False)
            options.set_editor_property("import_materials", False)
            options.set_editor_property("import_textures", False)
            options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
            data = options.get_editor_property("static_mesh_import_data")
            data.set_editor_property("combine_meshes", True)
            data.set_editor_property("auto_generate_collision", False)
            data.set_editor_property("generate_lightmap_u_vs", True)
            data.set_editor_property("convert_scene", True)
            data.set_editor_property("convert_scene_unit", True)
            data.set_editor_property("import_uniform_scale", 1.0)
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(manifest_path.parent / entry["file"]))
            task.set_editor_property("destination_path", destination)
            task.set_editor_property("destination_name", name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", reimport)
            task.set_editor_property("save", False)
            task.set_editor_property("options", options)
            task.set_editor_property("factory", unreal.FbxFactory())
            tools.import_asset_tasks([task])
            mesh = unreal.load_asset(asset_path)
        assert isinstance(mesh, unreal.StaticMesh), "FBX import failed: " + asset_path
        bounds = mesh.get_bounds()
        actual = [float(bounds.box_extent.x) * 2, float(bounds.box_extent.y) * 2, float(bounds.box_extent.z) * 2]
        expected = entry["dimensions_cm"]
        assert sorted(round(v, 1) for v in actual) == sorted(round(v, 1) for v in expected), (name, actual, expected)
        # Reuse original PBR materials by slot name. Only this NEW mesh is edited.
        mapping = {"Wood": "M_P2_Wood", "Metal": "M_P2_OldMetal", "Cloth": "M_P2_Cloth", "Fabric": "M_P2_Cloth"}
        material_root = "/Game/Yastar/OldTownSchoolStreet/Props/Detailed/Materials/"
        for i, slot in enumerate(mesh.get_editor_property("static_materials")):
            slot_name = str(slot.get_editor_property("material_slot_name"))
            material = materials.get("ScaleReferenceBlue") if name == HUMAN_NAME else next((materials[key] for key in sorted(materials, key=len, reverse=True) if key.lower() in slot_name.lower()), None)
            assert name != HUMAN_NAME or material is not None, "ScaleReferenceBlue material missing"
            if material is None:
                material_name = next((value for key, value in mapping.items() if key.lower() in slot_name.lower()), "M_P2_Wood")
                material = unreal.load_asset(material_root + material_name)
            assert material, slot_name
            mesh.set_material(i, material)
        # These are decorative movable furnishing pieces; never make a convex
        # collider across a bed, chair legs or open wardrobe.
        source_hash = hashlib.sha256((manifest_path.parent / entry["file"]).read_bytes()).hexdigest()
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, "OldTownFurnitureSourceSHA256", source_hash)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, "OldTownFurnitureManifest", str(manifest_path))
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False), "Unable to save imported mesh: " + asset_path
        assets[name] = mesh
        report.append({"asset": asset_path, "dimensions_cm": actual, "source": entry["file"],
                       "source_sha256": source_hash, "reimport_requested": reimport,
                       "import_uniform_scale": 1.0, "reference_only": name == HUMAN_NAME})
    axes = _infer_axes(entries, assets)
    (manifest_path.parent / "UnrealAxisVerification.json").write_text(json.dumps(axes, indent=2), encoding="utf-8")
    return assets, report


def place_furniture(actor_subsystem, assets, building_report, manifest_path=None):
    for actor in list(actor_subsystem.get_all_level_actors()):
        if TAG in [str(t) for t in actor.tags]:
            actor_subsystem.destroy_actor(actor)
    manifest_path = _manifest_path(manifest_path)
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["assets"]
    axes = json.loads((manifest_path.parent / "UnrealAxisVerification.json").read_text(encoding="utf-8"))
    groups = {}
    for entry in entries:
        group = entry.get("group") or next((word for word in ("Bed", "Wardrobe", "Table", "Chair") if word.lower() in entry["name"].lower()), None)
        if group and group != "Reference":
            groups.setdefault(group, []).append(entry)
    placed = []
    def rect_overlap(a, b, margin=0.0):
        return all(min(a[1][i], b[1][i]) + margin > max(a[0][i], b[0][i]) for i in (0, 1))
    def bounds_for(group):
        low, high = [float("inf")] * 3, [-float("inf")] * 3
        for entry in groups[group]:
            bounds = assets[entry["name"]].get_bounds()
            offset = _ue_offset(entry, axes)
            origin = [bounds.origin.x, bounds.origin.y, bounds.origin.z]
            extent = [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z]
            for i in range(3):
                low[i] = min(low[i], float(origin[i] - extent[i]) + offset[i])
                high[i] = max(high[i], float(origin[i] + extent[i]) + offset[i])
        return low, high
    for building in building_report["buildings"]:
        school = building["label"].startswith("Blockout_School_")
        street = building["label"].startswith("BLK_")
        if not school and not street:
            continue
        occupied = {}
        schedules = [(0, "TableChair")]
        if street and len(building["floor_z"]) > 1:
            schedules += [(1, "Bed"), (1, "Wardrobe")]
        for floor_index, group in schedules:
            members = [("Table", [0.,0.], 0.), ("Chair", [0.,81.], 180.)] if group == "TableChair" else [(group, [0.,0.], 0.)]
            if any(member[0] not in groups for member in members):
                continue
            boxes = []
            for member, shift, yaw in members:
                lo, hi = bounds_for(member)
                if yaw == 180.:
                    lo, hi = [-hi[0],-hi[1],lo[2]],[-lo[0],-lo[1],hi[2]]
                boxes.append(([lo[0]+shift[0],lo[1]+shift[1],lo[2]], [hi[0]+shift[0],hi[1]+shift[1],hi[2]]))
            local_low = [min(box[0][i] for box in boxes) for i in range(3)]
            local_high = [max(box[1][i] for box in boxes) for i in range(3)]
            reserved_low, reserved_high = list(local_low),list(local_high)
            if group == "TableChair":
                reserved_high[1] += 85.
            elif group == "Bed":
                reserved_high[0] += 85.
            elif group == "Wardrobe":
                reserved_high[1] += 100.
            lower, upper = building["interior_min"], building["interior_max"]
            keep = building.get("stair_keepout")
            keep_rect = [keep["min"], keep["max"]] if keep else None
            route_rects = []
            if floor_index == 0:
                for route in (building["primary_entry_route"], building["ground_route"]):
                    for first, second in zip(route, route[1:]):
                        route_rects.append([[min(first[i], second[i]) - 60 for i in range(2)],
                                            [max(first[i], second[i]) + 60 for i in range(2)]])
            elif building["stairs"]:
                arrival = building["stairs"][floor_index-1]["foot_waypoints"][-1]
                center = [(lower[i]+upper[i])*.5 for i in range(2)]
                turn = [center[0],arrival[1]]
                for first, second in ((arrival,turn),(turn,center)):
                    route_rects.append([[min(first[i],second[i])-60. for i in range(2)],
                                        [max(first[i],second[i])+60. for i in range(2)]])
            x = lower[0] + 40.0 - reserved_low[0]
            y_start = lower[1] + 40.0 - reserved_low[1]
            chosen = None
            while x + reserved_high[0] <= upper[0] - 40.0 and chosen is None:
                y = y_start
                while y + reserved_high[1] <= upper[1] - 40.0:
                    rect = [[x + reserved_low[0], y + reserved_low[1]], [x + reserved_high[0], y + reserved_high[1]]]
                    obstacles = occupied.get(floor_index, []) + route_rects + ([keep_rect] if keep_rect else [])
                    if not any(rect_overlap(rect, obstacle, 15.0) for obstacle in obstacles):
                        chosen = [x, y, building["floor_z"][floor_index] - local_low[2]]
                        occupied.setdefault(floor_index, []).append(rect)
                        break
                    y += 75.0
                x += 75.0
            if chosen is None:
                LAST_PLACEMENT_DIAGNOSTICS.append({"building":building["label"],"floor":floor_index+1,"group":group,"reason":"No adult-size layout with reserved access clearance"})
                continue
            for member, shift, yaw in members:
              for entry in groups[member]:
                offset = _ue_offset(entry, axes)
                if yaw == 180.:
                    offset = [-offset[0],-offset[1],offset[2]]
                position = [chosen[i] + offset[i] + (shift[i] if i<2 else 0.) for i in range(3)]
                actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*position), unreal.Rotator(pitch=0., yaw=yaw, roll=0.), False)
                assert actor, "Unable to place " + entry["name"]
                label = "OTS_Blender_{}_F{}_{}".format(building["label"], floor_index + 1, entry["name"])
                actor.set_actor_label(label)
                actor.set_folder_path(unreal.Name("OldTownSchoolStreet/EnterableBuildings/" + building["label"] + "/Furniture"))
                actor.set_editor_property("tags", [unreal.Name(TAG)])
                component = actor.get_component_by_class(unreal.StaticMeshComponent)
                component.set_static_mesh(assets[entry["name"]])
                # Set the profile too: StaticMeshComponent's default collision
                # can otherwise restore BlockAll when its mesh finishes loading.
                component.set_collision_profile_name("NoCollision")
                placed.append({"actor": label, "asset": assets[entry["name"]].get_path_name(), "location_cm": position,
                               "building": building["label"], "floor": floor_index + 1, "group": member,
                               "yaw_degrees":yaw,"assembly_origin_cm":[chosen[i]+(shift[i] if i<2 else 0.) for i in range(3)]})
    assert any(p["group"] == "Bed" for p in placed), "No Blender bedroom assembly fits the converted rooms"
    assert any(p["group"] == "Wardrobe" for p in placed), "No Blender wardrobe assembly fits the converted rooms"
    return placed
