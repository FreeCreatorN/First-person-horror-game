"""Accept and optionally publish whole-map realism evidence, without UE.

Default/--check-only writes fresh FinalReview.json, CaptureReview.json and
RealismFinalAudit.json in this stage. --publish additionally updates the
canonical current-report copies and writes CurrentEvidence.json last.

All checks read persisted files. No Unreal/Blender process is launched, no
package is edited, and no document is updated. Appearance mesh reconstruction
is authorized: this stage deliberately has no old-face preservation rule.

Fresh render exports and captures must bind the current Realism asset files as
well as the map. Supported binding fields are new_asset_sha256/asset_sha256
(file->SHA dictionaries) or asset_manifest_sha256 (canonical JSON SHA of the
Realism-root dictionary). PNG metadata must also carry an after-cleanup binding
as asset_sha256_after_cleanup/new_asset_sha256_after_cleanup or
asset_manifest_sha256_after_cleanup. A map-only binding cannot prove materials.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "Saved/CodexOutputs/OldTownRealism_20261012"
SOURCE = ROOT / "Saved/CodexOutputs/SanitaryFinish_20261012"
CANON = ROOT / "Saved/CodexOutputs/EnterableStreet_20261002"
GENERATED = ROOT / "Content/CodexGenerated/OldTown/Realism_20261012"
SOURCE_ART = ROOT / "SourceArt/OldTownRealism_20261012"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP = ROOT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
ASSET_ROOT = "/Game/CodexGenerated/OldTown/Realism_20261012/"
SOURCE_SHA = "ade3fcc6a6482713618e3fadbd4534771549e773097fd2b9d34886318451e1f6"
CURRENT_MAIN_INPUT_SHA = "d45a87ce99e6e38dde44550eb3591994624cf6e9af684feb84523921df35a841"
FOLLOWUP_SOURCE_SHA = "6025a94eb391fb43d09cc4972ce3d7c8192b7e712578155d517a00b035caeb43"
FOLLOWUP_COMPONENT = "OTS_HotelV4_Vestibule_Front_02::StaticMeshComponent0"
MODEL_CLOSURE_MAP_SHA = "82b8b44a08c223ca654807f85b633e0cf7e912372f82e84a3cdd8d816e873f5e"
MODEL_CLOSURE_FROZEN_REPORTS = ("RealismApply.json", "Applied.json", "ExpectedSnapshot.json",
    "ArchitecturePlan.json", "FollowupSurfaceRepairs.json", "AdditionalSurfaceRepairs.json",
    "MaterialRoleRepairs.json", "RealismInput.json", "RealismStreetInput.json",
    "SourceSolidsRepair.json", "SourceSolidsIndependentAudit.json")
COUNTS = dict(actors=8014, hotel=2975, outside=5039, furniture_variants=33,
              furniture_actors=680, architecture_variants=82,
              sanitary_variants=4, sanitary_actors=114, street_variants=24)
CAMERAS = {"CAM_V4_Reception", "CAM_V4_LobbyWide", "CAM_V4_GuestTwin",
    "CAM_Detail_StairRail", "CAM_Surface_WindowInside", "CAM_Basin_Guest201",
    "CAM_Shape_ToiletFullPublic", "CAM_V4_Exterior", "CAM_Cleanup_MainStreet",
    "CAM_StreetAccess_Lamp", "CAM_Enterable_Bedroom", "CAM_OTS_Alley"}
REPORTS = ("BuildReport.json", "Applied.json", "RealismInput.json", "RealismApply.json",
    "ExpectedSnapshot.json", "AfterSnapshot.json", "ArchitecturePlan.json",
    "AppearanceAudit.json", "ArchitectureAudit.json", "DetailAudit.json", "AfterSummary.json",
    "FurnitureAssetBuild.json", "ArchitectureAssetBuild.json", "SanitaryAssetBuild.json",
    "MaterialBuild.json", "RealismStreetInput.json", "StreetAssetBuild.json", "UserSavedInputRebase.json",
    "AdditionalSurfaceRepairs.json", "MaterialRoleRepairs.json", "FollowupSurfaceRepairs.json", "ModelClosureImportRepairs.json", "SourceSolidsRepair.json", "SourceSolidsIndependentAudit.json",
    "AxisVerification.json", "SavedScan.json", "SavedScanOcclusion.json",
    "SavedScanSummary.json", "VisualReview.json", "CaptureReview.json", "RealismFinalAudit.json", "FinalReview.json")
AUDIT_INPUTS = ("RealismInput.json", "BuildReport.json", "RealismApply.json",
    "ExpectedSnapshot.json", "AfterSnapshot.json", "FurnitureAssetBuild.json",
    "ArchitectureAssetBuild.json", "SanitaryAssetBuild.json", "MaterialBuild.json", "RealismStreetInput.json", "StreetAssetBuild.json",
    "AdditionalSurfaceRepairs.json", "MaterialRoleRepairs.json", "FollowupSurfaceRepairs.json", "ModelClosureImportRepairs.json")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, data):
    path = Path(path)
    require(path.resolve().is_relative_to(WORK.resolve()) or
            path.resolve().is_relative_to(CANON.resolve()), "Output escapes publication directories: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def normalized(values):
    require(isinstance(values, dict), "Expected a file SHA dictionary.")
    result = {}
    for name, digest in values.items():
        path = Path(name)
        require(path.is_absolute() and re.fullmatch(r"[0-9a-f]{64}", str(digest)),
                "Invalid absolute file/SHA manifest entry: " + str(name))
        key = str(path.resolve())
        require(key not in result, "Aliased duplicate file in hash manifest: " + key)
        result[key] = digest
    return result


def hashes(values, label, count=None):
    values = normalized(values)
    require(bool(values) and (count is None or len(values) == count), label + " has an incomplete file set.")
    for name, digest in values.items():
        require(Path(name).is_file() and sha(name) == digest, label + " changed: " + name)
    return values


def json_fingerprint(values):
    # Absolute normalized filenames make this fingerprint portable between
    # manifests in the same workspace, regardless of dictionary insertion order.
    payload = json.dumps(normalized(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def root_subset(values):
    return {name: digest for name, digest in normalized(values).items()
            if Path(name).is_relative_to(GENERATED.resolve())}


def asset_binding(document, expected, label, after=False, required=True):
    fields = (("new_asset_sha256_after_cleanup", "asset_sha256_after_cleanup") if after
              else ("new_asset_sha256", "asset_sha256"))
    fingerprint = "asset_manifest_sha256_after_cleanup" if after else "asset_manifest_sha256"
    found = False
    for field in fields:
        if field in document:
            found = True
            values = normalized(document[field])
            require(root_subset(values) == expected, label + " binds a different Realism asset set: " + field)
            # Additional older Codex packages are allowed only with their actual
            # current file hashes; they cannot disguise an incomplete new root.
            hashes(values, label + " " + field)
    if fingerprint in document:
        found = True
        require(document[fingerprint] == json_fingerprint(expected), label + " asset fingerprint differs.")
    require(found or not required, label + " lacks a current asset fingerprint (map SHA alone is insufficient).")
    return found


def current_report(name, digest, fresh=False, directory=None):
    report = read((WORK if directory is None else directory) / name)
    require(report.get("passed") is True and not report.get("errors") and report.get("map_sha256") == digest,
            name + " failed or describes another saved map.")
    require(report.get("target_level", TARGET) == TARGET, name + " describes another level.")
    checks = report.get("checks")
    if checks is not None:
        require(isinstance(checks, list) and bool(checks) and all(r.get("passed") is True and r.get("name") for r in checks)
                and len(checks) == len({r["name"] for r in checks}), name + " has failed, duplicate or missing checks.")
    if fresh:
        require(report.get("source") == "fresh_persisted_map_load" and report.get("persisted_map_unchanged") is True,
                name + " lacks an unchanged fresh saved-map load.")
    for field in ("input_sha256", "source_input_sha256"):
        if report.get(field):
            hashes(report[field], name + " inputs")
    return report


def canonical_source():
    pointer = read(CANON / "CurrentEvidence.json")
    current_pointer_hash = sha(CANON / "CurrentEvidence.json")
    already_published = Path(pointer.get("source_bundle", "")).resolve() == WORK.resolve()
    if already_published:
        previous = read(WORK / "BeforeCanonicalPublish/CurrentEvidence.json")
    else:
        previous = pointer
    require(Path(previous.get("source_bundle", "")).resolve() == SOURCE.resolve()
            and previous.get("map_sha256") == SOURCE_SHA,
            "Canonical evidence advanced to another task; refusing to overwrite it.")
    names = previous.get("current_reports", [])
    require(names and all(Path(n).name == n and n.endswith(".json") for n in names), "Unsafe/incomplete previous report names.")
    for name in names:
        wanted = previous.get("current_report_sha256", {}).get(name)
        require(wanted and sha(SOURCE / name) == wanted, "Prior accepted report changed: " + name)
        if not already_published:
            require(sha(CANON / name) == wanted, "Prior canonical report changed: " + name)
    return previous, current_pointer_hash


def component_index(actors):
    result = {}
    for actor, state in actors.items():
        for component in state["components"]:
            key = actor + "::" + component["name"]
            require(key not in result, "Duplicate Actor/component identity: " + key)
            result[key] = component
    return result


def merge_hashes(first, second, label):
    first, second = normalized(first), normalized(second)
    require(all(first[p] == second[p] for p in set(first) & set(second)), label + " disagrees on a shared input file.")
    return dict(first, **second)


def whole_map_input(inp, street):
    """Keep the original hotel inventory immutable; merge the fresh street read."""
    require(street.get("passed") is True and street.get("source_map_sha256") == SOURCE_SHA
            and street.get("source") == "fresh_persisted_map_load_read_only"
            and Path(street.get("input_inventory_file", "")).resolve() == (WORK / "RealismInput.json").resolve()
            and street.get("input_inventory_sha256") == sha(WORK / "RealismInput.json"),
            "Street input does not bind the accepted read-only hotel inventory.")
    before = read(inp["baseline_snapshot_file"])["actors"]
    hotel = set(inp["hotel_actor_labels"])
    outside = set(before) - hotel
    require(len(street.get("actor_labels", [])) == len(set(street.get("actor_labels", []))) == COUNTS["outside"]
            and set(street["actor_labels"]) == set(street["component_records"]) == outside
            and street.get("actor_count") == COUNTS["outside"], "Street input omitted or duplicated an outside-hotel Actor.")
    require(set(inp["component_records"]) == hotel and not set(inp["component_records"]) & set(street["component_records"]),
            "Hotel/street native Actor inventories overlap or are incomplete.")
    require(normalized(street["original_400_shared_asset_sha256"]) == normalized(inp["original_400_shared_asset_sha256"]),
            "Street input changed the original 400-file protection set.")
    merged = deepcopy(inp)
    merged["component_records"].update(street["component_records"])
    merged["source_asset_file_sha256"] = merge_hashes(inp["source_asset_file_sha256"], street["source_asset_file_sha256"], "Hotel/street native source hashes")
    merged["protected_map_sha256"] = deepcopy(street["protected_map_sha256"])
    require(set(merged["component_records"]) == set(before), "Whole-map native inventory does not cover all Actor identities.")
    return merged


def protected_input_rebase(hotel_input, street_input):
    rebase = read(WORK / "UserSavedInputRebase.json")
    prior = normalized(hotel_input["protected_map_sha256"])
    current = normalized(street_input["protected_map_sha256"])
    main = str((ROOT / "Content/Yastar/Maps/L_Main.umap").resolve())
    changes = [dict(file=main, old_sha256=prior[main], new_sha256=current[main])]
    require(rebase.get("passed") is True and rebase.get("source_map_sha256") == SOURCE_SHA
            and rebase.get("original_shared_assets_unchanged") is True
            and normalized(rebase.get("prior_input", {})) == prior and normalized(rebase.get("current_input", {})) == current
            and rebase.get("changes") == changes and set(prior) == set(current)
            and all(prior[p] == current[p] for p in prior if p != main)
            and current[main] == CURRENT_MAIN_INPUT_SHA,
            "Latest d45a MainHome input rebase is not the exact sole protected-map update.")
    return dict(passed=True, file=str(WORK / "UserSavedInputRebase.json"),
        sha256=sha(WORK / "UserSavedInputRebase.json"), changes=changes,
        latest_protected_map_sha256=current)


def near_vector(first, second, tolerance=.000002):
    return isinstance(first, (list, tuple)) and isinstance(second, (list, tuple)) and len(first) == len(second) == 3 and all(
        isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tolerance
        for a, b in zip(first, second))


def verify_material_role_repairs(build, inp, apply, applied, digest, stage_directory=None):
    stage_directory = WORK if stage_directory is None else stage_directory
    report = current_report("MaterialRoleRepairs.json", digest, directory=stage_directory)
    directory = WORK / "BeforeMaterialRoles"
    require(report.get("schema") == "OldTownRealismMaterialRoleRepairsV1" and report == build.get("material_role_repairs")
            and report.get("actor_poses_and_collision_unchanged") is True
            and report.get("changed_component_count") == applied.get("material_role_repairs") == 1519
            and report.get("concrete_component_count") == 2104 and build.get("realism_refinement") == apply,
            "Wall/floor material routing lacks exact Build/Applied/RealismApply bindings.")
    before_build, before_apply = read(directory / "BuildReport.json"), read(directory / "RealismApply.json")
    source_digest = sha(directory / MAP.name)
    require(report.get("source_map_sha256") == before_build.get("map_sha256") == before_apply.get("map_sha256") == source_digest
            and source_digest != digest and before_build.get("source_map_sha256") == before_apply.get("source_map_sha256") == SOURCE_SHA,
            "Material role repair does not bind its exact saved contact-repair predecessor.")
    inputs = {str((WORK / n).resolve()): sha(WORK / n) for n in ("RealismInput.json", "RealismStreetInput.json")}
    require(normalized(report.get("source_input_sha256", {})) == inputs, "Material role routing used different native source inventories.")
    source_components = {n + "::" + c["name"]: c for n, components in inp["component_records"].items() for c in components}
    before_rows = {r["id"]: r for r in before_apply["components"]}
    current_rows = {r["id"]: r for r in apply["components"]}
    routed = {r["id"]: r for r in report["components"]}
    require(len(routed) == len(report["components"]) == 1519 and len(before_rows) == len(before_apply["components"])
            and len(current_rows) == len(apply["components"]) and set(before_rows) == set(current_rows),
            "Material role repair duplicated, added, or removed an appearance component.")
    from OldTownRealismSurfaceRoles import concrete_role
    concrete = {i for i, r in before_rows.items() if "Concrete" in r["role"]}
    walls = {i for i in concrete if concrete_role(before_rows[i]["actor"], before_rows[i]["component"], source_components[i]) == "ConcreteWall"}
    floors = concrete - walls
    retained = report.get("retained_floor_component_ids", [])
    require(len(concrete) == 2104 and len(walls) == 1519 and len(floors) == 585 and set(routed) == walls
            and len(retained) == len(set(retained)) == 585 and set(retained) == floors and not walls & floors
            and {i for i, r in current_rows.items() if "ConcreteWall" in r["role"]} == walls
            and {i for i, r in current_rows.items() if "Concrete" in r["role"]} == floors,
            "Measured source use does not separate the exact 1519 walls and 585 floors.")
    material = read(stage_directory / "MaterialBuild.json")
    material_rows = {r["asset"]: r for r in material["assets"]}
    overrides = {r["id"]: r for r in build["surface_repair"]["material_overrides"]}
    expected = deepcopy(read(directory / "ExpectedSnapshot.json")["actors"])
    expected_components = component_index(expected)
    for ident, previous in before_rows.items():
        replay = deepcopy(previous)
        if ident in routed:
            row = routed[ident]
            target_roles = ["ConcreteWall" if role == "Concrete" else role for role in previous["role"]]
            require(ident == row.get("actor", "") + "::" + row.get("component", "") and row.get("appearance_only") is True
                    and row.get("source_roles") == previous["role"] and row.get("target_roles") == target_roles
                    and row.get("before_materials") == previous["after_materials"]
                    and near_vector(row.get("offset_cm"), previous["expected_offset_cm"])
                    and len(row["after_materials"]) == len(row["target_roles"]) == len(row["before_materials"]),
                    "A wall material role changes unlisted slots/offsets or its source identity: " + ident)
            for slot, (old_role, role, asset) in enumerate(zip(previous["role"], target_roles, row["after_materials"])):
                if old_role != "Concrete":
                    require(asset == previous["after_materials"][slot], "Material routing changed a non-concrete slot: " + ident)
                else:
                    registered = material_rows.get(asset, {})
                    require(registered.get("role") == "ConcreteWall" and registered.get("projection") == previous["projection"]
                            and near_vector(registered.get("offset_cm", [0., 0., 0.]), previous["expected_offset_cm"]),
                            "A routed material has the wrong wall role, projection or WPO: " + ident)
            replay.update(role=target_roles, after_materials=row["after_materials"])
            require(expected_components[ident]["materials"] == previous["after_materials"], "Role Before actor snapshot differs: " + ident)
            expected_components[ident]["materials"] = row["after_materials"]
            if ident in overrides:
                require(near_vector(overrides[ident]["offset_cm"], previous["expected_offset_cm"])
                        and overrides[ident]["materials"] == [dict(slot=i, original=m, asset=row["after_materials"][i])
                            for i, m in enumerate(row["before_materials"])], "Build role routing surface slots differ: " + ident)
        require(current_rows[ident] == replay, "Wall/floor routing changed another appearance field or component: " + ident)
    require(read(stage_directory / "ExpectedSnapshot.json")["actors"] == expected,
            "Material role routing moved an Actor or changed pose, parent, collision, mesh or unlisted materials.")
    role_script = ROOT / "Scripts/OldTownRealismSurfaceRoles.py"
    files = {str(p.resolve()): sha(p) for p in [role_script, directory / MAP.name, directory / "BuildReport.json",
        directory / "RealismApply.json", directory / "ExpectedSnapshot.json", directory / "ArchitecturePlan.json",
        directory / "MaterialBuild.json", directory / "AdditionalSurfaceRepairs.json"]}
    return routed, dict(passed=True, wall_components=1519, retained_floor_components=585, concrete_components=2104,
        source_map_sha256=source_digest, current_map_sha256=digest, source_input_sha256=inputs,
        file=str(stage_directory / "MaterialRoleRepairs.json"), sha256=sha(stage_directory / "MaterialRoleRepairs.json"),
        only_concrete_role_and_material_references_changed=True, prior_and_classifier_file_sha256=files)


def verify_additional_repairs(build, inp, apply, digest, material_roles, stage_directory=None):
    stage_directory = WORK if stage_directory is None else stage_directory
    report = current_report("AdditionalSurfaceRepairs.json", digest, directory=stage_directory)
    directory = WORK / "BeforeContacts"
    require(report == build.get("additional_surface_repairs") and report.get("appearance_only") is True
            and report.get("actor_poses_and_collision_unchanged") is True and report.get("count") == 51
            and report.get("maximum_added_offset_cm") == .06, "Fixed contact repair acceptance/Build binding is incomplete.")
    require(report.get("source_map_sha256") == sha(directory / MAP.name)
            and report["source_map_sha256"] != digest, "Contact repair does not bind its exact prior persisted map.")
    before_build = read(directory / "BuildReport.json")
    before_apply = read(directory / "RealismApply.json")
    require(before_build.get("map_sha256") == before_apply.get("map_sha256") == report["source_map_sha256"]
            and before_build.get("source_map_sha256") == before_apply.get("source_map_sha256") == SOURCE_SHA,
            "Contact repair Before files do not identify the authorized whole-map appearance result.")
    contact_directory = WORK / "BeforeMaterialRoles"
    contact_outcome = read(contact_directory / "RealismApply.json")
    source_contact_report = read(contact_directory / "AdditionalSurfaceRepairs.json")
    require(source_contact_report.get("map_sha256") == contact_outcome.get("map_sha256") == report.get("applied_map_sha256")
            == sha(contact_directory / MAP.name) and report["applied_map_sha256"] != digest,
            "Contact repair outcome does not precede the bound material-role stage.")
    source_repairs = {r["id"]: r for r in source_contact_report["components"]}
    expected_report = deepcopy(source_contact_report)
    expected_report.update(map_sha256=digest, applied_map_sha256=source_contact_report["map_sha256"])
    for row in expected_report["components"]:
        if row["id"] in material_roles:
            row["after_materials"] = material_roles[row["id"]]["after_materials"]
    require(report == expected_report, "Current contact report changed fields beyond its exact subsequent material routing.")
    furniture = read(SOURCE_ART / "Furniture/ModelDataManifest.json")
    head_ids = {r["actor_label"] + "::StaticMeshComponent0" for r in furniture["actors"] if r["kind"] == "BedHead"}
    require(len(head_ids) == 48, "The exact 48 original bed-head contact instances differ.")
    deltas = {"OTS_HotelV4_Vestibule_Front_00::StaticMeshComponent0": [0., .06, 0.],
        "OTS_HotelV4_Vestibule_Front_01::StaticMeshComponent0": [0., -.06, 0.],
        "OTS_HotelV4_Vestibule_Front_02::StaticMeshComponent0": [0., 0., -.06]}
    deltas.update({i: [.06, 0., 0.] for i in head_ids})
    repairs = {r["id"]: r for r in report["components"]}
    require(len(repairs) == len(report["components"]) == 51 and set(repairs) == set(deltas),
            "Additive repair escapes or omits the prescribed 3 walls and 48 bed heads.")
    native_source = {n + "::" + c["name"]: c for n, components in inp["component_records"].items() for c in components}
    before_rows = {r["id"]: r for r in before_apply["components"]}
    contact_rows = {r["id"]: r for r in contact_outcome["components"]}
    after_rows = {r["id"]: r for r in apply["components"]}
    require(len(before_rows) == len(before_apply["components"]) and len(after_rows) == len(apply["components"])
            and len(contact_rows) == len(contact_outcome["components"]) and set(before_rows) == set(after_rows) == set(contact_rows),
            "Contact repair added or removed an appearance component.")
    overrides = {r["id"]: r for r in build["surface_repair"]["material_overrides"]}
    for ident, previous in before_rows.items():
        expected = deepcopy(previous)
        if ident in repairs:
            spec = source_repairs[ident]
            source_offset = native_source[ident]["expected_surface_translation_cm_to_preserve"]
            expected_offset = [round(float(v) + d, 6) for v, d in zip(source_offset, deltas[ident])]
            require(ident == spec["actor"] + "::" + spec["component"] and spec.get("appearance_only") is True
                    and near_vector(spec["source_offset_cm"], source_offset)
                    and near_vector(previous["expected_offset_cm"], source_offset)
                    and near_vector(spec["delta_cm"], deltas[ident])
                    and near_vector(spec["expected_offset_cm"], expected_offset)
                    and spec["before_materials"] == previous["after_materials"]
                    and spec["after_materials"] == contact_rows[ident]["after_materials"],
                    "An additive contact delta/source/material identity differs: " + ident)
            expected.update(after_materials=spec["after_materials"], expected_offset_cm=spec["expected_offset_cm"])
            require(ident in overrides and near_vector(overrides[ident]["offset_cm"], expected_offset)
                    and [m["asset"] for m in overrides[ident]["materials"]] == after_rows[ident]["after_materials"],
                    "Build surface-repair slot offsets disagree with the fixed delta: " + ident)
        require(contact_rows[ident] == expected, "Contact stage changed an unlisted pre-routing appearance field: " + ident)
        if ident in material_roles:
            expected.update(role=material_roles[ident]["target_roles"], after_materials=material_roles[ident]["after_materials"])
        require(after_rows[ident] == expected, "Contact repair modified unlisted appearance fields: " + ident)
    diagnostic = WORK / "BeforePrecisionEvidence/ExposedGroups.json"
    require(report.get("diagnostic_sha256") == sha(diagnostic), "Contact repair binds a different exposed-group diagnosis.")
    groups = read(diagnostic)
    external = [r for r in groups if not r["intra_component"]]
    require(len(external) == 51 and all(not r["buried"] for r in external)
            and all(any(i in r["components"] for r in external) for i in repairs), "The complete external contact diagnosis is missing.")
    files = {str(p.resolve()): sha(p) for p in [diagnostic, directory / MAP.name,
        directory / "BuildReport.json", directory / "RealismApply.json", directory / "ExpectedSnapshot.json"]}
    return repairs, dict(passed=True, component_count=51, wall_components=3, bed_head_components=48,
        maximum_added_offset_cm=.06, source_map_sha256=report["source_map_sha256"], current_map_sha256=digest,
        file=str(stage_directory / "AdditionalSurfaceRepairs.json"), sha256=sha(stage_directory / "AdditionalSurfaceRepairs.json"),
        prior_and_diagnostic_file_sha256=files)


def verify_followup_surface_repairs(build, inp, apply, applied, digest):
    """Replay the three saved stages, preserving every historical delta."""
    directory = WORK / "BeforeFollowupSurfaceRepairs"
    before_build = read(directory / "BuildReport.json")
    before_apply = read(directory / "RealismApply.json")
    before_applied = read(directory / "Applied.json")
    source_digest = sha(directory / MAP.name)
    require(source_digest == FOLLOWUP_SOURCE_SHA == before_build.get("map_sha256")
            == before_apply.get("map_sha256") == before_applied.get("map_sha256")
            and digest != source_digest,
            "Followup repair does not follow the exact persisted 6025 wall/floor result.")
    # These are the unchanged original validators, against their exact saved
    # outcome, rather than accepting a later stage as their historical result.
    role_rows, roles = verify_material_role_repairs(before_build, inp, before_apply,
        before_applied, source_digest, stage_directory=directory)
    repairs, contacts = verify_additional_repairs(before_build, inp, before_apply,
        source_digest, role_rows, stage_directory=directory)
    require(before_applied.get("additional_surface_repairs") == 51,
            "Followup predecessor omitted the fixed 51 original contact repairs.")
    for name, field in (("AdditionalSurfaceRepairs.json", "additional_surface_repairs"),
                        ("MaterialRoleRepairs.json", "material_role_repairs")):
        historical = read(directory / name)
        rebound = deepcopy(historical)
        rebound["map_sha256"] = digest
        if name == "MaterialRoleRepairs.json":
            rebound["applied_map_sha256"] = source_digest
        require(current_report(name, digest) == build.get(field) == rebound,
                "Followup altered a historical repair component/delta or its applied map: " + name)
    report = current_report("FollowupSurfaceRepairs.json", digest)
    require(report == build.get("followup_surface_repairs")
            and report.get("schema") == "OldTownRealismFollowupSurfaceRepairsV1"
            and report.get("source_map_sha256") == source_digest
            and report.get("count") == applied.get("followup_surface_repairs") == 1
            and report.get("maximum_added_offset_cm") == .06
            and report.get("appearance_only") is True
            and report.get("actor_poses_and_collision_unchanged") is True
            and build.get("realism_refinement") == apply,
            "Single followup repair lacks exact Build/Applied/source-map bindings.")
    rows = report.get("components", [])
    require(len(rows) == 1 and rows[0].get("id") == FOLLOWUP_COMPONENT,
            "Followup repair changes or duplicates a component outside the sole Front02 contact.")
    row = rows[0]
    before_rows = {r["id"]: r for r in before_apply["components"]}
    current_rows = {r["id"]: r for r in apply["components"]}
    require(len(before_rows) == len(before_apply["components"]) == len(current_rows)
            == len(apply["components"]) == 8684 and set(before_rows) == set(current_rows),
            "Followup added, removed, or duplicated a whole-map appearance component.")
    previous = before_rows[FOLLOWUP_COMPONENT]
    expected_offset = [round(float(v) + d, 6) for v, d in
                       zip(previous["expected_offset_cm"], [.06, 0., 0.])]
    require(row.get("actor") == previous["actor"] == "OTS_HotelV4_Vestibule_Front_02"
            and row.get("component") == previous["component"] == "StaticMeshComponent0"
            and row.get("appearance_only") is True
            and row.get("role") == previous["role"] == ["Plaster"]
            and row.get("projection") == previous["projection"] == "World"
            and near_vector(row.get("source_offset_cm"), previous["expected_offset_cm"])
            and near_vector(row.get("delta_cm"), [.06, 0., 0.])
            and near_vector(row.get("expected_offset_cm"), expected_offset)
            and row.get("before_materials") == previous["after_materials"]
            and len(row.get("after_materials", [])) == len(row["before_materials"]) == len(previous["role"])
            and row["after_materials"] != row["before_materials"],
            "Front02 followup changed its role/projection, source slots, or fixed +X 0.06 cm delta.")
    replay = deepcopy(before_apply)
    replay["map_sha256"] = digest
    for item in replay["components"]:
        if item["id"] == FOLLOWUP_COMPONENT:
            item.update(after_materials=row["after_materials"], expected_offset_cm=row["expected_offset_cm"])
    require(apply == replay,
            "Followup changed an unlisted field/component in the complete 8684-row apply document.")
    replay_applied = deepcopy(before_applied)
    replay_applied.update(map_sha256=digest, followup_surface_repairs=1)
    require(applied == replay_applied, "Followup changed an unlisted Applied count or source binding.")
    expected = deepcopy(read(directory / "ExpectedSnapshot.json")["actors"])
    components = component_index(expected)
    require(len(expected) == 8014 and components[FOLLOWUP_COMPONENT]["materials"] == row["before_materials"],
            "Followup predecessor snapshot does not contain the source Front02 slots.")
    components[FOLLOWUP_COMPONENT]["materials"] = row["after_materials"]
    require(read(WORK / "ExpectedSnapshot.json")["actors"] == expected,
            "Followup changed an Actor/component mesh, identity, parent, pose, collision or unlisted material.")
    material_rows = {r["asset"]: r for r in read(WORK / "MaterialBuild.json")["assets"]}
    original_material_rows = {r["asset"]: r for r in read(directory / "MaterialBuild.json")["assets"]}
    require(all(material_rows.get(asset) == original for asset, original in original_material_rows.items()),
            "Followup changed or removed an existing material/texture registration.")
    added_materials = set(material_rows) - set(original_material_rows)
    require(added_materials == set(row["after_materials"]),
            "Followup introduced an unlisted material registration.")
    for role, old_asset, asset in zip(row["role"], row["before_materials"], row["after_materials"]):
        registered, original = material_rows.get(asset, {}), material_rows.get(old_asset, {})
        require(asset.startswith(ASSET_ROOT + "Materials/") and registered.get("kind") == "offset_instance"
                and registered.get("role") == original.get("role") == role
                and registered.get("projection") == original.get("projection") == "World"
                and registered.get("parent") == original.get("parent")
                and near_vector(original.get("offset_cm"), row["source_offset_cm"])
                and near_vector(registered.get("offset_cm"), expected_offset),
                "Followup changed the material role/master/projection or does not implement its precise WPO.")
    old_assets = normalized(before_build["new_asset_sha256"])
    current_assets = normalized(build["new_asset_sha256"])
    added_asset_files = {str(Path(material_rows[asset]["file"]).resolve()) for asset in added_materials}
    require(set(old_assets) <= set(current_assets)
            and all(current_assets[path] == old_digest for path, old_digest in old_assets.items())
            and set(current_assets) - set(old_assets) == added_asset_files
            and all(current_assets[path] == material_rows[asset]["sha256"]
                    for asset in added_materials for path in [str(Path(material_rows[asset]["file"]).resolve())]),
            "Followup altered an existing generated package or introduced an unlisted package.")
    previous_overrides = {r["id"]: r for r in before_build["surface_repair"]["material_overrides"]}
    replay_overrides = deepcopy(previous_overrides)
    require(FOLLOWUP_COMPONENT in replay_overrides, "Front02 lacks its original preserved render-offset record.")
    replay_overrides[FOLLOWUP_COMPONENT] = dict(id=FOLLOWUP_COMPONENT, offset_cm=row["expected_offset_cm"],
        materials=[dict(slot=i, original=m, asset=row["after_materials"][i])
                   for i, m in enumerate(row["before_materials"])])
    current_overrides = {r["id"]: r for r in build["surface_repair"]["material_overrides"]}
    require(len(current_overrides) == len(build["surface_repair"]["material_overrides"])
            and current_overrides == replay_overrides,
            "Followup changed an unlisted Build surface offset/material override.")
    diagnostic = directory / "ExposedGroups.json"
    prior_summary = directory / "SavedScanSummary.json"
    require(Path(report.get("diagnostic_file", "")).resolve() == diagnostic.resolve()
            and report.get("diagnostic_sha256") == sha(diagnostic)
            and Path(report.get("prior_saved_scan_summary_file", "")).resolve() == prior_summary.resolve()
            and report.get("prior_saved_scan_summary_sha256") == sha(prior_summary),
            "Followup binds another contact diagnosis or prior saved-scan summary.")
    groups = read(diagnostic)
    old_scan = read(directory / "SavedScanOcclusion.json")
    require(old_scan.get("source_map_sha256") == source_digest
            and old_scan.get("source_geometry_sha256") == sha(directory / "GeometryAfter.json")
            and groups == [r for r in old_scan["overlaps"] if not r["buried"]]
            and not old_scan.get("exact_duplicate_boxes"),
            "Followup diagnosis differs from the complete persisted 6025 geometry scan.")
    expected_pairs = {(f"OTS_HotelV4_Vestibule_Front_{i:02d}::StaticMeshComponent0", sign)
                      for i in (0, 1) for sign in (-1., 1.)}
    actual_pairs = set()
    for group in groups:
        other = [i for i in group["components"] if i != FOLLOWUP_COMPONENT]
        require(len(group["components"]) == 2 and FOLLOWUP_COMPONENT in group["components"]
                and len(other) == 1 and not group["intra_component"] and not group["buried"]
                and group.get("projection_axis") == "x"
                and near_vector(group.get("normal"), [group["normal"][0], 0., 0.])
                and group["normal"][0] in (-1., 1.) and group.get("exposed_area_cm2", 0) > 0,
                "Followup diagnosis contains an unrelated plane, pair or internal/buried contact.")
        actual_pairs.add((other[0], group["normal"][0]))
    require(len(groups) == 4 and actual_pairs == expected_pairs,
            "Followup must bind the sole four Front00/01 versus Front02 +X/-X contact groups.")
    files = {str(p.resolve()): sha(p) for p in [directory / MAP.name, diagnostic] +
        [directory / n for n in ("BuildReport.json", "RealismApply.json", "ExpectedSnapshot.json",
        "ArchitecturePlan.json", "MaterialBuild.json", "Applied.json", "AdditionalSurfaceRepairs.json",
        "MaterialRoleRepairs.json", "InputSnapshot.json", "AfterSnapshot.json", "GeometryAfter.json",
        "SavedScan.json", "SavedScanOcclusion.json", "SavedScanSummary.json", "VisualReview.json", "VisualReviewTeam.json")]}
    return repairs, contacts, roles, {FOLLOWUP_COMPONENT: row}, dict(passed=True, component_count=1,
        delta_cm=[.06, 0., 0.], source_map_sha256=source_digest, current_map_sha256=digest,
        appearance_components_replayed=8684, actor_snapshots_replayed=8014,
        original_51_contacts_and_1519_wall_585_floor_roles_preserved=True,
        file=str(WORK / "FollowupSurfaceRepairs.json"), sha256=sha(WORK / "FollowupSurfaceRepairs.json"),
        prior_and_diagnostic_file_sha256=files)


def native_exact_edge_proof(geometry):
    edges = Counter()
    for section in geometry["sections"]:
        for start in range(0, len(section["triangle_indices"]), 3):
            points = [tuple(section["vertices_cm"][i]) for i in section["triangle_indices"][start:start+3]]
            require(len(set(points)) == 3, "Exact Native face collapsed.")
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edges[tuple(sorted((points[a], points[b])))] += 1
    return dict(exact_odd_edges=sum(v % 2 for v in edges.values()), exact_edge_count=len(edges))


def native_frame_proof(geometry):
    from AuditOldTownRealismAppearance import finite_vector
    count = negative = invalid = uv_zero = 0
    for section in geometry["sections"]:
        positions, indices, normals, tangents, uv = (section[k] for k in
            ("vertices_cm", "triangle_indices", "normals", "tangents", "uv0"))
        require(len(positions) == len(normals) == len(tangents) == len(uv), "Native corner buffer sizes differ.")
        invalid += sum(not finite_vector(n, True) for n in normals)
        invalid += sum(not finite_vector(t["tangent_x"], True) for t in tangents)
        for start in range(0, len(indices), 3):
            ids = indices[start:start+3]
            a, b, c = [positions[i] for i in ids]
            ab, ac = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
            cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            # Persisted UE render indices use clockwise orientation. Require
            # every real corner to retain that fixed convention, independently
            # of the repair report's sign claim; zero and mixed signs fail.
            negative += sum(-sum(cross[k]*normals[i][k] for k in range(3)) <= 0 for i in ids)
            ua, ub, uc = [uv[i] for i in ids]
            area = (ub[0]-ua[0])*(uc[1]-ua[1])-(ub[1]-ua[1])*(uc[0]-ua[0])
            uv_zero += not math.isfinite(area) or abs(area) < 1e-12
            count += 1
    require(invalid == negative == uv_zero == 0, "Recovered Native normals/tangents/UV faces are invalid.")
    return dict(passed=True, triangles=count, nonfinite_or_zero_frames=invalid,
        nonpositive_corner_normals=negative, degenerate_uv0_triangles=uv_zero,
        expected_corner_normal_sign=-1, original_native_normal_orientation_preserved=True)


def native_binary_source_face_proof(geometry, record, recipe, fbx_file):
    """Bijection of actual binary FBX faces to recovered UE render faces/roles."""
    from collections import defaultdict
    from itertools import product
    from DiagnoseOldTownNativeSourceSolids import f32
    from ValidateOldTownRealismSourceSolids import fbx_mesh
    binary = fbx_mesh(fbx_file)
    require(binary["triangles"] == recipe["triangles"] and binary["material_indices"] == recipe["material_indices"],
            "Binary source FBX topology/material partitions differ from the frozen recipe.")
    vertices = [tuple(float(v)*100 for v in point) for point in binary["vertices"]]
    require(len(vertices) == len(recipe["vertices_cm"]) and all(max(abs(a-b) for a,b in zip(p,q)) < 2.e-5
            for p,q in zip(vertices, recipe["vertices_cm"])), "Binary source FBX positions differ from the frozen recipe.")
    keys = {tuple(f32(v) for v in point) for point in vertices}
    tolerance = 2.e-5
    cell = lambda p: tuple(math.floor(v/tolerance) for v in p)
    buckets = defaultdict(list)
    for point in keys:
        buckets[cell(point)].append(point)
    actual = {tuple(p) for s in geometry["sections"] for p in s["vertices_cm"]}
    mapping, maximum = {}, 0.
    for point in actual:
        at = cell(point)
        candidates = []
        for delta in product((-1,0,1), repeat=3):
            for other in buckets.get(tuple(at[i]+delta[i] for i in range(3)), ()):
                error = max(abs(point[i]-other[i]) for i in range(3))
                if error <= tolerance:
                    candidates.append((sum((point[i]-other[i])**2 for i in range(3)), error, other))
        candidates.sort()
        require(candidates and (len(candidates) == 1 or candidates[0][0] < candidates[1][0]),
                "Recovered Native vertex has no unique nearest actual source coordinate.")
        mapping[point] = candidates[0][2]
        maximum = max(maximum, candidates[0][1])
    require(len(mapping) == len(keys) == len(set(mapping.values())),
            "Recovered Native/source vertex mapping is not bijective.")
    def cyclic(points):
        return min(points, points[1:]+points[:1], points[2:]+points[:2])
    def source_key(index):
        return tuple(f32(v) for v in vertices[index])
    source_faces = Counter()
    for tri, material in zip(binary["triangles"], binary["material_indices"]):
        # Source uses outward triangles; actual UE render indices are clockwise.
        source_faces[(cyclic(tuple(source_key(i) for i in (tri[0],tri[2],tri[1]))),
            recipe["material_roles"][material])] += 1
    native_faces = Counter()
    for section in geometry["sections"]:
        slot = record["static_material_slots"][section["material_slot_index"]]
        material = slot["material"].rsplit(".",1)[-1]
        require(material.startswith("M_R_") and material.endswith("_UV"), "Recovered source material role is unavailable.")
        role = material[4:-3]
        indices = section["triangle_indices"]
        for start in range(0, len(indices), 3):
            points = tuple(mapping[tuple(section["vertices_cm"][i])] for i in indices[start:start+3])
            native_faces[(cyclic(points), role)] += 1
    require(source_faces == native_faces, "Recovered Native/source oriented faces or material partitions are not one-to-one.")
    return dict(passed=True, actual_binary_source_triangles=sum(source_faces.values()),
        actual_native_triangles=sum(native_faces.values()), position_welded_vertices=len(keys),
        missing_source_faces=0, unprescribed_native_faces=0, reversed_or_reassigned_faces=0,
        maximum_source_native_coordinate_error_cm=maximum, coordinate_matching_tolerance_cm=tolerance)


def verify_model_closure_import_repairs(build, inp, apply, applied, digest):
    """Replay the fixed 905-package result plus exactly 22 mesh/cache repairs."""
    directory = WORK / "BeforeNativeClosure"
    before = read(directory / "BuildReport.json")
    old = normalized(before["new_asset_sha256"])
    report = current_report("ModelClosureImportRepairs.json", digest)
    require(digest == MODEL_CLOSURE_MAP_SHA == sha(directory / MAP.name)
            and before.get("map_sha256") == digest and len(old) == 905
            and report == build.get("model_closure_import_repairs")
            and report.get("schema") == "OldTownRealismModelClosureImportRepairsV1"
            and report.get("source_map_sha256") == digest
            and Path(report.get("before_directory", "")).resolve() == directory.resolve()
            and report.get("changed_target_count") == report.get("added_import_cache_count") == 22
            and report.get("recovered_source_triangle_count") == 880
            and report.get("components_or_actors_changed") == 0
            and report.get("map_unchanged") is True
            and report.get("source_materials_textures_and_collision_preserved") is True,
            "Model-closure stage lacks its exact map, 905-package source or fixed 22/880 scope.")
    require(normalized(report["source_asset_sha256"]) == old == normalized(read(directory / "SourceAssetSHA256.json")),
            "Model-closure source asset manifest differs from its frozen 905-package Build.")
    current = hashes(build["new_asset_sha256"], "Post-closure generated packages")
    require(current == normalized(report["after_asset_sha256"]), "Model-closure after package hashes differ from Build.")
    fixed_files = {str((WORK / n).resolve()): sha(directory / n) for n in MODEL_CLOSURE_FROZEN_REPORTS}
    require(normalized(report["frozen_report_sha256"]) == fixed_files,
            "Model-closure frozen report list is incomplete or differs.")
    hashes(fixed_files, "Immutable appearance/source reports across ModelClosure")
    require(apply == read(directory / "RealismApply.json") and applied == read(directory / "Applied.json")
            and read(WORK / "ExpectedSnapshot.json") == read(directory / "ExpectedSnapshot.json"),
            "Model closure altered the Actor/component application or expected state.")
    diagnostic_path = directory / "NativeClosedSolidDiagnostic.json"
    diagnosis = read(diagnostic_path)
    require(diagnosis.get("map_sha256") == digest and diagnosis.get("count") == 143
            and len(diagnosis.get("rows", [])) == 143
            and len({r["asset"] for r in diagnosis["rows"]}) == 143
            and diagnosis.get("failed_count") == 22
            and Path(report["diagnostic_file"]).resolve() == (WORK / diagnostic_path.name).resolve()
            and report["diagnostic_sha256"] == sha(diagnostic_path) == sha(report["diagnostic_file"]),
            "Model closure does not bind the complete frozen 143-mesh/22-hole diagnosis.")
    diagnosed = {r["asset"]: r for r in diagnosis["rows"] if r["exact_odd_edges"]}
    rows = {r["asset"]: r for r in report.get("rows", [])}
    require(len(rows) == len(report.get("rows", [])) == len(diagnosed) == 22 and set(rows) == set(diagnosed),
            "Model closure omitted, duplicated or introduced an undiagnosed mesh.")
    face_diagnosis_path = directory / "NativeSourceFaceLossDiagnosis.json"
    face_diagnosis = read(face_diagnosis_path)
    require(Path(report["face_loss_diagnosis_file"]).resolve() == (WORK / face_diagnosis_path.name).resolve()
            and report["face_loss_diagnosis_sha256"] == sha(face_diagnosis_path) == sha(report["face_loss_diagnosis_file"])
            and face_diagnosis.get("passed") is True and face_diagnosis.get("total_missing_source_faces") == 880
            and face_diagnosis.get("all_surviving_native_faces_match_source") is True
            and {r["asset"] for r in face_diagnosis["rows"]} == set(rows),
            "Frozen binary-source face-loss diagnosis differs or is incomplete.")
    protected = {}
    for doc in (read(WORK / "RealismInput.json"), read(WORK / "RealismStreetInput.json")):
        for name in ("source_asset_file_sha256", "original_400_shared_asset_sha256", "protected_map_sha256"):
            protected.update(normalized(doc[name]))
    require(normalized(report["protected_source_file_sha256"]) == protected,
            "Model closure changed or omitted protected original files.")
    hashes(protected, "Protected source files across ModelClosure")
    source_files, manifests, targets, caches, prior_files = {}, {}, set(), set(), dict(fixed_files)
    face_proofs = {}
    native_backups = report.get("original_native_mesh_backups", {})
    require(len(native_backups) == 22, "Original Native geometry backup set is incomplete.")
    for original, backup in native_backups.items():
        path = Path(backup["backup_file"]).resolve()
        require(path.is_relative_to((directory / "NativeMeshes").resolve()) and sha(path) == backup["sha256"],
                "Historical Native mesh backup is absent, changed or outside the frozen directory.")
        require(face_diagnosis["input_sha256"].get(original) == backup["sha256"],
                "Historical Native mesh backup differs from the source face-loss proof.")
        prior_files[str(path)] = backup["sha256"]
    for category in ("Furniture", "Architecture", "Sanitary", "Street"):
        manifest_path = SOURCE_ART / category / "ModelDataManifest.json"
        manifest = read(manifest_path)
        source_files[str(manifest_path.resolve())] = sha(manifest_path)
        for variant in manifest["variants"]:
            asset = ASSET_ROOT + "Meshes/" + category + "/" + variant["mesh_name"] + "." + variant["mesh_name"]
            manifests[asset] = (category, variant)
        old_doc, new_doc = read(directory / (category+"AssetBuild.json")), read(WORK / (category+"AssetBuild.json"))
        expected_doc = deepcopy(old_doc)
        current_rows = {r["asset"]: r for r in new_doc["assets"]}
        require(len(current_rows) == len(new_doc["assets"]), "Duplicate repaired model/import manifest asset: " + category)
        for registered in expected_doc["assets"]:
            asset = registered["asset"]
            if asset in rows:
                row = rows[asset]
                registered.update(sha256=row["new_target_sha256"], triangles=row["new_native_triangles"])
                if "actual_local_bounds_cm" in registered:
                    published_bounds = current_rows[asset]["actual_local_bounds_cm"]
                    require(len(published_bounds) == 2 and all(near_vector(a, b, tolerance=1.e-12)
                        for a, b in zip(published_bounds, row["after_native"]["bounds_cm"])),
                        "Published model bounds differ from actual recovered Native positions: " + asset)
                    # GetBounds stores centre/extent, whose subtraction can cancel
                    # a 1e-15 cm extremum to zero; retain that bounded representation.
                    registered["actual_local_bounds_cm"] = published_bounds
        require(new_doc == expected_doc, "Model closure altered an unlisted model/import manifest field: " + category)
        prior_files[str(directory / (category+"AssetBuild.json"))] = sha(directory / (category+"AssetBuild.json"))
    for asset, row in rows.items():
        category, variant = manifests[asset]
        target = str(Path(row["new_target_file"]).resolve())
        backup = Path(row["before_target_backup_file"]).resolve()
        cache = Path(row["import_cache_file"]).resolve()
        require(row["category"] == category and row["key"] == variant["key"]
                and target == str(Path(row["before_target_file"]).resolve())
                and Path(target) == (GENERATED / "Meshes" / category / (variant["mesh_name"]+".uasset")).resolve()
                and backup == (directory / "Packages" / Path(target).relative_to(ROOT)).resolve()
                and old[target] == row["before_target_file_sha256"] == row["before_target_backup_sha256"] == sha(backup)
                and current[target] == row["new_target_sha256"] and current[target] != old[target]
                and cache.parent == (GENERATED / "Meshes/ImportData").resolve()
                and row["import_cache_asset"] == ASSET_ROOT+"Meshes/ImportData/"+cache.stem+"."+cache.stem
                and cache.stem == variant["mesh_name"]+"_Import_NativeClosureNoMerge_"+variant["source_file_sha256"][:12]
                and current[str(cache)] == row["import_cache_sha256"], "A repaired target/cache/backup identity differs: " + asset)
        targets.add(target); caches.add(str(cache)); prior_files[str(backup)] = sha(backup)
        fbx = Path(variant["fbx_file"])
        if not fbx.is_absolute(): fbx = SOURCE_ART / category / fbx
        recipe_path = Path(variant["geometry_recipe_file"])
        recipe = read(recipe_path)
        require(Path(row["source_fbx_file"]).resolve() == fbx.resolve()
                and row["source_fbx_sha256"] == sha(fbx) == variant["source_file_sha256"]
                and Path(row["source_recipe_file"]).resolve() == recipe_path.resolve()
                and row["source_recipe_sha256"] == sha(recipe_path) == variant["geometry_recipe_sha256"]
                and row["physical_scale"] == recipe["physical_scale"]
                and row["source_triangles"] == row["new_native_triangles"] == len(recipe["triangles"])
                and row["old_native_triangles"] == diagnosed[asset]["triangles"]
                and row["recovered_triangles"] == row["new_native_triangles"]-row["old_native_triangles"] > 0,
                "Recovered face counts or original FBX/recipe bindings differ: " + asset)
        source_files.update({str(fbx.resolve()): sha(fbx), str(recipe_path.resolve()): sha(recipe_path)})
        before_native, after_native = row["before_native"], row["after_native"]
        for record, base in ((before_native, directory / "Native"), (after_native, WORK / "NativeClosureAfter")):
            geometry_path = Path(record["geometry_file"]).resolve()
            require(record["asset"] == asset and Path(record["file"]).resolve() == Path(target)
                    and geometry_path.is_relative_to(base.resolve()) and sha(geometry_path) == record["geometry_sha256"],
                    "Native before/after record geometry identity differs: " + asset)
            prior_files[str(geometry_path)] = record["geometry_sha256"]
        old_geometry, new_geometry = read(before_native["geometry_file"]), read(after_native["geometry_file"])
        from AuditOldTownRealismAppearance import collision_signature
        require(before_native["sha256"] == old[target] and after_native["sha256"] == current[target]
                and before_native["geometry_sha256"] == diagnosed[asset]["geometry_sha256"]
                and before_native["static_material_slots"] == after_native["static_material_slots"]
                and collision_signature(before_native["collision_signature"]) == collision_signature(after_native["collision_signature"])
                and row["material_slots_preserved"] is True and row["bodysetup_signature_preserved"] is True
                and row["old_edge_proof"] == native_exact_edge_proof(old_geometry)
                and row["old_edge_proof"]["exact_odd_edges"] == diagnosed[asset]["exact_odd_edges"] > 0
                and row["native_closed_solid"] == native_closed_solid(new_geometry)
                and row["native_exact_edge_proof"] == native_exact_edge_proof(new_geometry)
                and row["native_exact_edge_proof"]["exact_odd_edges"] == 0
                and row["physical_uv"] == native_physical_uv(new_geometry, recipe["physical_scale"])
                and row["frames"] == native_frame_proof(new_geometry),
                "Actual source closure, Native buffers, slots, BodySetup, normals or UV proof differs: " + asset)
        native_frame_proof(old_geometry)
        face_proofs[asset] = native_binary_source_face_proof(new_geometry, after_native, recipe, fbx)
        require(before_native["triangle_count"] == row["old_native_triangles"]
                and after_native["triangle_count"] == row["new_native_triangles"]
                and row["native_closed_solid"]["triangles"] == row["new_native_triangles"]
                and row["frames"]["triangles"] == row["new_native_triangles"],
                "Native record triangle counts differ from recovered actual source faces: " + asset)
        bounds_change = max(abs(a-b) for aa,bb in zip(before_native["bounds_cm"], after_native["bounds_cm"]) for a,b in zip(aa,bb))
        require(row["maximum_bounds_change_cm"] == bounds_change < .03
                and row["native_source_model_read"] is True and row["native_no_degenerate_merge"] is True
                and isinstance(row["uv_chart_separation"], bool)
                and all(row[k] is False for k in ("fbx_remove_degenerates", "lod_remove_degenerates", "copy_remove_degenerates")),
                "Model import settings/envelope do not preserve valid small source faces: " + asset)
    require(len(targets) == len(caches) == 22 and not targets & caches and set(old) <= set(current)
            and {p for p in old if current[p] != old[p]} == targets and set(current)-set(old) == caches
            and len(current) == 927 and sum(r["recovered_triangles"] for r in rows.values()) == 880,
            "Model closure changed a package outside the exact 22 targets and 22 fresh caches.")
    require(normalized(report["source_fbx_and_recipe_sha256"]) == source_files,
            "Model closure changed or omitted its exact source FBX/recipe/manifest set.")
    hashes(source_files, "Unmodified original model source art across ModelClosure")
    replay = deepcopy(before); replay.update(new_asset_sha256=report["after_asset_sha256"], model_closure_import_repairs=report)
    require(build == replay, "Model closure altered an unlisted Build field.")
    material_before = read(directory / "MaterialBuild.json")
    material_expected = deepcopy(material_before)
    material_expected["final_compile_logs"].append(str(WORK / "NativeClosureImport.stdout.log"))
    require(read(WORK / "MaterialBuild.json") == material_expected,
            "Model closure changed original materials/textures or unlisted compile evidence.")
    prior_names = ("BuildReport.json", "MaterialBuild.json", "NativeClosedSolidDiagnostic.json", "NativeSourceFaceLossDiagnosis.json", "SourceAssetSHA256.json")
    prior_files.update({str(directory / name): sha(directory / name) for name in prior_names})
    prior_files[str(directory / MAP.name)] = sha(directory / MAP.name)
    return dict(passed=True, changed_model_count=22, recovered_source_faces=880,
        new_import_cache_count=22, unchanged_original_packages=883, source_map_sha256=digest, current_map_sha256=digest,
        actual_binary_source_face_bijections=face_proofs,
        actor_states_and_source_materials_unchanged=True, file=str(WORK / "ModelClosureImportRepairs.json"),
        sha256=sha(WORK / "ModelClosureImportRepairs.json"), prior_and_diagnostic_file_sha256=prior_files)


def verify_appearance_stage_chain(build, inp, apply, applied, digest):
    directory = WORK / "BeforeNativeClosure"
    historical = verify_followup_surface_repairs(read(directory / "BuildReport.json"), inp,
        read(directory / "RealismApply.json"), read(directory / "Applied.json"), digest)
    closure = verify_model_closure_import_repairs(build, inp, apply, applied, digest)
    return (*historical, closure)


def appearance_preservation(build, inp, apply, after, appearance, repairs, followup_repairs):
    before_document = read(inp["baseline_snapshot_file"])
    before = before_document["actors"]
    expected = deepcopy(before)
    old_components, destination = component_index(before), component_index(expected)
    hotel = set(inp["hotel_actor_labels"])
    require(len(before) == inp.get("actor_count") == build.get("actor_count") == COUNTS["actors"]
            and len(hotel) == len(inp["hotel_actor_labels"]) == COUNTS["hotel"] and hotel <= set(before),
            "The accepted 8014/2975 Actor set differs.")
    require(len(set(before) - hotel) == COUNTS["outside"], "The 5039 outside-hotel Actor set differs.")
    rows = next((apply[k] for k in ("components", "changes", "overrides", "applied_components")
                 if isinstance(apply.get(k), list)), None)
    require(rows and apply.get("appearance_only") is True and apply.get("scope") == "whole_map",
            "Missing whole-map appearance-only component manifest.")
    seen = set()
    for row in rows:
        ident = row["actor"] + "::" + row["component"]
        require(ident == row["id"] and ident not in seen and row["actor"] in before and ident in old_components,
                "Duplicate or unknown appearance override: " + ident)
        seen.add(ident)
        original = old_components[ident]
        require(original.get("visible") is True and original.get("hidden_in_game") is False
                and original.get("mesh") == row["source_mesh"] and original.get("materials") == row["before_materials"],
                "Appearance source/visibility differs: " + ident)
        require(row["target_mesh"] == row["source_mesh"] or row["target_mesh"].startswith(ASSET_ROOT + "Meshes/"),
                "Replacement mesh is outside this owned stage: " + ident)
        require(row["after_materials"] and all(m and m.startswith(ASSET_ROOT + "Materials/") for m in row["after_materials"]),
                "Replacement material is missing or outside this owned stage: " + ident)
        offset = row["expected_offset_cm"]
        require(len(offset) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in offset),
                "Invalid appearance WPO offset: " + ident)
        native_original = next(c for c in inp["component_records"][row["actor"]] if c["name"] == row["component"])
        original_offset = native_original["expected_surface_translation_cm_to_preserve"]
        permitted_offset = (followup_repairs[ident]["expected_offset_cm"] if ident in followup_repairs else
                            repairs[ident]["expected_offset_cm"] if ident in repairs else original_offset)
        require(near_vector(offset, permitted_offset), "Unlisted render offset or missing original WPO: " + ident)
        destination[ident]["mesh"] = row["target_mesh"]
        destination[ident]["materials"] = row["after_materials"]
    actual = after["actors"]
    require(actual == expected == read(WORK / "ExpectedSnapshot.json")["actors"],
            "Saved Actor identities, parent, pose, collision or unlisted properties differ.")
    native_after = read(WORK / "AppearanceSnapshot.json")
    require(native_after.get("map_sha256") == build["map_sha256"] and native_after["actors"] == expected
            and native_after.get("source") == "fresh_persisted_native_read_only", "Native fresh Actor snapshot differs.")
    require(after.get("passed") is True and after.get("target_level") == TARGET
            and after.get("source_map_sha256", after.get("map_sha256")) == build["map_sha256"], "AfterSnapshot is stale.")
    outside = set(before) - hotel
    require(all(actual[n] == expected[n] for n in outside), "A street Actor changed outside its declared appearance fields.")
    hidden_sanitary = [i for i, c in old_components.items() if i.split("::")[0] in hotel and
        "_Collision" in i.split("::")[0] and c.get("visible") is False]
    hidden_openings = [i for i, c in old_components.items() if i.split("::")[0] in hotel and c.get("visible") is False
        and c["name"] in ("LeafCollision", "LeftLeafCollision", "RightLeafCollision", "LeftPaneCollision", "RightPaneCollision")]
    now = component_index(actual)
    require(len(hidden_sanitary) == 87 and all(now[i] == old_components[i] for i in hidden_sanitary),
            "An independent sanitary collider changed.")
    require(len(hidden_openings) == 276 and len({i.split("::")[0] for i in hidden_openings}) == 169
            and all(now[i] == old_components[i] for i in hidden_openings), "A door/window hidden collider changed.")
    main = before_document["main_home"]
    require(main.get("interaction_preserved") is True and after.get("main_home") == main
            and actual[main["actor"]] == before[main["actor"]], "MainHome structure or interaction evidence changed.")
    require(build.get("hotel_v4") == build.get("hotel_architecture") == read(WORK / "ArchitecturePlan.json"),
            "The current architecture plan differs from the saved BuildReport.")
    source_plan = read(SOURCE / "BuildReport.json")["hotel_v4"]
    for field in ("floor_z_cm", "rooms", "shell_bounds"):
        if field in source_plan:
            require(build["hotel_v4"].get(field) == source_plan[field], "Hotel layout changed: " + field)
    changed_actors = {row["actor"] for row in rows}
    changed_street = changed_actors & outside
    require(apply.get("changed_component_count", len(rows)) == len(rows)
            and apply.get("changed_actor_count", len(changed_actors)) == len(changed_actors)
            and apply.get("changed_street_actor_count") == len(changed_street), "Applied whole-map appearance counts differ.")
    source_components = {n + "::" + c["name"]: c for n, components in inp["component_records"].items() for c in components}
    wpo = {i for i, c in source_components.items() if any(abs(v) > 1.e-8
        for m in c.get("materials", []) for v in m.get("effective_surface_translation_cm", [0, 0, 0]))}
    hotel_wpo = {i for i in wpo if i.split("::")[0] in hotel}
    actual_wpo = {n + "::" + c["name"] for n, components in native_after["component_records"].items() for c in components
        if any(abs(v) > 1.e-8 for m in c.get("materials", []) for v in m.get("effective_surface_translation_cm", [0, 0, 0]))}
    added_wpo = {i for i, spec in repairs.items() if i not in wpo and any(abs(v) > 1.e-8 for v in spec["expected_offset_cm"])}
    require(len(added_wpo) == 48 and actual_wpo == wpo | added_wpo,
            "Current effective WPO lost an original component or gained an unprescribed component.")
    required_checks = {"fresh_persisted_map_load", "all_8014_actor_identities_preserved",
        "all_actor_component_parent_pose_collision_and_allowed_appearance_exact", "outside_hotel_5039_actors_exact",
        "all_87_hidden_sanitary_colliders_exact", "all_169_opening_actors_276_hidden_colliders_exact",
        "mainhome_structure_and_components_exact", "native_parent_relative_world_pose_bodyinstance_collisionflags_exact",
        "all_1061_original_wpo_components_identified", "effective_wpo_preserved_on_every_old_component_and_new_slot",
        "strict_51_additive_render_contact_repairs", "all_3297_current_wpo_components_identified",
        "no_default_gray_or_unregistered_replacement_materials", "completed_material_compile_logs_supplied",
        "wall_and_floor_concrete_materials_separated",
        "strict_1_followup_additive_render_contact_repair", "full_8684_appearance_stage_chain_replayed",
        "strict_22_model_closure_import_stage", "all_143_actual_native_meshes_closed",
        "all_native_read_asset_files_unchanged_during_audit", "map_unchanged_during_read_only_audit"}
    require(required_checks <= {c["name"] for c in appearance["checks"]}, "Native appearance audit omitted required preservation/PBR checks.")
    stats = appearance["statistics"]
    require(stats.get("actors") == 8014 and stats.get("outside_hotel") == 5039 and stats.get("original_wpo_components") == 1061
            and len(hotel_wpo) == 1061 and stats.get("whole_map_original_wpo_components") == len(wpo)
            and len(wpo) == 3249 and stats.get("current_whole_map_wpo_components") == len(actual_wpo) == 3297
            and stats.get("additional_surface_contact_repairs") == len(repairs) == 51
            and stats.get("followup_surface_contact_repairs") == len(followup_repairs) == 1
            and stats.get("model_closure_import_repairs") == 22 and stats.get("native_closed_meshes") == 143
            and stats.get("changed_components") == len(rows) and stats.get("inspected_native_components") == len(source_components)
            and stats.get("hidden_sanitary_colliders") == 87 and stats.get("hidden_opening_colliders") == 276
            and stats.get("grounded_furniture") == 104, "Native appearance coverage/counts differ.")
    return rows, dict(passed=True, original_actors=8014, current_actors=8014, hotel_actors=2975,
        outside_hotel_actors_only_declared_appearance=5039, hidden_sanitary_colliders_exact=87,
        opening_actor_instances=169, hidden_opening_collision_components_exact=276,
        original_hotel_wpo_components_preserved=len(hotel_wpo), original_street_wpo_components_preserved=len(wpo - hotel_wpo),
        original_whole_map_wpo_components_preserved=len(wpo), grounded_bed_and_seat_bases=104,
        added_contact_wpo_components=len(added_wpo), current_effective_wpo_components=len(actual_wpo),
        changed_components=len(rows), changed_actors=len(changed_actors),
        changed_street_actors=len(changed_street), unchanged_actors=8014 - len(changed_actors), scope="whole_map",
        MainHome_interaction_structure_preserved=True, all_unlisted_actor_properties_exact=True)


def verify_models(build, rows, appearance, new_root):
    used = {r["target_mesh"] for r in rows if r["target_mesh"] != r["source_mesh"]}
    imported = set()
    source_files, recipe_files, categories = {}, {}, {}
    changes = {r["id"]: r for r in rows}
    names = {c["name"] for c in appearance["checks"]}
    for category in ("Furniture", "Architecture", "Sanitary", "Street"):
        manifest_file = SOURCE_ART / category / "ModelDataManifest.json"
        manifest = read(manifest_file)
        report = read(WORK / (category + "AssetBuild.json"))
        require(manifest.get("status") in ("COMPLETE", "PASS") and report.get("passed") is True
                and report.get("manifest_sha256") == sha(manifest_file), category + " source/import manifest failed or changed.")
        variants = {v["key"]: v for v in manifest["variants"]}
        assets = {v["key"]: v for v in report["assets"]}
        require(len(variants) == len(manifest["variants"]) == len(assets) == len(report["assets"])
                and set(variants) == set(assets) and len(variants) == COUNTS[category.lower() + "_variants"]
                and manifest.get("variant_count") == len(variants), category + " variants are duplicated or missing.")
        if "source_map_sha256" in manifest:
            require(manifest["source_map_sha256"] == SOURCE_SHA, category + " model manifest starts from another map.")
        for file_field, sha_field in (("source_native_inventory_file", "source_native_inventory_sha256"),
                                     ("source_input_file", "source_input_sha256")):
            if manifest.get(file_field):
                require(Path(manifest[file_field]).resolve().is_relative_to(WORK.resolve())
                        and sha(manifest[file_field]) == manifest.get(sha_field), category + " model input evidence changed.")
                recipe_files[str(Path(manifest[file_field]).resolve())] = manifest[sha_field]
        actor_set, component_set = set(), set()
        for key, variant in variants.items():
            asset = assets[key]
            file = Path(asset["file"]).resolve()
            fbx = Path(asset["fbx_source"]).resolve()
            require(file.is_relative_to(GENERATED.resolve()) and new_root.get(str(file)) == asset["sha256"],
                    "Imported package is not in the current root manifest: " + key)
            require(fbx.is_relative_to((SOURCE_ART / category).resolve()) and fbx.is_file()
                    and sha(fbx) == asset["fbx_sha256"] == variant.get("source_file_sha256", variant.get("fbx_sha256")),
                    "Imported FBX differs from its frozen source: " + key)
            require(asset["asset"].startswith(ASSET_ROOT + "Meshes/" + category + "/") and asset["asset"] in used,
                    "Detailed asset is outside the stage or not actually applied: " + key)
            require(asset["asset"] not in imported, "Duplicate imported mesh package: " + key)
            imported.add(asset["asset"])
            source_files[str(fbx)] = sha(fbx)
            actor_set.update(variant.get("source_actor_labels", []))
            assignments = variant.get("components", variant.get("component_assignments"))
            if assignments is None:
                assignments = [dict(actor=n, component=variant.get("component_name", "StaticMeshComponent0"))
                               for n in variant.get("source_actor_labels", [])]
            require(assignments and len(assignments) == len({a["actor"] + "::" + a["component"] for a in assignments}),
                    "Duplicated/missing model component assignments: " + key)
            assigned_actors = {a["actor"] for a in assignments}
            require(assigned_actors == set(variant.get("source_actor_labels", [])), "Model Actor and component assignments disagree: " + key)
            for assignment in assignments:
                ident = assignment["actor"] + "::" + assignment["component"]
                require(ident not in component_set and ident in changes and changes[ident]["category"] == category
                        and changes[ident]["target_mesh"] == asset["asset"], "Model-to-instance assignment is incomplete or wrong: " + ident)
                component_set.add(ident)
            for file_field, sha_field in (("geometry_recipe_file", "geometry_recipe_sha256"),
                                         ("source_native_geometry_file", "source_native_geometry_sha256")):
                if variant.get(file_field):
                    require(sha(variant[file_field]) == variant.get(sha_field), "Source model recipe/native geometry changed: " + key)
                    recipe_files[str(Path(variant[file_field]).resolve())] = variant[sha_field]
            if variant.get("source_file") and variant.get("source_sha256"):
                require(sha(variant["source_file"]) == variant["source_sha256"], "Original model source package changed: " + key)
                recipe_files[str(Path(variant["source_file"]).resolve())] = variant["source_sha256"]
            native = appearance.get("meshes", {}).get(asset["asset"], {})
            require(native.get("sha256") == asset["sha256"] and native.get("triangle_count", 0) > 12
                    and native.get("uv_channel_count", 0) >= 1, "Actual native LOD/UV/hash evidence missing: " + key)
            require(native.get("geometry_file") and sha(native["geometry_file"]) == native.get("geometry_sha256"),
                    "Actual native render-buffer export changed: " + key)
            recipe_files[str(Path(native["geometry_file"]).resolve())] = native["geometry_sha256"]
            require(len(native.get("bounds_cm", [])) == 2 and all(abs(float(a) - float(b)) <= .03
                    for aa, bb in zip(native["bounds_cm"], variant["local_bounds_cm"]) for a, b in zip(aa, bb)),
                    "Actual imported model left its authored local envelope: " + key)
            require(sorted(asset["material_roles"]) == sorted(variant["material_roles"]), "Imported model role set changed: " + key)
            required = {"clone_bodysetup_exact:", "actual_render_triangles_exceed_old_cube:",
                        "actual_normals_tangents_uv0_valid:", "actual_imported_material_role_slots:", "actual_closed_native_solid:"}
            require(all(prefix + asset["asset"] in names for prefix in required), "Native mesh/collision checks missing: " + key)
            require(all("material_partition_reference:" + asset["asset"] + ":" + str(s["section_index"]) in names
                        for s in native["sections"]), "Native material partition checks missing: " + key)
            if category == "Furniture":
                require("furniture_actual_physical_uv_cm:" + asset["asset"] in names
                        and "furniture_actual_local_bounds_003cm:" + asset["asset"] in names,
                        "Furniture physical UV/envelope checks are absent: " + key)
        require(component_set == {r["id"] for r in rows if r.get("category") == category},
                category + " model overrides do not cover their exact component source set.")
        if "component_count" in manifest:
            require(manifest["component_count"] == len(component_set), category + " model component count differs.")
        if category == "Furniture":
            require(len(variants) == 33 and len(actor_set) == manifest.get("actor_count") == 680,
                    "The 33 detailed furniture variants/680 Actor coverage differs.")
            require({r["actor"] for r in rows if r.get("category") == category} == actor_set,
                    "Furniture instance overrides do not cover the exact source set.")
        elif category == "Sanitary":
            require(len(variants) == 4 and len(actor_set) == manifest.get("actor_count") == 114,
                    "The 4 sanitary models/114 Actor coverage differs.")
            require({r["actor"] for r in rows if r.get("category") == category} == actor_set,
                    "Sanitary instance overrides do not cover the exact source set.")
        else:
            require(bool(variants) and any(r.get("category") == category for r in rows), "Detailed opening/stair models are absent.")
        recipe_files[str(manifest_file.resolve())] = sha(manifest_file)
        blend = manifest.get("source_blend_file", manifest.get("blend_file"))
        blend_sha = manifest.get("source_blend_sha256", manifest.get("blend_sha256"))
        if blend and blend_sha:
            require(Path(blend).resolve().is_relative_to(SOURCE_ART.resolve()) and sha(blend) == blend_sha,
                    "Source blend differs: " + category)
            recipe_files[str(Path(blend).resolve())] = blend_sha
        categories[category] = dict(variants=len(variants), source_actors=len(actor_set),
            applied_components=len(component_set),
            source_manifest=str(manifest_file), source_manifest_sha256=sha(manifest_file), actual_native_meshes=len(assets))
    require(imported == used == set(appearance.get("meshes", {}))
            and appearance.get("statistics", {}).get("imported_meshes") == len(imported),
            "Applied/native replacement mesh set differs from the four imported model reports.")
    actual_fbx = {str(p.resolve()): sha(p) for p in sorted(SOURCE_ART.rglob("*.fbx"))}
    require(actual_fbx and all(actual_fbx.get(p) == h for p, h in source_files.items()), "Source FBX set differs.")
    require(normalized(appearance.get("source_fbx_sha256", {})) == actual_fbx, "Native appearance audit used different source FBX files.")
    axis = read(WORK / "AxisVerification.json")
    require(axis.get("error_cm", 1) < .005 and len(axis.get("import_order", [])) == 3
            and sorted(axis["import_order"]) == [0, 1, 2] and all(s in (-1, 1) for s in axis.get("import_signs", []))
            and len(axis.get("import_signs", [])) == 3, "Asymmetric FBX axis verification failed.")
    return dict(passed=True, categories=categories, actual_native_imported_meshes=len(imported)), actual_fbx, recipe_files


def native_closed_solid(geometry):
    """Check closure in actual persisted render positions across UV/slot seams.

    A split render vertex is welded by its measured cm coordinate. Even edge
    incidence permits several closed solids to meet on a common edge; it does
    not pretend an arbitrary AABB is an occupied solid.
    """
    edges, degenerate, volume6, triangles = Counter(), 0, 0., 0
    for section in geometry["sections"]:
        vertices, indices = section["vertices_cm"], section["triangle_indices"]
        require(len(indices) % 3 == 0 and all(isinstance(i, int) and 0 <= i < len(vertices) for i in indices),
                "Actual native render geometry has invalid triangle indices.")
        for start in range(0, len(indices), 3):
            points = [vertices[i] for i in indices[start:start + 3]]
            require(len(points) == 3 and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in points),
                    "Actual native render geometry contains an invalid triangle/position.")
            keys = [tuple(round(float(v), 6) for v in p) for p in points]
            degenerate += len(set(keys)) != 3
            a, b, c = points
            ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            area4 = sum(v * v for v in (ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]))
            degenerate += not math.isfinite(area4) or area4 <= 1.e-20
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edges[tuple(sorted((keys[a], keys[b])))] += 1
            a, b, c = points
            volume6 += a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])
            triangles += 1
    odd = sum(n % 2 != 0 for n in edges.values())
    require(triangles > 12 and odd == 0 and degenerate == 0 and math.isfinite(volume6) and abs(volume6) > .00000001,
            "Actual native render mesh is open, degenerate, or has no finite closed volume.")
    return dict(passed=True, triangles=triangles, odd_boundary_edges=odd,
        welded_degenerate_triangles=degenerate, absolute_signed_local_volume_cm3=abs(volume6) / 6,
        coordinate_weld_precision_cm=.000001)


def native_physical_uv(geometry, scale, tolerance=.0005):
    require(len(scale) == 3 and all(math.isfinite(v) and v != 0 for v in scale), "Invalid source physical scale.")
    count, maximum_error = 0, 0.
    for section in geometry["sections"]:
        points, uv, indices = section["vertices_cm"], section["uv0"], section["triangle_indices"]
        require(len(uv) == len(points) and all(len(v) == 2 and all(math.isfinite(c) for c in v) for v in uv),
                "Actual native UV channel contains missing or nonfinite coordinates.")
        for start in range(0, len(indices), 3):
            ids = indices[start:start + 3]
            errors = []
            for axes in ((0, 1), (0, 2), (1, 2)):
                errors.append(max(max(
                    abs((uv[i][0] - uv[j][0]) - (points[i][axes[0]] - points[j][axes[0]]) * scale[axes[0]] / 100),
                    abs((uv[i][1] - uv[j][1]) + (points[i][axes[1]] - points[j][axes[1]]) * scale[axes[1]] / 100))
                    for i, j in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0]))))
            error = min(errors)
            require(math.isfinite(error) and error <= tolerance, "Actual native UV edges do not represent physical cm/100.")
            maximum_error = max(maximum_error, error)
            count += 1
    require(count > 12, "Native physical UV proof has insufficient render triangles.")
    return dict(passed=True, actual_native_triangles=count, maximum_error_uv=maximum_error,
        tolerance_uv=tolerance, convention="One UV unit per metre; translated islands allowed; UE FBX V=1-V")


def verify_source_solids(appearance, models, inp):
    report = read(WORK / "SourceSolidsRepair.json")
    count = models["actual_native_imported_meshes"]
    require(report.get("passed") is True and not report.get("errors") and report.get("target_variant_count") == count
            and report.get("repaired_variant_count") == count and report.get("all_uv_degenerate_triangle_counts_zero") is True
            and report.get("all_topology_closed") is True and report.get("material_slots_preserved") is True,
            "Source solid/UV repair is incomplete or failed; an in-progress report cannot pass.")
    diagnostic = Path(report["diagnostic_file"]).resolve()
    require(diagnostic.is_relative_to((WORK / "BeforePrecisionEvidence").resolve()) and sha(diagnostic) == report["diagnostic_sha256"],
            "Source solid repair used another contact diagnosis.")
    repair_script = ROOT / "Scripts/RepairOldTownRealismSolidsBlender.py"
    require(sha(repair_script) == report.get("source_script_sha256"), "Source solid repair script changed after the final repair.")
    variants = {(r["category"], r["key"]): r for r in report["variants"]}
    diagnosis = read(diagnostic)
    diagnosed_names = {m["mesh"].rsplit(".", 1)[-1] for row in diagnosis["overlaps"]
        if row["intra_component"] and not row.get("buried") and row.get("exposed_area_cm2", 0) > 0
        for m in row["component_metadata"]}
    union_names = {r["mesh_name"] for r in variants.values() if r.get("exact_union") is True}
    require(len(variants) == len(report["variants"]) == count and len(union_names)
            == report.get("exact_union_variant_count") == 30 and len(diagnosed_names)
            == report.get("diagnosed_unique_mesh_count") == report.get("diagnosed_exact_union_variant_count") == 24
            and diagnosed_names <= union_names and len(union_names - diagnosed_names)
            == report.get("source_shared_edge_exact_union_variant_count") == 6
            and all(r["category"] == "Street" for r in variants.values() if r["mesh_name"] in union_names - diagnosed_names),
            "Source solid repair omitted/duplicated a model or changed diagnosed-union coverage.")
    files = {str(diagnostic): sha(diagnostic), str(repair_script.resolve()): report["source_script_sha256"]}
    native_proofs = {}
    source_components = {n + "::" + c["name"]: c for n, components in inp["component_records"].items() for c in components}
    for category, summary in models["categories"].items():
        declaration = report.get("categories", {}).get(category, {})
        manifest = read(SOURCE_ART / category / "ModelDataManifest.json")
        require(Path(declaration.get("manifest_file", "")).resolve() == (SOURCE_ART / category / "ModelDataManifest.json").resolve()
                and declaration.get("manifest_sha256") == sha(declaration["manifest_file"])
                and declaration.get("variant_count") == summary["variants"], "Source solid category manifest is stale: " + category)
        require(Path(declaration.get("blend_file", "")).resolve() == Path(manifest.get("blend_file", manifest.get("source_blend_file", ""))).resolve()
                and declaration.get("blend_sha256") == manifest.get("blend_sha256", manifest.get("source_blend_sha256"))
                and sha(declaration["blend_file"]) == declaration["blend_sha256"], "Source solid category blend is stale: " + category)
        for item in manifest["variants"]:
            repaired = variants.get((category, item["key"]), {})
            topology = repaired.get("final_physical_topology", {})
            require(repaired.get("passed") is True and topology.get("nonmanifold_edges") == topology.get("degenerate_faces") == 0
                    and topology.get("signed_volume_cm3", 0) > 0 and repaired.get("uv_degenerate_triangle_count") == 0
                    and repaired.get("invalid_tangent_count") == 0 and repaired.get("minimum_uv_area2", 0) >= 1.e-12
                    and repaired.get("material_slot_order_unchanged") is True and repaired.get("material_roles") == item["material_roles"]
                    and 0 <= repaired.get("maximum_bounds_change_cm", 1) < .005,
                    "Source repair lacks the original envelope/roles or closed physical UV geometry: " + item["key"])
            require(repaired.get("fbx_sha256") == item.get("source_file_sha256", item.get("fbx_sha256"))
                    and sha(repaired["fbx_file"]) == repaired["fbx_sha256"]
                    and repaired.get("geometry_recipe_sha256") == item.get("geometry_recipe_sha256")
                    and sha(repaired["geometry_recipe_file"]) == repaired["geometry_recipe_sha256"],
                    "Source repair mesh/recipe is not the current frozen source: " + item["key"])
            asset = ASSET_ROOT + "Meshes/" + category + "/" + item["mesh_name"] + "." + item["mesh_name"]
            record = appearance["meshes"][asset]
            actual = read(record["geometry_file"])
            recipe = read(repaired["geometry_recipe_file"])
            assignments = item.get("components", item.get("component_assignments"))
            if assignments is None:
                assignments = [dict(actor=n, component=item.get("component_name", "StaticMeshComponent0"))
                    for n in item["source_actor_labels"]]
            original_scales = [[abs(v) for v in source_components[a["actor"] + "::" + a["component"]]["world_pose"]["scale"]]
                for a in assignments]
            if category == "Sanitary":
                # Sanitary sources are authored directly in physical local cm,
                # shared by the original differently scaled basin instances.
                # Their Actor scales remain protected by the native audit.
                require(near_vector(recipe["physical_scale"], [1., 1., 1.]), "Sanitary local cm UV basis changed: " + item["key"])
            else:
                require(all(near_vector(recipe["physical_scale"], scale, .00002) for scale in original_scales),
                    "Physical UV scale differs from the original native instance scale: " + item["key"])
            native_proofs[asset] = native_closed_solid(actual)
            native_proofs[asset]["physical_uv"] = native_physical_uv(actual, recipe["physical_scale"])
            native_proofs[asset]["physical_uv"]["physical_basis"] = ("Original sanitary asset local cm; original instance scales retained"
                if category == "Sanitary" else "Original native component world scale")
            files[str(Path(repaired["geometry_recipe_file"]).resolve())] = repaired["geometry_recipe_sha256"]
    return dict(passed=True, file=str(WORK / "SourceSolidsRepair.json"), sha256=sha(WORK / "SourceSolidsRepair.json"),
        variant_count=count, exact_union_variants=report["exact_union_variant_count"], all_physical_uv_valid=True,
        diagnosed_exact_union_variants=24, source_shared_edge_exact_union_variants=6,
        all_source_topology_closed=True, actual_native_closed_solid_proofs=native_proofs,
        preserved_envelopes_and_material_roles=True), files


def verify_independent_source_solids(models):
    path = WORK / "SourceSolidsIndependentAudit.json"
    report = read(path)
    require(report.get("schema") == "OldTownRealismIndependentSerializedSourceAuditV1"
            and report.get("passed") is True and report.get("repair_final") is True and not report.get("errors")
            and report.get("target_count") == report.get("audited_variant_count") == models["actual_native_imported_meshes"]
            and report.get("completed_utc") and Path(report.get("repair_file", "")).resolve() == (WORK / "SourceSolidsRepair.json").resolve()
            and report.get("repair_sha256") == sha(WORK / "SourceSolidsRepair.json"),
            "Independent serialized-source audit is incomplete, failed, or binds another source repair.")
    script = Path(report["audit_script_file"]).resolve()
    require(script == (ROOT / "Scripts/ValidateOldTownRealismSourceSolids.py").resolve()
            and sha(script) == report["audit_script_sha256"], "Independent source audit script changed.")
    files = {str(script): report["audit_script_sha256"]}
    variants = {(r["category"], r["key"]): r for r in report["variants"]}
    require(len(variants) == len(report["variants"]) == models["actual_native_imported_meshes"],
            "Independent source audit omits or duplicates a model.")
    for category, summary in models["categories"].items():
        declaration = report.get("categories", {}).get(category, {})
        manifest_file = SOURCE_ART / category / "ModelDataManifest.json"
        manifest = read(manifest_file)
        original_file = SOURCE_ART / category / "BeforeSolids/ModelDataManifest.json.bak"
        require(declaration.get("variant_count") == declaration.get("expected_variant_count") == summary["variants"]
                and Path(declaration.get("manifest_file", "")).resolve() == manifest_file.resolve()
                and declaration.get("manifest_sha256") == sha(manifest_file)
                and Path(declaration.get("original_manifest_file", "")).resolve() == original_file.resolve()
                and declaration.get("original_manifest_sha256") == sha(original_file),
                "Independent source category/original manifest is stale: " + category)
        require(Path(declaration.get("blend_file", "")).resolve() == Path(manifest.get("blend_file", manifest.get("source_blend_file", ""))).resolve()
                and declaration.get("blend_sha256") == sha(declaration["blend_file"]),
                "Independent source blend is stale: " + category)
        files[str(original_file.resolve())] = declaration["original_manifest_sha256"]
        old_variants = {v["key"]: v for v in read(original_file)["variants"]}
        for item in manifest["variants"]:
            row = variants.get((category, item["key"]), {})
            require(row.get("passed") is True and not row.get("errors") and row.get("mesh_name") == item["mesh_name"]
                    and row.get("original_role_order_verified") is True and row.get("material_role_slot_order") == item["material_roles"]
                    and 0 <= row.get("maximum_local_envelope_change_cm", 1) < .005,
                    "Independent binary source role/envelope proof failed: " + item["key"])
            require(row.get("fbx_sha256") == item.get("source_file_sha256", item.get("fbx_sha256"))
                    and sha(row["fbx_file"]) == row["fbx_sha256"] and row.get("recipe_sha256") == item["geometry_recipe_sha256"]
                    and sha(row["recipe_file"]) == row["recipe_sha256"], "Independent binary FBX/recipe binding is stale: " + item["key"])
            for name in ("recipe", "fbx", "float32_centimetre"):
                evidence = row.get(name, {})
                require(evidence.get("passed") is True and not evidence.get("issue_counts")
                        and evidence.get("triangles", 0) > 12 and evidence.get("minimum_uv_area2", 0) >= 1.e-12
                        and evidence.get("native_uv_zero_threshold") == 1.e-12
                        and evidence.get("minimum_corner_normal_geometric_facing", -1) > 0
                        and evidence.get("maximum_physical_uv_projected_edge_error", 1) <= .000002
                        and evidence.get("connected_shell_count") == len(evidence.get("signed_shell_volumes_cm3", [])) > 0
                        and all(math.isfinite(v) and v > 0 for v in evidence["signed_shell_volumes_cm3"]),
                        "Independent actual serialized topology/normal/UV/frame proof failed: " + item["key"] + " " + name)
            original_fbx = SOURCE_ART / category / "BeforeSolids" / (Path(row["fbx_file"]).name + ".bak")
            old = old_variants[item["key"]]
            original_sha = old.get("source_file_sha256", old.get("fbx_sha256"))
            require(original_sha and sha(original_fbx) == original_sha, "Original binary FBX backup changed: " + item["key"])
            files[str(original_fbx.resolve())] = original_sha
    return dict(passed=True, file=str(path), sha256=sha(path), audited_variant_count=len(variants),
        independent_actual_binary_fbx_and_recipe_geometry=True, immutable_original_source_files=len(files) - 1), files


def verify_geometry(digest, new_root):
    path = WORK / "GeometryAfter.json"
    geometry, summary = read(path), current_report("AfterSummary.json", digest)
    require(geometry.get("coordinate_serialization") ==
            "unrounded native local positions and unrounded native transformed world positions, plus verified material WPO",
            "Render export rounded native coordinates and may collapse valid small faces.")
    require(geometry.get("map_sha256") == digest and not geometry.get("errors")
            and summary.get("actors") == 8014 and summary.get("visible_components") == len(geometry["components"])
            and summary.get("triangles") == geometry.get("triangles") and summary.get("unique_meshes") == geometry.get("unique_meshes"),
            "Whole-map saved render export/summary differs.")
    bound_g = asset_binding(geometry, new_root, "GeometryAfter", required=False)
    bound_s = asset_binding(summary, new_root, "AfterSummary", required=False)
    require(bound_g or bound_s, "The render export/summary lacks a current native asset binding.")
    components = geometry["components"]
    require(len({c["id"] for c in components}) == len(components), "Duplicate visible render component IDs.")
    require(sum(len(c["triangles"]) for c in components) == geometry["triangles"], "Actual triangle arrays differ from the whole-map count.")
    require(len({c["mesh"] for c in components}) == geometry["unique_meshes"], "Unique render-mesh arrays differ.")
    require(all(not any(abs(v) > 1.e-8 for v in c.get("render_offset_cm", [0, 0, 0]))
                or c.get("wpo_verified_from_persisted_material") is True for c in components),
            "Nonzero WPO geometry was not verified against persisted materials.")
    return geometry, summary, sha(path)


def close(a, b, tolerance=1.e-6):
    return math.isclose(float(a), float(b), abs_tol=tolerance, rel_tol=1.e-7)


def overlap_identity(row):
    fields = ("components", "component_metadata", "intra_component", "normal", "plane_cm",
        "projection_axis", "area_cm2", "face_pair_count", "max_plane_gap_cm", "face_pair_samples",
        "face_indices_by_component", "overlap_bounds_cm")
    require(all(k in row for k in fields), "An overlap group lacks its complete raw face identity.")
    return json.dumps({k: row[k] for k in fields}, sort_keys=True, separators=(",", ":"))


def third_box_proof(row, records, by_id, normal_tolerance, plane_tolerance, minimum_area, occlusion=None):
    """Recompute every raw buried polygon against actual third solid cubes.

    These pure helpers do not start an editor. They annotate only verified
    Engine Cube geometry, never arbitrary furniture/fixture AABBs as solids.
    """
    from OldTownCoplanarScan import (box_faces, _face, _dot, _project, _world_point,
        _signed_area, polygon_intersection, _BoxOcclusion)
    owners = [by_id[i] for i in row["components"]]
    declared = row.get("buried_by", [])
    require(declared and all(i in by_id and i not in row["components"] and records[by_id[i]].get("kind") == "box"
                           for i in declared), "Raw buried group lacks valid third solid cube references.")
    faces = []
    for owner, ident in zip(owners, row["components"]):
        rec = records[owner]
        triangles = box_faces(rec["bounds_cm"]) if rec.get("kind") == "box" else rec["triangles"]
        items = []
        for index in row["face_indices_by_component"][ident]:
            require(0 <= index < len(triangles), "Buried proof references an absent face.")
            points = triangles[index] if rec.get("kind") == "box" else [rec["vertices"][int(i)] for i in triangles[index]]
            face = _face(owner, index, points, normal_tolerance, rec.get("reverse_winding", False) if rec.get("kind") != "box" else False)
            if face is not None:
                items.append(face)
        faces.append(items)
    occlusion = occlusion or _BoxOcclusion(records, 200.)
    count, area_total, used_cubes = 0, 0., set()
    pairs = ((a, b) for j, a in enumerate(faces[0]) for b in faces[0][:j]) if owners[0] == owners[1] else product(*faces)
    for face, other in pairs:
        if _dot(face.normal, other.normal) < 1. - normal_tolerance ** 2 / 2:
            continue
        if round((face.plane + other.plane) / (2 * plane_tolerance)) != round(row["plane_cm"] / plane_tolerance):
            continue
        if any(min(face.bounds[1][i], other.bounds[1][i]) < max(face.bounds[0][i], other.bounds[0][i]) - plane_tolerance for i in range(3)):
            continue
        gap = max(max(abs(_dot(face.normal, p) - face.plane) for p in other.points),
                  max(abs(_dot(other.normal, p) - other.plane) for p in face.points))
        if gap > plane_tolerance:
            continue
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        polygon = polygon_intersection(_project(face.points, axis), _project(other.points, axis))
        if len(polygon) < 3:
            continue
        area = abs(_signed_area(polygon)) / abs(face.normal[axis])
        if area < minimum_area:
            continue
        world = [_world_point(p, axis, face.normal, face.plane) for p in polygon]
        centre = tuple(sum(p[i] for p in world) / len(world) for i in range(3))
        points = [centre] + [tuple(.99 * p[i] + .01 * centre[i] for i in range(3)) for p in world]
        containing = [occlusion.containing(tuple(p[i] + .1 * face.normal[i] for i in range(3)), owners) for p in points]
        require(all(containing),
                "A purported buried polygon is exposed in the actual saved solid-cube geometry.")
        used_cubes.update(records[i]["id"] for candidates in containing for i in candidates)
        count += 1
        area_total += area
    require(count == row["face_pair_count"] and close(area_total, row["area_cm2"], .02) and used_cubes == set(declared),
            "Third-solid burial proof did not account for every face pair and overlap area.")
    return count


def complete_surface_stats(stats):
    """Cube rectangles cover native cube triangles without discarding faces."""
    return (isinstance(stats, dict) and stats.get("input_faces", 0) > 0
            and stats.get("degenerate_faces_skipped", 0) == 0
            and stats.get("non_axis_faces_skipped", 0) == 0
            and stats.get("axis_faces_scanned", 0) + stats.get("non_axis_faces_scanned", 0) == stats["input_faces"])


def verify_scans(digest, geometry, geometry_hash):
    from OldTownCoplanarScan import annotate_axisaligned_cubes, _BoxOcclusion
    raw, final = read(WORK / "SavedScan.json"), read(WORK / "SavedScanOcclusion.json")
    summary = read(WORK / "SavedScanSummary.json")
    geometry_path = (WORK / "GeometryAfter.json").resolve()
    for name, scan in (("SavedScan.json", raw), ("SavedScanOcclusion.json", final)):
        scope = scan.get("scope", {})
        require(scan.get("source_map_sha256") == digest and scan.get("source_geometry_sha256") == geometry_hash
                and Path(scan.get("source_geometry_path", "")).resolve() == geometry_path, name + " provenance is stale.")
        require(scope.get("component_count") == len(geometry["components"]) and scope.get("include_internal") is True
                and scope.get("axis_only") is False and close(scope.get("plane_tolerance_cm", 0), .03)
                and close(scope.get("minimum_overlap_area_cm2", 0), 1.) and close(scope.get("normal_tolerance", 0), .0001),
                name + " omitted whole-map/internal/arbitrary-normal scope or changed the scan tolerance.")
        require(scan.get("completed_utc") and scan.get("overlap_count") == len(scan.get("overlaps", []))
                and not scan.get("exact_duplicate_boxes"), name + " has no completion or contains duplicate exposed boxes.")
        require(complete_surface_stats(scan.get("stats")) and scan["stats"] == raw["stats"],
                name + " skipped degenerate/arbitrary-normal faces or changed complete face counts.")
    require(summary.get("passed") is True and not summary.get("exposed_candidates"), "SavedScanSummary failed or retains exposed candidates.")
    provenance = summary.get("provenance", {})
    require(provenance.get("source_map_sha256") == digest and provenance.get("source_geometry_sha256") == geometry_hash
            and Path(provenance.get("source_geometry_path", "")).resolve() == geometry_path,
            "SavedScanSummary map/geometry provenance is stale.")
    for field, filename in (("scan_sha256", "SavedScan.json"), ("classified_scan_sha256", "SavedScanOcclusion.json")):
        require(provenance.get(field) == sha(WORK / filename), "SavedScanSummary binds another " + filename)
    raw_rows = {overlap_identity(r): r for r in raw["overlaps"]}
    final_rows = {overlap_identity(r): r for r in final["overlaps"]}
    require(len(raw_rows) == len(raw["overlaps"]) and len(final_rows) == len(final["overlaps"])
            and set(raw_rows) == set(final_rows), "Occlusion classification removed, duplicated or changed raw overlap identities.")
    records = annotate_axisaligned_cubes(geometry["components"])
    by_id = {r["id"]: i for i, r in enumerate(records)}
    occlusion = _BoxOcclusion(records, 200.)
    proved_external_pairs, self_groups = 0, []
    for ident, before in raw_rows.items():
        after = final_rows[ident]
        require(all(i in by_id for i in after["components"]) and after.get("buried") is True
                and close(after.get("exposed_area_cm2", -1), 0) and close(after.get("buried_area_cm2", -1), after["area_cm2"]),
                "The saved scan contains an exposed or incompletely classified overlap.")
        if before.get("buried") is True and close(before.get("exposed_area_cm2", -1), 0):
            proved_external_pairs += third_box_proof(before, records, by_id, .0001, .03, 1., occlusion)
        else:
            require(before["intra_component"] is True and after["components"][0] == after["components"][1],
                    "An exposed inter-component overlap was reclassified without real geometry repair.")
            proof = after.get("self_occlusion", {})
            require(proof.get("complete_group_recomputed") is True and proof.get("closed_mesh") is True
                    and proof.get("odd_boundary_edges") == 0 and proof.get("tested_face_pairs") == proof.get("expected_face_pairs") == after["face_pair_count"]
                    and close(proof.get("recomputed_area_cm2", -1), after["area_cm2"])
                    and close(proof.get("internal_buried_area_cm2", -1), after["area_cm2"]),
                    "Internal burial lacks a complete closed solid and whole-area proof.")
            method = str(proof.get("method", "")).lower()
            require("signed ray" in method and "centre" in method and "vertex" in method,
                    "Internal burial lacks signed-ray centre/vertex proof.")
            self_groups.append(dict(components=after["components"], tested_face_pairs=proof["tested_face_pairs"],
                area_cm2=after["area_cm2"], method=proof["method"]))
    expected = dict(groups=len(final_rows), exposed_groups=0, fully_buried_groups=len(final_rows),
        inter_exposed=0, intra_exposed=0, exact_duplicate_box_groups=0)
    require(all(summary.get("counts", {}).get(k) == v for k, v in expected.items()), "SavedScanSummary counts differ from actual complete groups.")
    require(summary.get("scope", {}).get("include_internal") is True and summary.get("scope", {}).get("axis_only") is False,
            "SavedScanSummary omits internal/arbitrary-normal surfaces.")
    require(complete_surface_stats(summary.get("stats")) and summary["stats"] == raw["stats"],
            "SavedScanSummary does not bind the complete zero-skipped face coverage.")
    return dict(passed=True, map_sha256=digest, geometry_sha256=geometry_hash,
        scanned_visible_components=len(records), scanned_render_triangles=geometry["triangles"],
        arbitrary_normal_surfaces=True, internal_surfaces=True, plane_tolerance_cm=.03,
        minimum_overlap_area_cm2=1., final_counts=expected, retained_buried_groups=len(final_rows),
        independently_recomputed_third_solid_face_pairs=proved_external_pairs,
        completely_recomputed_internal_buried_groups=len(self_groups), internal_occlusion_proofs=self_groups,
        scope="Same-facing overlaps >=1cm2 at 0.03cm plane tolerance; valid buried groups remain as evidence.")


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "Capture time has no timezone.")
    return result.timestamp()


def helper_run(run_id, metadata, digest, camera, mode, new_root):
    require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", run_id), "Unsafe/missing capture run ID.")
    directory = WORK / "ClosureCaptures/Runs" / run_id
    owned, shutdown, batch = (read(directory / n) for n in ("OwnedProcess.json", "ShutdownRequest.json", "CaptureBatch.json"))
    pid = metadata["owned_editor_pid"]
    require(isinstance(pid, int) and pid > 0 and owned.get("run_id") == shutdown.get("run_id") == batch.get("run_id") == run_id
            and owned.get("owned_editor_pid") == shutdown.get("owned_editor_pid") == batch.get("owned_editor_pid") == pid,
            "Capture process/run identity differs: " + camera)
    require(owned.get("normal_exit") is True and owned.get("helper_has_exited") is True and owned.get("exit_code") == 0
            and owned.get("forced_cleanup") is False and owned.get("lifecycle_status") == "NORMAL_EXIT",
            "Current capture helper did not exit normally: " + camera)
    require(owned.get("map_sha256") == owned.get("map_sha256_after") == digest and owned.get("persisted_map_unchanged") is True
            and owned.get("map_save_requested") is False and owned.get("no_auto_save") is True
            and owned.get("cleanup_only_owned_process") is True and owned.get("window_style") == "Hidden"
            and Path(owned.get("output_directory", "")).resolve() == (WORK / "ClosureCaptures").resolve()
            and owned.get("lighting_mode") == mode and owned.get("view_mode") == "lit" and camera in owned.get("cameras", []),
            "Helper ownership/map/capture parameters differ: " + camera)
    require(shutdown.get("status") == "REQUESTED" and shutdown.get("keep_alive_released") is True
            and shutdown.get("deferred_quit_returned") is True and shutdown.get("map_save_requested") is False
            and owned.get("shutdown_request") == shutdown, "Normal helper shutdown request is unverified: " + camera)
    lighting = batch.get("temporary_lighting", {})
    require(batch.get("status") == "PASS" and batch.get("target_level") == TARGET and batch.get("map_sha256") == batch.get("map_sha256_after_cleanup") == digest
            and batch.get("source") == "fresh_persisted_map_load" and batch.get("persisted_map_unchanged") is True
            and batch.get("map_save_requested") is False and batch.get("lighting_mode") == mode and batch.get("view_mode") == "lit"
            and camera in batch.get("requested_cameras", []) and lighting.get("cleanup_verified_zero") is True
            and lighting.get("remaining_count") == 0 and not lighting.get("remaining_labels") and not lighting.get("errors"),
            "Capture batch saved-map/lighting-cleanup proof failed: " + camera)
    require(batch.get("appearance_assets_unchanged") is True, "Capture batch appearance assets changed: " + camera)
    asset_binding(batch, new_root, "CaptureBatch " + run_id)
    asset_binding(batch, new_root, "CaptureBatch after cleanup " + run_id, after=True)
    launched = parse_time(owned["launch_time_utc"])
    latest_revision = max([MAP.stat().st_mtime] + [Path(p).stat().st_mtime for p in new_root])
    require(launched >= latest_revision, "Capture helper predates the latest persisted map/asset revision: " + camera)
    archive = directory / "Renders" / (camera + ".png")
    require(archive.is_file() and sha(archive) == metadata["png_sha256"] and read(archive.with_suffix(".json")) == metadata,
            "PNG/metadata differ from their current run archive: " + camera)
    files = {str(directory / n): sha(directory / n) for n in ("OwnedProcess.json", "ShutdownRequest.json", "CaptureBatch.json")}
    files.update({str(archive): sha(archive), str(archive.with_suffix(".json")): sha(archive.with_suffix(".json"))})
    return dict(run_id=run_id, owned_editor_pid=pid, normal_exit=True, forced_cleanup=False,
        exit_code=0, persisted_map_unchanged=True, launch_time_utc=owned["launch_time_utc"],
        owned_process=str(directory / "OwnedProcess.json"), shutdown_request=str(directory / "ShutdownRequest.json"),
        capture_batch=str(directory / "CaptureBatch.json")), files, launched


def verify_captures(build, digest, new_root):
    directory = WORK / "ClosureCaptures"
    run_file = directory / "CaptureRuns.json"
    rows = read(run_file)
    require(isinstance(rows, list) and len(rows) == len({r.get("camera") for r in rows}) == len(CAMERAS)
            and {r["camera"] for r in rows} == CAMERAS, "CaptureRuns lacks the exact twelve current viewpoints.")
    require(len(build.get("hotel_openings_review_cameras", [])) == len(CAMERAS) and set(build["hotel_openings_review_cameras"]) == CAMERAS,
            "BuildReport selected review cameras differ.")
    views, helpers, capture_files = [], {}, {str(run_file): sha(run_file)}
    for row in rows:
        camera = row["camera"]
        png = directory / "Renders" / (camera + ".png")
        meta_file = png.with_suffix(".json")
        data, metadata = png.read_bytes(), read(meta_file)
        require(len(data) > 20000 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR", "Invalid/incomplete current PNG: " + camera)
        dimensions = struct.unpack(">II", data[16:24])
        require(dimensions == (metadata.get("width"), metadata.get("height")) and dimensions[0] >= 1280 and dimensions[1] >= 720,
                "Current PNG resolution differs or is too small: " + camera)
        require(metadata.get("status") == "PASS" and metadata.get("camera") == camera and metadata.get("target_level") == TARGET
                and metadata.get("map_sha256") == metadata.get("map_sha256_after_cleanup") == digest
                and metadata.get("png_sha256") == sha(png) and metadata.get("bytes") == len(data), "Current PNG/map/hash identity differs: " + camera)
        require(metadata.get("source") == "fresh_persisted_map_load" and metadata.get("fresh_map_load_verified") is True
                and metadata.get("persisted_map_unchanged") is True and metadata.get("map_save_requested") is False
                and Path(metadata.get("source_persisted_map", "")).resolve() == MAP.resolve()
                and metadata.get("view_mode_requested") == metadata.get("view_mode_verified") == "lit", "PNG did not inspect the fresh saved lit map: " + camera)
        mode = metadata.get("lighting_mode")
        lighting = metadata.get("temporary_lighting", {})
        require(mode in ("temporary", "street_only") and metadata.get("temporary_lighting_cleanup_verified_zero") is True
                and metadata.get("temporary_lighting_cleanup_remaining_count") == 0 and lighting.get("cleanup_verified_zero") is True
                and lighting.get("remaining_count") == 0 and not lighting.get("remaining_labels") and not lighting.get("errors")
                and lighting.get("mode") == mode and lighting.get("created_count") == lighting.get("destroyed_count") == metadata.get("temporary_lighting_created_count")
                and ((mode == "temporary" and lighting["created_count"] > 0) or (mode == "street_only" and lighting["created_count"] == 0)),
                "Temporary inspection lights were not completely cleaned: " + camera)
        asset_binding(metadata, new_root, "PNG metadata " + camera)
        asset_binding(metadata, new_root, "PNG metadata after cleanup " + camera, after=True)
        require(metadata.get("appearance_assets_unchanged") is True, "PNG capture appearance assets changed: " + camera)
        asset_binding(row, new_root, "CaptureRuns " + camera)
        run_id = metadata.get("run_id")
        helper, files, launched = helper_run(run_id, metadata, digest, camera, mode, new_root)
        helpers[run_id] = helper
        capture_files.update(files)
        require(row.get("captured") is True and row.get("reused") is False and row.get("normal_exit") is True and row.get("forced_cleanup") is False
                and row.get("exit_code") == 0 and row.get("lifecycle_status") == "NORMAL_EXIT"
                and row.get("map_sha256") == digest and row.get("run_id") == run_id and row.get("owned_editor_pid") == metadata["owned_editor_pid"]
                and row.get("lighting_mode") == mode and row.get("view_mode") == "lit" and Path(row.get("path", "")).resolve() == png.resolve()
                and Path(row.get("archive", "")).resolve() == (directory / "Runs" / run_id / "Renders" / (camera + ".png")).resolve(),
                "CaptureRuns row differs from its current PNG/helper proof: " + camera)
        require(png.stat().st_mtime >= launched and meta_file.stat().st_mtime >= launched, "Current PNG/metadata predate the helper.")
        capture_files.update({str(png): sha(png), str(meta_file): sha(meta_file)})
        views.append(dict(camera=camera, png=str(png), metadata=str(meta_file), png_sha256=sha(png),
            width=dimensions[0], height=dimensions[1], bytes=len(data), lighting_mode=mode, view_mode="lit",
            run_id=run_id, owned_editor_pid=metadata["owned_editor_pid"], fresh_persisted_map_load=True,
            persisted_map_unchanged=True, asset_manifest_sha256=json_fingerprint(new_root), temporary_lighting_cleanup_remaining_count=0))
    visual = current_report("VisualReview.json", digest)
    reviewed = visual.get("views", [])
    current = {v["camera"]: v for v in views}
    require(visual.get("reviewer") and len(reviewed) == len({v.get("camera") for v in reviewed}) == len(CAMERAS)
            and {v["camera"] for v in reviewed} == CAMERAS and all(v.get("passed") is True and
                v.get("png_sha256") == current[v["camera"]]["png_sha256"] and v.get("observations")
                and Path(v.get("png", "")).resolve() == Path(current[v["camera"]]["png"]).resolve() for v in reviewed)
            and visual.get("schema") == "OldTownRealismVisualReviewV1" and visual.get("status") == "PASS"
            and parse_time(visual["reviewed_utc"]) >= max(Path(v["png"]).stat().st_mtime for v in views),
            "Root visual review lacks the exact twelve actual PNG identities/observations.")
    asset_binding(visual, new_root, "VisualReview")
    visual_limitations = visual.get("limitations", [])
    require(isinstance(visual_limitations, list) and all(isinstance(v, str) and v.strip() for v in visual_limitations),
            "Visual review limitations must be explicit nonempty strings.")
    require(all(Path(p).resolve().is_relative_to(directory.resolve()) for p in capture_files), "Capture proof escapes this stage's Captures directory.")
    return dict(passed=True, status="PASS", target_level=TARGET, map_sha256=digest,
        asset_manifest_sha256=json_fingerprint(new_root), capture_directory=str(directory), current_renders=str(directory / "Renders"),
        current_capture_runs_file=str(run_file), current_capture_runs_sha256=sha(run_file), current_capture_file_sha256=capture_files,
        views=views, current_helpers=list(helpers.values()), current_helper_normal_exit_verified=True,
        temporary_lighting_cleanup_verified_zero=True, visual_review_file=str(WORK / "VisualReview.json"),
        visual_review_sha256=sha(WORK / "VisualReview.json"), visual_limitations=visual_limitations, reviewed_utc=utc())


def history(previous):
    pointers = {k: deepcopy(v) for k, v in previous.items() if k.startswith("historical_")}
    old = read(SOURCE / "FinalReview.json")
    old_views = old.get("current_captures", [])
    require(old.get("passed") is True and old.get("map_sha256") == SOURCE_SHA and len(old_views) == 4
            and all(sha(v["png"]) == v["png_sha256"] for v in old_views), "Prior accepted sanitary-finish review changed.")
    for key in ("historical_shape_views", "historical_fixture_views", "historical_basin_views"):
        require(key in pointers and pointers[key].get("status") == "historical", "An inherited historical bundle pointer is missing: " + key)
    # Preserve all prior history fields verbatim, including original review/map
    # identities; add the former current result as another historical bundle.
    pointers["historical_sanitary_finish_views"] = dict(status="historical", map_sha256=SOURCE_SHA,
        bundle=str(SOURCE), review=str(SOURCE / "FinalReview.json"), review_sha256=sha(SOURCE / "FinalReview.json"),
        view_count=4, cameras=[v["camera"] for v in old_views])
    return pointers


def validate():
    previous, pointer_hash = canonical_source()
    digest = sha(MAP)
    build, hotel_input = read(WORK / "BuildReport.json"), read(WORK / "RealismInput.json")
    street_input = read(WORK / "RealismStreetInput.json")
    inp = whole_map_input(hotel_input, street_input)
    require(build.get("status") == "PASS" and build.get("target_level") == TARGET and build.get("map_sha256") == digest
            and build.get("source_map_sha256") == inp.get("source_map_sha256") == inp.get("map_sha256") == SOURCE_SHA and digest != SOURCE_SHA,
            "Build/input/current map does not bind the accepted ade3 starting map and a new persisted result.")
    require(inp.get("passed") is True and all(inp.get("read_only_verification", {}).get(k) is True for k in
        ("map_unchanged", "original_actor_states_unchanged", "original_400_assets_unchanged", "protected_maps_unchanged", "recursively_read_assets_unchanged", "no_save_or_compile_called")),
        "Native accepted input inventory lacks its complete read-only proof.")
    immutable = hashes(inp["original_400_shared_asset_sha256"], "Original 400 assets", 400)
    hashes(hotel_input["source_asset_file_sha256"], "Native 141 hotel input assets", 141)
    native_sources = hashes(inp["source_asset_file_sha256"], "Complete native hotel/street input assets")
    input_rebase = protected_input_rebase(hotel_input, street_input)
    protected = hashes(street_input["protected_map_sha256"], "Latest three protected input maps", 3)
    require(protected.get(str((ROOT / "Content/Yastar/Maps/L_Main.umap").resolve())) == CURRENT_MAIN_INPUT_SHA,
            "L_Main protection reverted to an older input instead of the latest accepted d45a save.")
    require(normalized(build["protected_map_sha256"]) == protected, "Build protected-map identity differs from current input.")
    source_reports = hashes(inp["source_input_sha256"], "Accepted source report files")
    require(sha(WORK / "Before" / MAP.name) == SOURCE_SHA, "Immutable Before source-map copy is absent or differs.")
    for name in ("BuildReport.json", "AfterSnapshot.json"):
        require(read(WORK / "Before" / name) == read(SOURCE / name), "Before source report copy differs: " + name)
    for path, expected in protected.items():
        require(sha(WORK / "Before" / ("Protected_" + Path(path).name)) == expected,
                "Latest protected-map Before copy differs: " + path)
    all_new = hashes(build["new_asset_sha256"], "Build generated packages")
    require(all(Path(p).is_relative_to((ROOT / "Content/CodexGenerated").resolve()) for p in all_new), "A generated package escaped CodexGenerated.")
    new_root = root_subset(all_new)
    actual_files = {str(p.resolve()) for p in GENERATED.rglob("*") if p.is_file()}
    require(new_root and set(new_root) == actual_files, "Build.new_asset_sha256 does not cover every file in the new Realism root.")
    require(all(not Path(p).is_relative_to(GENERATED.resolve()) for p in immutable | native_sources), "An original input package was placed in the writable new root.")
    applied = current_report("Applied.json", digest)
    apply = current_report("RealismApply.json", digest)
    require(applied.get("source_map_sha256") == apply.get("source_map_sha256") == SOURCE_SHA
            and applied.get("actor_count") == 8014, "Applied marker does not identify the accepted source/count.")
    require(normalized(apply.get("protected_map_sha256", {})) == protected
            and normalized(apply.get("source_asset_sha256", {})) == native_sources,
            "Whole-map apply omitted or changed a protected/source-native input file.")
    repairs, contacts, role_proof, followup_repairs, followup_proof, closure_proof = verify_appearance_stage_chain(
        build, inp, apply, applied, digest)
    require(applied.get("additional_surface_repairs") == 51, "Applied marker omitted the exact 51 contact repairs.")
    appearance = current_report("AppearanceAudit.json", digest, fresh=True)
    asset_binding(appearance, new_root, "AppearanceAudit")
    require(normalized(appearance.get("input_sha256", {})) == {str((WORK / n).resolve()): sha(WORK / n) for n in AUDIT_INPUTS},
            "Fresh native appearance audit binds different input/import/material reports.")
    after = read(WORK / "AfterSnapshot.json")
    require(normalized(after.get("protected_map_sha256", {})) == protected, "Saved after snapshot protects different input maps.")
    rows, preservation = appearance_preservation(build, inp, apply, after, appearance, repairs, followup_repairs)
    require("strict_51_additive_render_contact_repairs" in {r["name"] for r in appearance["checks"]},
            "Native appearance audit omitted strict additive contact acceptance.")
    require(applied.get("changed_components") == len(rows) and applied.get("changed_actors") == preservation["changed_actors"],
            "Applied marker component/Actor counts differ.")
    architecture = current_report("ArchitectureAudit.json", digest, fresh=True)
    detail = current_report("DetailAudit.json", digest, fresh=True)
    require(architecture.get("statistics", {}).get("actors") == 8014, "Fresh architecture audit omitted saved Actors.")
    models, fbx, recipes = verify_models(build, rows, appearance, new_root)
    solids, solid_files = verify_source_solids(appearance, models, inp)
    independent_solids, independent_files = verify_independent_source_solids(models)
    solids["independent_serialized_source_audit"] = independent_solids
    solid_files = merge_hashes(solid_files, independent_files, "Source/independent solid files")
    recipes = merge_hashes(recipes, solid_files, "Model/solid recipe hashes")
    material = read(WORK / "MaterialBuild.json")
    require(material.get("passed") is True and material.get("final_compile_logs"), "PBR material build/compile evidence is incomplete.")
    require(appearance.get("materials") and appearance.get("shader_compile_logs") and all(not r.get("shader_errors") and
        Path(r["file"]).is_file() and sha(r["file"]) == r["sha256"] for r in appearance["shader_compile_logs"]),
        "Final shader-compile logs have changed, failed, or are absent.")
    material_assets = material.get("assets", material.get("records", []))
    if isinstance(material_assets, dict):
        material_assets = list(material_assets.values())
    for row in material_assets:
        if row.get("file") and row.get("sha256"):
            require(new_root.get(str(Path(row["file"]).resolve())) == row["sha256"], "Material/texture package does not match Build SHA: " + str(row.get("asset")))
        texture_source = row.get("source_file", row.get("source"))
        if texture_source and row.get("source_sha256"):
            hashes({texture_source: row["source_sha256"]}, "Material texture source")
            recipes[str(Path(texture_source).resolve())] = row["source_sha256"]
    require(material.get("physical_uv_cm_per_unit") == 100., "Material physical UV unit changed.")
    masters = {r["asset"]: r for r in material_assets if r.get("kind") == "master"}
    checks = {r["name"] for r in appearance["checks"]}
    outputs = ("MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_METALLIC", "MP_WORLD_POSITION_OFFSET")
    from AuditOldTownRealismAppearance import normal_projection_contract
    for path, native_material in appearance["materials"].items():
        require(path in masters and native_material.get("role") == masters[path]["role"]
                and native_material.get("projection") == masters[path]["projection"]
                and all(native_material.get("output_connections", {}).get(p, {}).get("node") for p in outputs),
                "Actual active master lacks registered physical PBR output connections: " + path)
        require(all(prefix + path in checks for prefix in ("active_pbr_master_registered:", "active_pbr_role_known:",
                    "real_pbr_output_connections:", "normal_projection_space_property:", "no_missing_graph_texture_objects:")),
                "An active PBR master lacks native graph/property acceptance: " + path)
        scanned = masters[path].get("scan") is not None
        normal_input = native_material.get("actual_normal_input", {})
        require(native_material.get("scanned") is scanned
                and normal_input.get("node") == native_material["output_connections"]["MP_NORMAL"]["node"]
                and normal_projection_contract(native_material["projection"], scanned,
                    native_material.get("tangent_space_normal"), normal_input),
                "Actual master normal node/property pair is invalid in its projection space: " + path)
    require(appearance["statistics"].get("active_pbr_masters") == len(appearance["materials"]), "Active PBR master coverage/count differs.")
    for log in appearance["shader_compile_logs"]:
        recipes[str(Path(log["file"]).resolve())] = log["sha256"]
    geometry, summary, geometry_hash = verify_geometry(digest, new_root)
    scan = verify_scans(digest, geometry, geometry_hash)
    captures = verify_captures(build, digest, new_root)
    inherited = history(previous)
    evidence_names = [n for n in REPORTS if n not in ("CaptureReview.json", "RealismFinalAudit.json", "FinalReview.json")]
    extra = [WORK / "GeometryAfter.json", WORK / "AppearanceSnapshot.json"]
    if inp.get("input_baseline_rebase_file"):
        extra.append(Path(inp["input_baseline_rebase_file"]))
    evidence = {str((WORK / n).resolve()): sha(WORK / n) for n in evidence_names}
    evidence.update({str(p.resolve()): sha(p) for p in extra})
    evidence.update(contacts["prior_and_diagnostic_file_sha256"])
    evidence.update(role_proof["prior_and_classifier_file_sha256"])
    evidence.update(followup_proof["prior_and_diagnostic_file_sha256"])
    evidence.update(closure_proof["prior_and_diagnostic_file_sha256"])
    immutable.update(native_sources)
    immutable.update(protected)
    immutable.update(source_reports)
    asset_types = {kind: {str(Path(r["file"]).resolve()): r["sha256"] for r in material_assets if r.get("kind") == kind}
                   for kind in ("texture", "master", "offset_instance")}
    audit = dict(schema="OldTownRealismFinalAuditV1", passed=True, status="PASS", target_level=TARGET,
        map_sha256=digest, source_map_sha256=SOURCE_SHA, source="fresh_persisted_map_load",
        persisted_map_unchanged=True, actor_count=8014, hotel_actor_count=2975, outside_hotel_actor_count=5039,
        scope="whole_map", protected_input_rebase=input_rebase, additive_contact_repairs=contacts,
        followup_contact_repair=followup_proof,
        model_closure_import_repairs=closure_proof,
        wall_and_floor_material_role_repairs=role_proof, source_solids_and_uv=solids,
        preservation=preservation, models=models, new_asset_sha256=all_new, new_root_asset_sha256=new_root,
        asset_manifest_sha256=json_fingerprint(new_root), source_fbx_sha256=fbx, source_art_sha256=recipes,
        immutable_input_sha256=immutable, input_sha256=evidence, current_capture_file_sha256=captures["current_capture_file_sha256"],
        architecture_statistics=architecture.get("statistics", {}), detail_statistics=detail.get("statistics", {}),
        surface_scans=scan, reviewed_utc=utc())
    final = dict(schema="OldTownRealismFinalReviewV1", passed=True, status="PASS", target_level=TARGET,
        map_sha256=digest, source_map_sha256=SOURCE_SHA, current_bundle=str(WORK), source_bundle_name=WORK.name,
        actor_count=8014, hotel_actor_count=2975, outside_hotel_actor_count=5039,
        scope="whole_map", protected_input_rebase=input_rebase, additive_contact_repairs=contacts,
        followup_contact_repair=followup_proof,
        model_closure_import_repairs=closure_proof,
        wall_and_floor_material_role_repairs=role_proof, source_solids_and_uv=solids,
        change="Detailed furniture, openings, stairs, sanitary fixtures and street models with realistic aged PBR materials across the saved map, preserving layout, poses, collision and interactions.",
        preservation=preservation, models=models, active_pbr_masters=len(appearance["materials"]),
        new_asset_sha256=all_new, new_root_asset_sha256=new_root, asset_manifest_sha256=json_fingerprint(new_root),
        material_asset_sha256=asset_types, source_fbx_sha256=fbx, source_art_sha256=recipes,
        imported_mesh_sha256={p: h for p, h in new_root.items()
            if any(Path(p).is_relative_to(GENERATED.resolve() / "Meshes" / category)
                for category in models["categories"])},
        immutable_input_sha256=immutable, current_evidence_file_sha256=evidence,
        current_render_source=str(WORK / "GeometryAfter.json"), current_render_source_sha256=geometry_hash,
        current_actor_snapshot=str(WORK / "AfterSnapshot.json"), current_actor_snapshot_sha256=sha(WORK / "AfterSnapshot.json"),
        fresh_architecture_validation=architecture.get("statistics", {}), fresh_detail_validation=detail.get("statistics", {}),
        whole_map_render_summary=summary, surface_scans=scan, current_captures=captures["views"],
        current_helpers=captures["current_helpers"], current_capture_file_sha256=captures["current_capture_file_sha256"],
        capture_directory=captures["capture_directory"], current_renders=captures["current_renders"],
        current_capture_runs_file=captures["current_capture_runs_file"], current_capture_runs_sha256=captures["current_capture_runs_sha256"],
        previous_bundle=str(SOURCE), previous_evidence_status="historical", **inherited,
        limitations=["Current image identity and PBR acceptance apply to the twelve reviewed views.",
            "Temporary inspection lights, where used, were completely cleaned without saving the map.",
            "The complete saved surface scan detects same-facing overlaps >=1cm2 within 0.03cm; proven buried groups remain in the evidence.",
            *captures["visual_limitations"]],
        reviewed_utc=audit["reviewed_utc"])
    result = dict(build=build, digest=digest, mapfile=MAP, new_assets=all_new, immutable=immutable,
        fbx=fbx, recipes=recipes, evidence=evidence, geometry_hash=geometry_hash, captures=captures,
        audit=audit, final=final, previous=previous, canonical_pointer_sha256=pointer_hash)
    recheck(result)
    return result


def recheck(result):
    require(sha(MAP) == result["digest"], "Current map changed during/before final publication.")
    for field in ("new_assets", "immutable", "fbx", "recipes", "evidence"):
        hashes(result[field], "Final recheck " + field)
    hashes(result["captures"]["current_capture_file_sha256"], "Final capture recheck")
    require(sha(WORK / "GeometryAfter.json") == result["geometry_hash"], "Render geometry changed during final publication.")
    require({str(p.resolve()) for p in GENERATED.rglob("*") if p.is_file()} == set(root_subset(result["new_assets"])),
            "Generated Realism root changed its file set during publication.")


def save_review(result):
    recheck(result)
    write(WORK / "CaptureReview.json", result["captures"])
    write(WORK / "RealismFinalAudit.json", result["audit"])
    result["final"]["current_evidence_file_sha256"].update({str((WORK / n).resolve()): sha(WORK / n)
        for n in ("CaptureReview.json", "RealismFinalAudit.json")})
    write(WORK / "FinalReview.json", result["final"])
    require(sha(MAP) == result["digest"], "Saving JSON review unexpectedly changed the map.")


def _publish_current(result):
    # FinalReview exists and is bound before any canonical copy is changed.
    require(read(WORK / "FinalReview.json") == result["final"] and result["final"]["passed"] is True,
            "Fresh passing FinalReview must be saved before publication.")
    recheck(result)
    require(sha(CANON / "CurrentEvidence.json") == result["canonical_pointer_sha256"],
            "Canonical evidence changed concurrently; refusing publication.")
    backup = WORK / "BeforeCanonicalPublish"
    backup.mkdir(parents=True, exist_ok=True)
    names = sorted(set(REPORTS) | {"CurrentEvidence.json"} | set(result["previous"]["current_reports"]))
    for name in names:
        require(Path(name).name == name and name.endswith(".json"), "Unsafe canonical filename.")
        source, target = CANON / name, backup / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    previous_backup = read(backup / "CurrentEvidence.json")
    require(previous_backup == result["previous"], "Prior canonical backup does not preserve the accepted original pointer.")
    write(backup / "BackupManifest.json", dict(historical_only=True, source_map_sha256=SOURCE_SHA,
        current_publication_map_sha256=result["digest"], backed_up_report_sha256={p.name: sha(p) for p in backup.glob("*.json") if p.name != "BackupManifest.json"}))
    expected = {n: sha(WORK / n) for n in REPORTS}
    for name in REPORTS:
        temporary = CANON / (name + ".tmp")
        shutil.copy2(WORK / name, temporary)
        temporary.replace(CANON / name)
        require(sha(CANON / name) == expected[name], "Published report differs: " + name)
    recheck(result)
    require(sha(CANON / "CurrentEvidence.json") == result["canonical_pointer_sha256"], "Canonical pointer advanced during report copies.")
    captures = result["captures"]
    prior = result["previous"]
    pointer = deepcopy(prior)
    pointer.update(target_level=TARGET, map_sha256=result["digest"], source_map_sha256=SOURCE_SHA,
        source_bundle=str(WORK), source_bundle_name=WORK.name, source_directory=str(WORK),
        actor_count=8014, hotel_actor_count=2975, outside_hotel_actor_count=5039,
        scope="whole_map", changed_component_count=result["final"]["preservation"]["changed_components"],
        changed_actor_count=result["final"]["preservation"]["changed_actors"],
        current_reports=list(REPORTS), current_report_sha256=expected,
        current_renders=captures["current_renders"], current_capture_directory=captures["capture_directory"],
        current_capture_runs_file=captures["current_capture_runs_file"], current_capture_runs_sha256=captures["current_capture_runs_sha256"],
        current_render_cameras=[v["camera"] for v in captures["views"]],
        current_render_lighting_modes={v["camera"]: v["lighting_mode"] for v in captures["views"]},
        current_render_geometry=str(WORK / "GeometryAfter.json"), current_render_geometry_sha256=result["geometry_hash"],
        current_actor_snapshot=str(WORK / "AfterSnapshot.json"), current_actor_snapshot_sha256=sha(WORK / "AfterSnapshot.json"),
        current_architecture_plan=str(WORK / "ArchitecturePlan.json"), current_architecture_plan_sha256=sha(WORK / "ArchitecturePlan.json"),
        current_asset_sha256=result["new_assets"], current_asset_manifest_sha256=json_fingerprint(root_subset(result["new_assets"])),
        current_source_fbx_sha256=result["fbx"], current_final_review=str(WORK / "FinalReview.json"),
        current_final_review_sha256=sha(WORK / "FinalReview.json"), previous_bundle=str(SOURCE),
        previous_evidence_status="historical", historical_report_backup=str(backup), published_utc=utc())
    pointer.update({k: deepcopy(v) for k, v in result["final"].items() if k.startswith("historical_")})
    # Existing historical fields are preserved exactly. Retired current reports
    # get their own field instead of rewriting the older inherited history list.
    pointer["newly_retired_reports_not_current"] = sorted(set(prior["current_reports"]) - set(REPORTS))
    require(all(pointer.get(k) == v for k, v in prior.items() if k.startswith("historical_")), "Publication rewrote inherited historical evidence.")
    result["publication_pointer_sha256"] = hashlib.sha256(json.dumps(pointer, ensure_ascii=False, indent=2).encode("utf-8")).hexdigest()
    write(CANON / "CurrentEvidence.json", pointer)
    require(read(CANON / "CurrentEvidence.json") == pointer and sha(MAP) == result["digest"], "Final pointer/map publication verification failed.")
    return expected


def publish(result):
    """Restore this attempt's prior canonical files if publication fails.

    The original historical backup is kept separately; a later retry must
    restore its own starting files rather than reverting an accepted run.
    """
    recheck(result)
    require(sha(CANON / "CurrentEvidence.json") == result["canonical_pointer_sha256"],
            "Canonical evidence changed before publication.")
    lock = CANON / ".OldTownRealismPublication.lock"
    attempt = WORK / "CanonicalPublicationAttempts" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    # Exclusive creation prevents another instance of this finalizer from
    # replacing the same reports while this attempt is copying them.
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(attempt=str(attempt), map_sha256=result["digest"], created_utc=utc())))
    prior = {}
    copying_started = False
    try:
        attempt.mkdir(parents=True, exist_ok=False)
        require(sha(CANON / "CurrentEvidence.json") == result["canonical_pointer_sha256"],
                "Canonical pointer changed while acquiring publication ownership.")
        for name in (*REPORTS, "CurrentEvidence.json"):
            path = CANON / name
            if path.is_file():
                copy = attempt / name
                shutil.copy2(path, copy)
                prior[name] = dict(existed=True, sha256=sha(path), backup=str(copy))
                require(sha(copy) == prior[name]["sha256"], "Publication rollback copy differs: " + name)
            else:
                prior[name] = dict(existed=False)
        write(attempt / "Attempt.json", dict(status="PREPARED", map_sha256=result["digest"], prior_files=prior))
        copying_started = True
        expected = _publish_current(result)
        write(attempt / "Attempt.json", dict(status="PASS", map_sha256=result["digest"], prior_files=prior,
            current_report_sha256=expected, current_pointer_sha256=sha(CANON / "CurrentEvidence.json")))
        return expected
    except Exception:
        failure = traceback.format_exc()
        if copying_started:
            pointer_sha = sha(CANON / "CurrentEvidence.json")
            require(pointer_sha in {result["canonical_pointer_sha256"], result.get("publication_pointer_sha256")},
                    "Publication failed and another writer changed CurrentEvidence; refusing to overwrite that writer's evidence. " + failure)
            # Restore reports first, then the pointer which selects them.
            for name in (*REPORTS, "CurrentEvidence.json"):
                state, target = prior[name], CANON / name
                if state["existed"]:
                    require(sha(state["backup"]) == state["sha256"], "Publication rollback input changed: " + name)
                    pending = CANON / (name + ".rollback.tmp")
                    shutil.copy2(state["backup"], pending)
                    pending.replace(target)
                    require(sha(target) == state["sha256"], "Publication rollback differs: " + name)
                elif target.exists():
                    target.unlink()
            require(sha(CANON / "CurrentEvidence.json") == result["canonical_pointer_sha256"], "Publication pointer rollback failed.")
            write(attempt / "Attempt.json", dict(status="ROLLED_BACK", map_sha256=result["digest"], prior_files=prior, error=failure))
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-only", action="store_true", help="Write this stage's fresh acceptance review without updating canonical evidence (default).")
    modes.add_argument("--publish", action="store_true", help="After acceptance, copy current reports and update canonical CurrentEvidence.json.")
    args = parser.parse_args()
    try:
        result = validate()
        save_review(result)
        published = publish(result) if args.publish else {}
        print(json.dumps(dict(passed=True, published=bool(published), map_sha256=result["digest"],
            actors=8014, hotel_actors=2975, outside_hotel_actors=5039, current_views=len(CAMERAS),
            source_fbx=len(result["fbx"]), detailed_meshes=result["final"]["models"]["actual_native_imported_meshes"],
            exposed_coplanar_groups=0, duplicate_visible_boxes=0, canonical_reports=len(published)), ensure_ascii=False))
    except Exception:
        failure = dict(schema="OldTownRealismFinalReviewV1", passed=False, status="FAIL", target_level=TARGET,
            map_sha256=sha(MAP) if MAP.is_file() else None, source_map_sha256=SOURCE_SHA,
            current_bundle=str(WORK), reviewed_utc=utc(), canonical_publication_requested=args.publish,
            error=traceback.format_exc())
        write(WORK / "FinalReviewFailure.json", failure)
        # Failure invalidates an older review in this stage; it never modifies
        # the canonical pointer or misrepresents incomplete evidence as current.
        write(WORK / "FinalReview.json", failure)
        raise


if __name__ == "__main__":
    main()
