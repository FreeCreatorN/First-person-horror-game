"""Pure, read-only preservation/geometry verifier for the second realism stage.

Root creates the frozen baseline and approved plan before applying replacements.
This module reads actual fresh exports; it never launches UE or writes evidence.
The former stage, its assets and source art are immutable inputs.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import math

from AuditOldTownRealismAppearance import collision_signature
from FinalizeOldTownRealism import (native_closed_solid, native_frame_proof,
    native_physical_uv, native_binary_source_face_proof)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Saved/CodexOutputs/OldTownRealism_20261012"
WORK = ROOT / "Saved/CodexOutputs/OldTownRealismRefinement_20261013"
CANON = ROOT / "Saved/CodexOutputs/EnterableStreet_20261002"
MAP = ROOT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
ASSET_ROOT = "/Game/CodexGenerated/OldTown/RealismRefinement_20261013/"
GENERATED = ROOT / "Content/CodexGenerated/OldTown/RealismRefinement_20261013"
SOURCE_MAP_SHA = "82b8b44a08c223ca654807f85b633e0cf7e912372f82e84a3cdd8d816e873f5e"
SOURCE_POINTER_SHA = "6d18cba953f069e344ebcec7831e1bfffaf277bd382329f21f7459219efa0924"
SOURCE_REVIEW_SHA = "89e53efc15483b786b510b3c1d954b1fb577646ae7b60cdeb43ef39e58b8c298"
MAIN_SHA = "d45a87ce99e6e38dde44550eb3591994624cf6e9af684feb84523921df35a841"
BASE_SCHEMA = "OldTownRealismRefinementBaselineV1"
PLAN_SCHEMA = "OldTownRealismRefinementPlanV1"
AFTER_SCHEMA = "OldTownRealismRefinementAfterV1"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def hashes(values, label):
    require(isinstance(values, dict) and bool(values), label+" is empty.")
    for name, expected in values.items():
        require(Path(name).is_absolute() and Path(name).is_file() and sha(name) == expected,
                label+" changed or disappeared: "+name)


def component_index(actors, native=False):
    result = {}
    for name, value in actors.items():
        for component in value if native else value["components"]:
            ident = name+"::"+component["name"]
            require(ident not in result, "Duplicated Actor/component identity: "+ident)
            result[ident] = component
    return result


def reference(path):
    path = Path(path).resolve()
    return dict(file=str(path), sha256=sha(path))


def bound_document(row):
    require(Path(row["file"]).is_absolute() and sha(row["file"]) == row["sha256"],
            "Frozen or fresh export SHA differs: "+row["file"])
    return read(row["file"])


def create_baseline(map_backup_file, pointer_backup_file):
    """Return baseline data after root copies map/pointer into the new stage."""
    require(sha(MAP) == sha(map_backup_file) == SOURCE_MAP_SHA, "Starting saved map differs.")
    require(sha(pointer_backup_file) == sha(CANON/"CurrentEvidence.json") == SOURCE_POINTER_SHA,
            "Starting canonical evidence differs.")
    pointer, review = read(pointer_backup_file), read(SOURCE/"FinalReview.json")
    require(sha(SOURCE/"FinalReview.json") == SOURCE_REVIEW_SHA and review["passed"], "Source review differs.")
    for path in (map_backup_file, pointer_backup_file):
        require(Path(path).resolve().is_relative_to((WORK/"Before").resolve()), "Baseline backup escaped the new stage.")
    previous = pointer["current_asset_sha256"]
    require(len(previous) == 927 and previous == review["new_asset_sha256"], "Source 927-package set differs.")
    hashes(previous, "Previous accepted packages")
    protected = dict(review["immutable_input_sha256"])
    protected.update(review["source_art_sha256"])
    main_file = str((ROOT/"Content/Yastar/Maps/L_Main.umap").resolve())
    changes = []
    for file, digest in list(protected.items()):
        current = sha(file)
        if current != digest:
            require(file == main_file, "An immutable input other than user L_Main changed: "+file)
            changes.append(dict(file=file, accepted_sha256=digest, input_sha256=current))
            protected[file] = current
    snapshots = dict(actors=reference(SOURCE/"AfterSnapshot.json"),
        native=reference(SOURCE/"AppearanceSnapshot.json"),
        appearance=reference(SOURCE/"AppearanceAudit.json"))
    source_reports = {str((SOURCE/name).resolve()): pointer["current_report_sha256"][name]
                      for name in pointer["current_reports"]}
    hashes(source_reports, "Previous accepted reports")
    return dict(schema=BASE_SCHEMA, source_map_sha256=SOURCE_MAP_SHA,
        source_current_evidence=reference(pointer_backup_file), source_map_copy=reference(map_backup_file),
        source_final_review=reference(SOURCE/"FinalReview.json"), source_snapshot=snapshots,
        source_report_sha256=source_reports, previous_asset_sha256=previous,
        protected_file_sha256=protected, preexisting_protected_map_changes=changes,
        actor_count=8014, scene_component_count=13920)


def verify_baseline(baseline):
    require(baseline["schema"] == BASE_SCHEMA and baseline["source_map_sha256"] == SOURCE_MAP_SHA,
            "Wrong refinement baseline schema/map.")
    require(baseline["source_current_evidence"]["sha256"] == SOURCE_POINTER_SHA
            and baseline["source_final_review"]["sha256"] == SOURCE_REVIEW_SHA
            and baseline["source_map_copy"]["sha256"] == SOURCE_MAP_SHA,
            "The refinement baseline is not the published first-stage result.")
    for key in ("source_current_evidence", "source_map_copy"):
        require(Path(baseline[key]["file"]).resolve().is_relative_to((WORK/"Before").resolve()),
                "Source pointer/map copy is outside the frozen Before directory.")
        require(sha(baseline[key]["file"]) == baseline[key]["sha256"], "Frozen source pointer/map copy changed.")
    pointer, review = bound_document(baseline["source_current_evidence"]), bound_document(baseline["source_final_review"])
    require(review["passed"] is True and review["map_sha256"] == pointer["map_sha256"] == SOURCE_MAP_SHA,
            "Published source review/map identities differ.")
    require(baseline["previous_asset_sha256"] == pointer["current_asset_sha256"] == review["new_asset_sha256"]
            and len(baseline["previous_asset_sha256"]) == 927, "Source package baseline omitted or altered a file.")
    wanted_reports = {str((SOURCE/name).resolve()): pointer["current_report_sha256"][name]
                      for name in pointer["current_reports"]}
    require(len(wanted_reports) == 32 and baseline["source_report_sha256"] == wanted_reports,
            "Source report baseline omitted or introduced a report.")
    protected = dict(review["immutable_input_sha256"]); protected.update(review["source_art_sha256"])
    main_file = str((ROOT/"Content/Yastar/Maps/L_Main.umap").resolve())
    changes = baseline.get("preexisting_protected_map_changes",[])
    require(len(changes)<=1, "Only the user-edited standalone Main may predate this stage.")
    for row in changes:
        require(row["file"] == main_file and row["accepted_sha256"] == protected[main_file]
            and row["input_sha256"] != row["accepted_sha256"], "Invalid user Main input rebase.")
        protected[main_file] = row["input_sha256"]
    require(baseline["protected_file_sha256"] == protected, "Original/shared/source-art protection set differs.")
    for field in ("previous_asset_sha256", "source_report_sha256", "protected_file_sha256"):
        hashes(baseline[field], field)
    require(sha(main_file) == protected[main_file], "Protected user L_Main differs from the frozen new-stage input.")
    documents = {name: bound_document(ref) for name,ref in baseline["source_snapshot"].items()}
    for name,filename in (("actors","AfterSnapshot.json"),("native","AppearanceSnapshot.json"),("appearance","AppearanceAudit.json")):
        require(Path(baseline["source_snapshot"][name]["file"]).resolve() == (SOURCE/filename).resolve(),
                "Wrong source snapshot file: "+name)
    require(documents["actors"]["actors"] == documents["native"]["actors"]
            and len(documents["actors"]["actors"]) == baseline["actor_count"] == 8014
            and len(component_index(documents["native"]["component_records"],True)) == baseline["scene_component_count"] == 13920,
            "Complete saved/native source Actor or component coverage differs.")
    # Exact, recorded pre-stage user Blueprint edit: no blanket state exclusion.
    rebase=baseline.get("preexisting_actor_reload_change")
    if rebase:
        evidence=bound_document(rebase["evidence"])
        require(rebase["actor"] == "BP_ItemPickup" and evidence["asset"] == rebase["source_blueprint"],
                "Unexpected pre-stage actor rebase.")
        require(sha(rebase["source_blueprint"]["file"]) == rebase["source_blueprint"]["sha256"],
                "User pickup Blueprint changed after the stage input was frozen.")
        old_actor=documents["actors"]["actors"]["BP_ItemPickup"]
        current_actor=evidence["actor_state"]
        replay=deepcopy(old_actor)
        part=next(c for c in replay["components"] if c["name"] == "ItemMesh")
        require(part["mesh"] == "/Game/Yastar/Meshes/foot/base_basic_shaded/base_basic_pbr/foot.foot",
                "Source pickup mesh differs from documented prior input.")
        part["mesh"],part["materials"]=None,[]
        require(replay == current_actor, "A pickup field other than the unloaded original mesh/material changed.")
        records=documents["native"]["component_records"]["BP_ItemPickup"]
        old_component=next(c for c in records if c["name"] == "ItemMesh")
        expected_native={k:v for k,v in old_component.items() if k not in {
            "mesh","materials","local_render_bounds_cm","uniform_slot_surface_translation",
            "expected_surface_translation_cm_to_preserve","world_render_bounds_before_wpo_cm",
            "world_render_bounds_after_surface_translation_cm","world_transform_negative_determinant"}}
        require(expected_native == evidence["component"], "An unrelated pickup native field changed.")
        documents=deepcopy(documents)
        documents["actors"]["actors"]["BP_ItemPickup"]=current_actor
        documents["native"]["actors"]["BP_ItemPickup"]=current_actor
        records=documents["native"]["component_records"]["BP_ItemPickup"]
        records[records.index(next(c for c in records if c["name"]=="ItemMesh"))]=evidence["component"]
    return documents


def verify_stage(baseline, plan, after):
    """Verify replacements only; root separately binds fresh full scan/captures."""
    source = verify_baseline(baseline)
    require(plan["schema"] == PLAN_SCHEMA and plan["source_map_sha256"] == SOURCE_MAP_SHA
            and plan["source_current_evidence_sha256"] == SOURCE_POINTER_SHA,
            "Approved refinement plan identifies another source.")
    require(after["schema"] == AFTER_SCHEMA and after["source"] == "fresh_persisted_map_load"
            and after["persisted_map_unchanged"] is True and after["source_map_sha256"] == SOURCE_MAP_SHA,
            "Fresh saved-stage binding differs.")
    require(Path(after["approved_plan"]["file"]).resolve().is_relative_to(WORK.resolve())
            and bound_document(after["approved_plan"]) == plan,
            "Fresh saved-stage approved-plan file/SHA binding differs.")
    require(Path(after["map_file"]).resolve() == MAP.resolve() and sha(MAP) == after["map_sha256"] != SOURCE_MAP_SHA,
            "Current map did not persist the new stage.")
    approved = plan["components"]
    require(approved and len({r["id"] for r in approved}) == len(approved), "Approved component set is empty/duplicated.")
    actors_after = bound_document(after["actor_snapshot"])
    native_after = bound_document(after["native_snapshot"])
    require(native_after["source"] == "fresh_persisted_native_read_only"
            and native_after["map_sha256"] == after["map_sha256"]
            and actors_after.get("source_map_sha256",actors_after.get("map_sha256")) == after["map_sha256"],
            "Fresh saved/native snapshots describe another map.")
    expected = deepcopy(source["actors"]["actors"])
    expected_components = component_index(expected)
    original_native = component_index(source["native"]["component_records"],True)
    current_native = component_index(native_after["component_records"],True)
    require(set(current_native) == set(original_native), "Native component identity/coverage changed.")
    new_assets = after["new_asset_sha256"]
    require(new_assets == plan["new_asset_sha256"] and bool(new_assets)
            and all(Path(p).resolve().is_relative_to(GENERATED.resolve()) for p in new_assets)
            and set(new_assets) == {str(p.resolve()) for p in GENERATED.rglob("*") if p.is_file()},
            "New package footprint differs from its frozen approved manifest.")
    hashes(new_assets, "New refinement packages")
    used_meshes = set()
    for row in approved:
        ident = row["actor"]+"::"+row["component"]
        require(ident == row["id"] and ident in expected_components and ident in original_native,
                "Unknown approved Actor/component: "+ident)
        old, now = original_native[ident], current_native[ident]
        state = expected_components[ident]
        require(state.get("visible") is True and state.get("hidden_in_game") is False
                and row["actor"] != source["actors"]["main_home"]["actor"],
                "A hidden collider or MainHome interactive component was targeted: "+ident)
        require(state["mesh"] == old["mesh"] == row["source_mesh"]
                and state["materials"] == [m["asset"] for m in old["materials"]] == row["before_materials"],
                "Approved replacement does not match actual source component: "+ident)
        require(row["target_mesh"] == row["source_mesh"] or row["target_mesh"].startswith(ASSET_ROOT+"Meshes/"),
                "Replacement mesh escaped the new stage: "+ident)
        require(len(row["after_materials"]) == len(row["after_base_materials"]) == len(old["materials"])
                and all(m.startswith(ASSET_ROOT+"Materials/") or m == before
                        for m,before in zip(row["after_materials"],row["before_materials"])),
                "Material slot layout/reference escaped approved scope: "+ident)
        replay = deepcopy(old)
        replay["mesh"] = row["target_mesh"]
        for i,material in enumerate(replay["materials"]):
            material["asset"] = row["after_materials"][i]
            material["base_material"] = row["after_base_materials"][i]
        if row["target_mesh"] != row["source_mesh"]:
            used_meshes.add(row["target_mesh"])
            for field in ("local_render_bounds_cm", "world_render_bounds_before_wpo_cm", "world_render_bounds_after_surface_translation_cm"):
                require(now[field] == row[field], "Unapproved new render envelope: "+ident+" / "+field)
                replay[field] = row[field]
        require(now == replay, "Native pose/parent/BodyInstance/collision/WPO/unlisted field changed: "+ident)
        state["mesh"], state["materials"] = row["target_mesh"], row["after_materials"]
    changed = {r["id"] for r in approved}
    require(all(current_native[i] == old for i,old in original_native.items() if i not in changed),
            "An unapproved native component changed.")
    require(actors_after["actors"] == native_after["actors"] == expected
            and len(expected) == 8014 and actors_after["main_home"] == source["actors"]["main_home"],
            "Actor identity/class/pose/parent/collision/function or unapproved appearance changed.")
    blueprints = source["native"]["blueprints"]
    require(len(blueprints) == 18, "Source opening Blueprint coverage differs.")
    hashes({r["file"]:r["sha256"] for r in blueprints.values()}, "Original 18 opening Blueprints")
    model_specs = {r["asset"]:r for r in plan["models"]}
    require(len(model_specs) == len(plan["models"]) and set(model_specs) == used_meshes == set(after["mesh_records"]),
            "New model prescription/actual readback coverage differs.")
    model_proofs = {}
    for asset,spec in model_specs.items():
        record = after["mesh_records"][asset]
        original = source["appearance"]["meshes"][spec["source_asset"]]
        require(record["asset"] == asset and new_assets[record["file"]] == record["sha256"]
                and collision_signature(record["collision_signature"]) == collision_signature(original["collision_signature"])
                and len(record["static_material_slots"]) == len(original["static_material_slots"]),
                "New model package/collision/slot layout differs: "+asset)
        require(record["bounds_cm"] == spec["local_bounds_cm"] and sha(record["geometry_file"]) == record["geometry_sha256"],
                "New model actual envelope or geometry binding differs: "+asset)
        geometry = read(record["geometry_file"])
        recipe = bound_document(spec["recipe"])
        require(sha(spec["fbx"]["file"]) == spec["fbx"]["sha256"], "New model FBX changed: "+asset)
        model_proofs[asset] = dict(closed=native_closed_solid(geometry), frames=native_frame_proof(geometry),
            physical_uv=native_physical_uv(geometry,recipe["physical_scale"]),
            binary_source_faces=native_binary_source_face_proof(geometry,record,recipe,Path(spec["fbx"]["file"])))
    return dict(passed=True, source_map_sha256=SOURCE_MAP_SHA, map_sha256=after["map_sha256"],
        actors=8014, scene_components=13920, approved_components=len(approved),
        changed_actors=len({r["actor"] for r in approved}), prior_packages_preserved=927,
        new_packages=len(new_assets), opening_blueprints_preserved=18,
        pose_parent_bodyinstance_collision_and_wpo_preserved=True, mainhome_structure_preserved=True,
        models=model_proofs, next_required="Fresh whole-map raw scan/classifier/summary and actual visual review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("after",type=Path)
    args = parser.parse_args()
    result = verify_stage(read(args.baseline),read(args.plan),read(args.after))
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()
