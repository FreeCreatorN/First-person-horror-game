"""Independent read-only persisted-map appearance/preservation acceptance.

Run only after the main realism pipeline has saved all assets and the map.
This script loads the map afresh, reads actual render LOD0 buffers/material
graphs/collision, and writes evidence. It never saves a package, edits a
material, recompiles a Blueprint, or changes an actor/component.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "Saved/CodexOutputs/OldTownRealism_20261012"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP = ROOT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
ASSET_ROOT = "/Game/CodexGenerated/OldTown/Realism_20261012/"
APPEARANCE_FIELDS = {"mesh", "materials", "local_render_bounds_cm",
    "uniform_slot_surface_translation", "expected_surface_translation_cm_to_preserve",
    "world_render_bounds_before_wpo_cm", "world_render_bounds_after_surface_translation_cm"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_of(document):
    for field in ("components", "changes", "overrides", "applied_components"):
        if isinstance(document.get(field), list):
            return document[field]
    raise ValueError("RealismApply must provide a components list")


def component_index(actors):
    return {name + "::" + component["name"]: component
            for name, state in actors.items() for component in state["components"]}


def native_index(actors):
    return {name + "::" + component["name"]: component
            for name, components in actors.items() for component in components}


def independently_expected(before, changes):
    expected = deepcopy(before)
    source, destination = component_index(before), component_index(expected)
    seen = set()
    for row in changes:
        ident = row["actor"] + "::" + row["component"]
        assert ident == row["id"] and ident not in seen, ident
        seen.add(ident)
        old = source[ident]
        assert old.get("visible") is True and old.get("hidden_in_game") is False, ident
        assert old.get("mesh") == row["source_mesh"], ident
        assert old.get("materials") == row["before_materials"], ident
        assert row["actor"] in before, ident
        assert row["target_mesh"] == row["source_mesh"] or row["target_mesh"].startswith(ASSET_ROOT), ident
        assert row["after_materials"] and all(m and m.startswith(ASSET_ROOT + "Materials/") for m in row["after_materials"]), ident
        assert len(row["expected_offset_cm"]) == 3 and all(math.isfinite(v) for v in row["expected_offset_cm"])
        destination[ident]["mesh"] = row["target_mesh"]
        destination[ident]["materials"] = row["after_materials"]
    return expected


def without_appearance(row):
    return {k: v for k, v in row.items() if k not in APPEARANCE_FIELDS}


def collision_signature(row):
    # Export filenames and BodySetup object identities necessarily differ on
    # a clone. Compare full native AggGeom parameters and collision properties.
    return {k: v for k, v in row.items() if k not in ("body_setup","native_body_setup_export")}


def near(a, b, tolerance):
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(near(x, y, tolerance) for x, y in zip(a, b))
    return abs(float(a) - float(b)) <= tolerance


def physical_uv_errors(geometry, dimensions_cm, tolerance=.0005):
    """Verify actual UV buffers against physical geometry, not manifest claims.

    The exporter uses physical centimetres/100 projected to one of XY/XZ/YZ.
    Compare all three triangle edges to allow translated UV islands while
    checking actual physical scale independently of manifest claims.
    """
    bad, checked, maximum_error = [], 0, 0.
    for section in geometry["sections"]:
        points, uv, indices = section["vertices_cm"], section["uv0"], section["triangle_indices"]
        for start in range(0, len(indices), 3):
            ids = indices[start:start + 3]
            errors = []
            for axes in ((0, 1), (0, 2), (1, 2)):
                # Unreal's FBX importer maps V to 1-V; the measured geometry
                # handedness correction changes positions, not this UV convention.
                errors.append(max(max(
                    abs((uv[i][0]-uv[j][0])-(points[i][axes[0]]-points[j][axes[0]])*dimensions_cm[axes[0]]/10000),
                    abs((uv[i][1]-uv[j][1])+(points[i][axes[1]]-points[j][axes[1]])*dimensions_cm[axes[1]]/10000)
                ) for i,j in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0]))))
            error = min(errors)
            maximum_error = max(maximum_error, error)
            checked += 1
            if error > tolerance and len(bad) < 12:
                bad.append(dict(section=section["section_index"], triangle=start // 3, error_uv=error))
    return dict(passed=not bad, checked_triangles=checked, maximum_error_uv=maximum_error,
                tolerance_uv=tolerance, samples=bad, mapping="Actual triangle UV edge differences equal physical cm/100; one UV unit per metre; island translations allowed")


def finite_vector(v, require_nonzero=False):
    return len(v) >= 2 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v) and (not require_nonzero or sum(x * x for x in v) > .5)


def normal_projection_contract(mode, scanned, tangent, normal_input):
    """Strictly accept the actual graph connection in its declared space."""
    if mode not in ("UV", "World") or not normal_input.get("node"):
        return False
    if scanned:
        return tangent == (mode == "UV")
    cls = normal_input.get("class_path", "")
    values = normal_input.get("properties", {}).get("constant", [])
    flat = (cls == "/Script/Engine.MaterialExpressionConstant3Vector"
        and isinstance(values, (list, tuple)) and len(values) >= 3
        and all(isinstance(v, (int, float)) and math.isfinite(v) for v in values[:3])
        and all(abs(a - b) <= .00000001 for a, b in zip(values[:3], [0., 0., 1.])))
    if mode == "UV":
        return tangent is True and flat
    return ((tangent is True and flat) or
        (tangent is False and cls == "/Script/Engine.MaterialExpressionVertexNormalWS"))


def main():
    import unreal
    sys.path.insert(0, str(ROOT / "Scripts"))
    import InspectOldTownRealismInput as native
    import OldTownRealismMaterials as pbr
    from PolishOldTownHotel import actor_state

    result = dict(schema="OldTownRealismAppearanceAuditV1", passed=False,
        target_level=TARGET, checks=[], errors=[], statistics={}, meshes={},
        materials={}, grounding=[], shader_compile_logs=[],
        read_only_scope="Fresh persisted map, native render LOD0 buffers, native material graph and source BodySetup; no save/edit/recompile calls")

    def check(name, passed, **details):
        item = dict(name=name, passed=bool(passed), **details)
        result["checks"].append(item)
        if not passed:
            result["errors"].append(item)
        return bool(passed)

    def checkpoint():
        write(WORK / "AppearanceAudit.json", result)

    inp = read(WORK / "RealismInput.json")
    street_input=read(WORK/'RealismStreetInput.json')
    assert street_input['passed'] and street_input['input_inventory_sha256']==sha(WORK/'RealismInput.json')
    inp=deepcopy(inp)
    inp['component_records'].update(street_input['component_records'])
    inp['meshes'].update(street_input['meshes'])
    inp['source_asset_file_sha256'].update(street_input['source_asset_file_sha256'])
    inp['protected_map_sha256']=street_input['protected_map_sha256']
    build = read(WORK / "BuildReport.json")
    apply = read(WORK / "RealismApply.json")
    expected_file = read(WORK / "ExpectedSnapshot.json")
    after_file = read(WORK / "AfterSnapshot.json")
    before_snapshot = read(inp["baseline_snapshot_file"])
    before = before_snapshot["actors"]
    evidence_inputs = [WORK / name for name in ("RealismInput.json", "BuildReport.json",
        "RealismApply.json", "ExpectedSnapshot.json", "AfterSnapshot.json",
        "FurnitureAssetBuild.json", "ArchitectureAssetBuild.json", "SanitaryAssetBuild.json", "MaterialBuild.json")]
    input_fingerprints = {str(path): sha(path) for path in evidence_inputs}
    input_fingerprints[str(WORK/'RealismStreetInput.json')]=sha(WORK/'RealismStreetInput.json')
    input_fingerprints[str(WORK/'StreetAssetBuild.json')]=sha(WORK/'StreetAssetBuild.json')
    repairs=read(WORK/'AdditionalSurfaceRepairs.json')
    input_fingerprints[str(WORK/'AdditionalSurfaceRepairs.json')]=sha(WORK/'AdditionalSurfaceRepairs.json')
    material_roles=read(WORK/'MaterialRoleRepairs.json')
    input_fingerprints[str(WORK/'MaterialRoleRepairs.json')]=sha(WORK/'MaterialRoleRepairs.json')
    followup=read(WORK/'FollowupSurfaceRepairs.json')
    input_fingerprints[str(WORK/'FollowupSurfaceRepairs.json')]=sha(WORK/'FollowupSurfaceRepairs.json')
    input_fingerprints[str(WORK/'ModelClosureImportRepairs.json')]=sha(WORK/'ModelClosureImportRepairs.json')
    generated_fingerprints = dict(build["new_asset_sha256"])
    source_fbx_fingerprints = {str(path): sha(path) for path in
        sorted((ROOT / "SourceArt/OldTownRealism_20261012").rglob("*.fbx"))}
    result.update(source="fresh_persisted_map_load", source_map_sha256=inp["source_map_sha256"],
        input_sha256=input_fingerprints, new_asset_sha256=generated_fingerprints,
        source_fbx_sha256=source_fbx_fingerprints)
    changes = rows_of(apply)
    independently_allowed = independently_expected(before, changes)
    allowed = {r["id"]: r for r in changes}
    # The pure validator replays the persisted 51-contact, wall/floor-routing,
    # and one-contact stages against all 8684 rows and all 8014 Actor states.
    # The later native checks still read actual slots, graph, WPO and collision.
    from FinalizeOldTownRealism import verify_appearance_stage_chain, native_closed_solid
    try:
        _, _, _, followup_rows, followup_proof, closure_proof = verify_appearance_stage_chain(
            build, inp, apply, read(WORK/'Applied.json'), build['map_sha256'])
        check('full_8684_appearance_stage_chain_replayed', True,
              appearance_components_replayed=followup_proof['appearance_components_replayed'],
              actor_snapshots_replayed=followup_proof['actor_snapshots_replayed'])
        check('strict_1_followup_additive_render_contact_repair', True,
              component_count=1, delta_cm=followup_proof['delta_cm'])
        check('strict_22_model_closure_import_stage', True, changed_models=closure_proof['changed_model_count'])
        historical_stage_files=dict(followup_proof['prior_and_diagnostic_file_sha256'])
        historical_stage_files.update(closure_proof['prior_and_diagnostic_file_sha256'])
    except Exception as error:
        followup_rows={r['id']:r for r in followup.get('components',[])}
        historical_stage_files={}
        check('full_8684_appearance_stage_chain_replayed', False, error=str(error))
        check('strict_1_followup_additive_render_contact_repair', False, error=str(error))
        check('strict_22_model_closure_import_stage', False, error=str(error))
    routed={r['id']:r for r in material_roles['components']}
    walls={r['id'] for r in changes if 'ConcreteWall' in r['role']}
    floors={r['id'] for r in changes if 'Concrete' in r['role']}
    check('wall_and_floor_concrete_materials_separated',material_roles['passed'] and material_roles['map_sha256']==build['map_sha256'] and
        len(routed)==1519 and set(routed)==walls and len(floors)==585 and set(material_roles['retained_floor_component_ids'])==floors and not walls&floors and
        all(r['after_materials']==allowed[i]['after_materials'] and r['target_roles']==allowed[i]['role'] for i,r in routed.items()))
    hotel = set(inp["hotel_actor_labels"])
    check("accepted_source_input", inp.get("passed") is True and inp["source_map_sha256"] == "ade3fcc6a6482713618e3fadbd4534771549e773097fd2b9d34886318451e1f6")
    check("expected_snapshot_only_changes_listed_visible_meshes_materials", expected_file["actors"] == independently_allowed)
    check("saved_after_snapshot_exactly_expected", after_file["actors"] == independently_allowed)
    check("input_actor_counts", len(before) == 8014 and len(hotel) == 2975 and len(set(before) - hotel) == 5039)
    initial_digest = sha(MAP)
    check("saved_map_matches_build", initial_digest == build["map_sha256"])
    check("fresh_persisted_map_load", unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET))
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by = {a.get_actor_label(): a for a in actors}
    actual = {name: actor_state(actor) for name, actor in by.items()}
    check("all_8014_actor_identities_preserved", len(actors) == len(by) == 8014 and set(by) == set(before))
    differences = [n for n in before if actual.get(n) != independently_allowed[n]]
    check("all_actor_component_parent_pose_collision_and_allowed_appearance_exact", not differences,
          differences=differences[:20], checked_actors=len(before))
    outside = [n for n in set(before) - hotel if actual.get(n) != independently_allowed[n]]
    check("outside_hotel_5039_actors_exact", not outside and len(set(before) - hotel) == 5039, differences=outside[:20],scope='Only declared street mesh/material replacements; other fields exact')
    old_flat, now_flat = component_index(before), component_index(actual)
    sanitary_hidden = [ident for ident, row in old_flat.items() if ident.split("::")[0] in hotel and
                       "_Collision" in ident.split("::")[0] and row.get("visible") is False]
    opening_hidden = [ident for ident, row in old_flat.items() if ident.split("::")[0] in hotel and
                      row.get("visible") is False and row["name"] in
                      ("LeafCollision", "LeftLeafCollision", "RightLeafCollision", "LeftPaneCollision", "RightPaneCollision")]
    opening_actors = {ident.split("::")[0] for ident in opening_hidden}
    check("all_87_hidden_sanitary_colliders_exact", len(sanitary_hidden) == 87 and all(now_flat.get(i) == old_flat[i] for i in sanitary_hidden))
    check("all_169_opening_actors_276_hidden_colliders_exact", len(opening_actors) == 169 and len(opening_hidden) == 276 and
          all(now_flat.get(i) == old_flat[i] for i in opening_hidden), actor_count=len(opening_actors), component_count=len(opening_hidden))
    mainhome = before_snapshot["main_home"]["actor"]
    check("mainhome_structure_and_components_exact", actual.get(mainhome) == before[mainhome] and
          sum("mesh" in c for c in actual[mainhome]["components"]) == before_snapshot["main_home"]["mesh_components"])
    check("mainhome_snapshot_summary_exact", after_file.get("main_home") == before_snapshot.get("main_home"))
    hash_groups = {"original_400": inp["original_400_shared_asset_sha256"],
                   "recursive_native_source_assets": inp["source_asset_file_sha256"],
                   "protected_latest_user_saved_maps": inp["protected_map_sha256"],
                   "input_evidence": inp.get("source_input_sha256", {})}
    for name, hashes in hash_groups.items():
        changed = [p for p, digest in hashes.items() if not Path(p).is_file() or sha(p) != digest]
        check("unchanged_hashes:" + name, not changed and (name != "original_400" or len(hashes) == 400), checked=len(hashes), changed=changed[:20])
    check("all_generated_package_files_match_build_before_audit", bool(generated_fingerprints) and
        all(Path(p).is_file() and sha(p) == h for p, h in generated_fingerprints.items()))
    checkpoint()

    # Reuse tested native readers, with fresh caches and separate evidence paths.
    native.WORK = WORK / "AppearanceNative"
    native.MATERIAL_CACHE.clear()
    native.MESH_CACHE.clear()
    native.SOURCE_FILES.clear()
    native.LIMITATIONS.clear()
    current_components = {}
    for index, name in enumerate(sorted(inp['component_records'])):
        current_components[name] = [native.component_record(c) for c in by[name].get_components_by_class(unreal.SceneComponent)]
        if index % 400 == 0:
            unreal.log("APPEARANCE_NATIVE_COMPONENTS " + str(index) + "/" + str(len(hotel)))
    input_components, current_flat = native_index(inp["component_records"]), native_index(current_components)
    check("native_component_identities_exact", set(input_components) == set(current_flat))
    altered_native = []
    for ident, row in input_components.items():
        now = current_flat.get(ident)
        valid = without_appearance(row) == without_appearance(now) if ident in allowed and now else row == now
        if not valid:
            altered_native.append(ident)
    check("native_parent_relative_world_pose_bodyinstance_collisionflags_exact", not altered_native,
          checked_components=len(input_components), differences=altered_native[:20])
    nonzero_old = {ident: row for ident, row in input_components.items() if any(
        abs(v) > 1.e-8 for m in row.get("materials", []) for v in m.get("effective_surface_translation_cm", [0, 0, 0]))}
    hotel_wpo={i:r for i,r in nonzero_old.items() if i.split('::')[0] in hotel}
    check("all_1061_original_wpo_components_identified", len(hotel_wpo) == 1061, count=len(hotel_wpo),whole_map_count=len(nonzero_old))
    repair_rows={r['id']:r for r in repairs['components']}
    declared_deltas={f'OTS_HotelV4_Vestibule_Front_{i:02d}::StaticMeshComponent0':d for i,d in enumerate(([0,.06,0],[0,-.06,0],[0,0,-.06]))}
    heads={ident for ident,r in allowed.items() if r['category']=='Furniture' and '/SM_OTS_Real_BedHead_' in r['target_mesh']}
    declared_deltas.update({ident:[.06,0,0] for ident in heads})
    valid_repairs=repairs['passed'] and repairs['map_sha256']==build['map_sha256'] and len(heads)==48 and len(repair_rows)==51 and set(repair_rows)==set(declared_deltas)
    for ident,r in repair_rows.items():
        source=input_components[ident]['expected_surface_translation_cm_to_preserve']
        valid_repairs=valid_repairs and near(r['delta_cm'],declared_deltas[ident],.000002) and near(r['source_offset_cm'],source,.000002) and near(r['expected_offset_cm'],[v+d for v,d in zip(source,declared_deltas[ident])],.000002)
    check('strict_51_additive_render_contact_repairs',valid_repairs)
    effective_wpo={ident for ident,r in current_flat.items() if any(abs(v)>1.e-8 for m in r.get('materials',[]) for v in m.get('effective_surface_translation_cm',[0,0,0]))}
    check('all_3297_current_wpo_components_identified',len(effective_wpo)==3297 and effective_wpo==set(nonzero_old)|heads,count=len(effective_wpo))
    wpo_failures = []
    for ident, old in input_components.items():
        if not old.get("materials"):
            continue
        previous = old.get("expected_surface_translation_cm_to_preserve")
        now = current_flat[ident]
        if ident in allowed:
            requested = allowed[ident]["expected_offset_cm"]
            preserved=[v+d for v,d in zip(previous,declared_deltas.get(ident,[0,0,0]))] if previous is not None else None
            if preserved is not None and ident in followup_rows:
                preserved=[v+d for v,d in zip(preserved,followup_rows[ident]['delta_cm'])]
            valid = preserved is not None and near(requested, preserved, .000002) and all(
                m.get("has_surface_translation_parameter") and near(m.get("effective_surface_translation_cm", [0, 0, 0]), requested, .000002)
                for m in now["materials"])
        else:
            valid = old["materials"] == now["materials"]
        if not valid:
            wpo_failures.append(ident)
    check("effective_wpo_preserved_on_every_old_component_and_new_slot", not wpo_failures, differences=wpo_failures[:20])
    for row in changes:
        component = current_flat[row["id"]]
        check("component_manifest_actual:" + row["id"], component["mesh"] == row["target_mesh"] and
              [m["asset"] for m in component["materials"]] == row["after_materials"])

    # Blueprint assets remain unchanged, including SCS templates and graph links.
    current_blueprints = {}
    for package, old in inp["blueprints"].items():
        fresh = native.blueprint_record(package, [by[n] for n in old["instances"]])
        current_blueprints[package] = fresh
        fields = ("generated_class", "blueprint_properties", "parent_class_native_text",
                  "variable_definitions", "all_defined_variable_names", "cdo_variable_values",
                  "graph_pages", "graph_pages_native_text", "linked_exec_pin_count_native_text", "component_templates")
        changed = [name for name in fields if fresh.get(name) != old.get(name)]
        check("blueprint_scs_cdo_variables_graph_exact:" + package, not changed and fresh["sha256"] == old["sha256"], differences=changed)
        for name, instance in old["instances"].items():
            now = fresh["instances"][name]
            check("blueprint_instance_variables_exact:" + name,
                  instance["variable_values"] == now["variable_values"] and instance["object_path"] == now["object_path"])
    checkpoint()

    asset_documents = {category: read(WORK / filename) for category, filename in
        (("Furniture", "FurnitureAssetBuild.json"), ("Architecture", "ArchitectureAssetBuild.json"), ("Sanitary", "SanitaryAssetBuild.json"),("Street","StreetAssetBuild.json"))}
    imported = {}
    closed_solids = {}
    for category, doc in asset_documents.items():
        check("asset_build_declares_success:" + category, doc.get("passed") is True)
        for row in doc["assets"]:
            imported[row["asset"]] = row
            check("saved_imported_asset_hash:" + row["asset"], Path(row["file"]).is_file() and sha(row["file"]) == row["sha256"])
    furniture = read(ROOT / "SourceArt/OldTownRealism_20261012/Furniture/ModelDataManifest.json")
    variants = {r["key"]: r for r in furniture["variants"]}
    check("all_33_furniture_variants_680_actors_registered", len(variants) == 33 and len(furniture["actors"]) == 680 and
          len(asset_documents["Furniture"]["assets"]) == 33)
    for path, row in imported.items():
        try:
            mesh = unreal.load_asset(path)
            record = native.mesh_record(mesh)
            geometry = read(record["geometry_file"])
            result["meshes"][path] = {k: v for k, v in record.items() if k != "_positions"}
            try:
                solid = native_closed_solid(geometry)
                closed_solids[path] = solid
                check("actual_closed_native_solid:" + path, True, **{k:v for k,v in solid.items() if k!='passed'})
            except Exception as error:
                check("actual_closed_native_solid:" + path, False, error=str(error))
            source_path = row.get("source_asset", row.get("source_mesh", "/Engine/BasicShapes/Cube.Cube"))
            source = unreal.load_asset(source_path)
            source_signature = native.collision_record(source)
            check("clone_bodysetup_exact:" + path, collision_signature(record["collision_signature"]) == collision_signature(source_signature))
            check("actual_render_triangles_exceed_old_cube:" + path, record["triangle_count"] > 12 and record["uv_channel_count"] >= 1,
                  triangles=record["triangle_count"], uv_channels=record["uv_channel_count"])
            bad_sections = []
            for section in geometry["sections"]:
                n = len(section["vertices_cm"])
                valid = (len(section["normals"]) == len(section["tangents"]) == len(section["uv0"]) == n and
                    all(finite_vector(v, True) for v in section["normals"]) and
                    all(finite_vector(t["tangent_x"], True) for t in section["tangents"]) and
                    all(finite_vector(v) for v in section["uv0"]) and section["degenerate_uv0_triangles"] == 0)
                if not valid:
                    bad_sections.append(section["section_index"])
                check("material_partition_reference:" + path + ":" + str(section["section_index"]),
                    0 <= section["material_slot_index"] < len(record["static_material_slots"]) and
                    bool(section["default_material"]) and unreal.load_asset(section["default_material"]) is not None)
            check("actual_normals_tangents_uv0_valid:" + path, not bad_sections, sections=bad_sections)
            roles = row["material_roles"]
            actual_roles = []
            for slot in record["static_material_slots"]:
                material = native.MATERIAL_CACHE[slot["material"]]
                match = re.search(r"/M_R_(.+)_(UV|World)\.M_R_", material["base_material"])
                actual_roles.append(match.group(1) if match else None)
            check("actual_imported_material_role_slots:" + path, actual_roles == roles, actual=actual_roles, expected=roles)
            if row.get("category") == "Furniture" or path in {r["asset"] for r in asset_documents["Furniture"]["assets"]}:
                entry = variants[row["key"]]
                check("furniture_actual_local_bounds_003cm:" + path, near(record["bounds_cm"], entry["local_bounds_cm"], .03),
                      actual=record["bounds_cm"], expected=entry["local_bounds_cm"])
                uv_audit = physical_uv_errors(geometry, entry["world_dimensions_cm"])
                check("furniture_actual_physical_uv_cm:" + path, uv_audit["passed"], **{k: v for k, v in uv_audit.items() if k != "passed"})
                check("fbx_source_hash:" + path, sha(row["fbx_source"]) == row["fbx_sha256"] == entry["source_file_sha256"])
        except Exception:
            check("actual_mesh_native_read:" + path, False, traceback=traceback.format_exc())
    check("all_143_actual_native_meshes_closed", len(imported) == len(closed_solids) == 143,
          inspected=len(imported), closed=len(closed_solids))
    result["native_closed_solids"] = closed_solids
    source_boxes = {r["actor"]: r for r in inp["layout_manifest"]["boxes"]}
    floors = inp["layout_manifest"]["floor_z_cm"]
    for row in furniture["actors"]:
        if row["kind"] not in ("BedBase", "SeatBase"):
            continue
        ident = row["actor_label"] + "::StaticMeshComponent0"
        now = current_flat[ident]
        floor = floors[source_boxes[row["actor_label"]]["floor"]]
        old_offset = input_components[ident]["expected_surface_translation_cm_to_preserve"]
        actual_low = now["world_render_bounds_after_surface_translation_cm"][0][2]
        expected_low = floor + old_offset[2]
        passed = abs(actual_low - expected_low) <= .2
        witness = dict(actor=row["actor_label"], kind=row["kind"], floor_z_cm=floor,
                       expected_wpo_cm=old_offset, actual_low_z_cm=actual_low,
                       expected_low_z_cm=expected_low, gap_cm=actual_low - expected_low, passed=passed)
        result["grounding"].append(witness)
        check("actual_grounded_feet:" + row["actor_label"], passed, gap_cm=witness["gap_cm"])
    check("all_bed_and_chair_feet_grounded", len(result["grounding"]) == 104 and all(r["passed"] for r in result["grounding"]), count=len(result["grounding"]))
    checkpoint()

    material_build = read(WORK / "MaterialBuild.json")
    for row in material_build["assets"]:
        check("saved_pbr_asset_hash:" + row["asset"], Path(row["file"]).is_file() and sha(row["file"]) == row["sha256"])
    masters = {r["asset"]: r for r in material_build["assets"] if r.get("kind") == "master"}
    texture_specs = {r["asset"]: r for r in material_build["assets"] if r.get("kind") == "texture"}
    active = {m["asset"] for row in current_flat.values() if row.get("mesh") and
              row.get("primitive_properties", {}).get("visible", False) for m in row.get("materials", [])}
    bases = {native.MATERIAL_CACHE[p]["base_material"] for p in active if p and p.startswith(ASSET_ROOT + "Materials/")}
    for path in sorted(bases):
        record = native.material_record(unreal.load_asset(path))
        base = record["chain"][-1]
        material = unreal.load_asset(path)
        source = masters.get(path)
        check("active_pbr_master_registered:" + path, source is not None)
        if source is None:
            continue
        role, mode = source["role"], source["projection"]
        check("active_pbr_role_known:" + path, role in pbr.SPEC)
        connected = base["property_inputs"]
        required = ("MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_METALLIC", "MP_WORLD_POSITION_OFFSET")
        check("real_pbr_output_connections:" + path, all(connected.get(k, {}).get("node") for k in required))
        tangent = bool(material.get_editor_property("tangent_space_normal"))
        graph = base["connected_graph_nodes"]
        normal_path = connected.get("MP_NORMAL", {}).get("node")
        normal_input = dict(node=normal_path, **graph.get(normal_path, {}))
        scanned = pbr.SPEC[role][0] is not None
        check("normal_projection_space_property:" + path,
              normal_projection_contract(mode, scanned, tangent, normal_input),
              tangent_space_normal=tangent, projection=mode, scanned=scanned, actual_normal_input=normal_input)
        missing = [p for p, node in graph.items() if "TextureSample" in node["class_path"] or "TextureObject" in node["class_path"]
                   if not node["properties"].get("texture")]
        check("no_missing_graph_texture_objects:" + path, not missing, missing=missing)
        pending = [unreal.MaterialEditingLibrary.get_material_property_input_node(material, getattr(unreal.MaterialProperty, prop)) for prop in required]
        seen, coordinates = set(), []
        while pending:
            expression = pending.pop()
            if expression is None or expression.get_path_name() in seen:
                continue
            seen.add(expression.get_path_name())
            if isinstance(expression, unreal.MaterialExpressionTextureCoordinate):
                coordinates.append(native.props(expression, ["u_tiling", "v_tiling"]))
            pending.extend(x for x in unreal.MaterialEditingLibrary.get_inputs_for_material_expression(material, expression) if x is not None)
        if mode == "UV" and pbr.SPEC[role][0] is not None:
            expected_tiling = 100. / pbr.SPEC[role][1]
            check("physical_uv_texture_scale:" + path, bool(coordinates) and all(near([c["u_tiling"], c["v_tiling"]], [expected_tiling] * 2, .00001) for c in coordinates),
                  coordinates=coordinates, tile_size_cm=pbr.SPEC[role][1])
        for texture in base["used_textures"]:
            spec = texture_specs.get(texture["asset"])
            props = texture["properties"]
            check("pbr_texture_registered_exists:" + texture["asset"], spec is not None and Path(texture["file"]).is_file())
            if spec:
                kind = spec["channel"]
                compression = str(props.get("compression_settings", ""))
                expected_compression = "NORMALMAP" if kind == "normal" else "MASKS" if kind == "rough" else "DEFAULT"
                check("pbr_texture_color_space_compression:" + texture["asset"], props.get("srgb") == (kind == "color") and expected_compression in compression.upper(),
                      channel=kind, properties=props)
        result["materials"][path] = dict(role=role, projection=mode, tangent_space_normal=tangent,
            output_connections=connected, actual_texture_coordinates=coordinates, used_textures=base["used_textures"],
            scanned=scanned, actual_normal_input=normal_input)
    missing_pbr = [row["id"] for row in changes if any(not native.MATERIAL_CACHE[m]["base_material"].startswith(ASSET_ROOT + "Materials/M_R_") for m in row["after_materials"])]
    check("no_default_gray_or_unregistered_replacement_materials", not missing_pbr and bool(bases), missing=missing_pbr)
    final_logs = material_build.get("final_compile_logs", [])
    if isinstance(final_logs, str):
        final_logs = [final_logs]
    check("completed_material_compile_logs_supplied", bool(final_logs))
    pattern = re.compile(r"(?:LogMaterial|LogShaderCompilers).*?(?:Error:|Failed to compile|error [A-Z]+\d+|Missing.*Texture)", re.I)
    for path in final_logs:
        log = Path(path)
        text = log.read_text(encoding="utf-8-sig", errors="replace") if log.is_file() else ""
        errors = [line for line in text.splitlines() if pattern.search(line)]
        result["shader_compile_logs"].append(dict(file=str(log), sha256=sha(log) if log.is_file() else None, shader_errors=errors[:30]))
        check("completed_shader_compile_log_clean:" + str(log), bool(text) and not errors, errors=errors[:20])
    # Actual live log is supplementary; the caller also verifies it after UE exits.
    for argument in unreal.SystemLibrary.get_command_line().split():
        if argument.lower().startswith("-abslog="):
            live = Path(argument.split("=", 1)[1].strip('"'))
            if live.is_file():
                errors = [line for line in live.read_text(encoding="utf-8-sig", errors="replace").splitlines() if pattern.search(line)]
                check("live_audit_shader_log_clean", not errors, file=str(live), errors=errors[:20])
    check("map_unchanged_during_read_only_audit", sha(MAP) == initial_digest)
    check("all_native_read_asset_files_unchanged_during_audit", all(Path(p).is_file() and sha(p) == digest for p, digest in native.SOURCE_FILES.items()),
          checked=len(native.SOURCE_FILES))
    for name, hashes in hash_groups.items():
        check("post_audit_hashes_unchanged:" + name, all(Path(p).is_file() and sha(p) == h for p, h in hashes.items()))
    check("audit_input_reports_unchanged", all(sha(p) == h for p, h in input_fingerprints.items()))
    check("historical_appearance_stage_files_unchanged_during_audit", bool(historical_stage_files) and
          all(Path(p).is_file() and sha(p) == h for p, h in historical_stage_files.items()))
    check("all_generated_package_files_unchanged_during_audit", all(sha(p) == h for p, h in generated_fingerprints.items()))
    check("all_source_fbx_files_unchanged_during_audit", bool(source_fbx_fingerprints) and
        all(sha(p) == h for p, h in source_fbx_fingerprints.items()))
    result["statistics"] = dict(actors=len(by), outside_hotel=len(set(before) - hotel),
        changed_components=len(changes), inspected_native_components=len(current_flat),
        original_wpo_components=len(hotel_wpo), whole_map_original_wpo_components=len(nonzero_old), imported_meshes=len(imported),
        current_whole_map_wpo_components=len(effective_wpo), additional_surface_contact_repairs=len(repair_rows),
        followup_surface_contact_repairs=len(followup_rows),
        model_closure_import_repairs=22, native_closed_meshes=len(closed_solids),
        active_pbr_masters=len(bases), grounded_furniture=len(result["grounding"]),
        hidden_sanitary_colliders=len(sanitary_hidden), hidden_opening_colliders=len(opening_hidden),
        blueprint_assets=len(current_blueprints), checked_original_files=len(inp["original_400_shared_asset_sha256"]))
    result["map_sha256"] = initial_digest
    result["persisted_map_unchanged"] = sha(MAP) == initial_digest
    result["passed"] = not result["errors"]
    write(WORK / "AppearanceSnapshot.json", dict(actors=actual, actor_count=len(actual),
        component_records=current_components, blueprints=current_blueprints,
        map_sha256=initial_digest, target_level=TARGET, source="fresh_persisted_native_read_only"))
    checkpoint()
    unreal.log("REALISM_APPEARANCE_AUDIT_" + ("PASS " if result["passed"] else "FAIL ") + json.dumps(result["statistics"]))
    assert result["passed"], "Appearance audit rejected; see AppearanceAudit.json"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write(WORK / "AppearanceAuditFailure.json", dict(passed=False, traceback=traceback.format_exc()))
        raise
