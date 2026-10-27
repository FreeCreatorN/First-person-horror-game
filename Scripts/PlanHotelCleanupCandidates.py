"""Read-only provenance proposal for the narrow 10+19+18 authored source sets.

Writes only this stage's CleanupOwnershipCandidates.json. It never imports
Unreal or moves/deletes/changes Content. No cumulative owned/current hash bag is
accepted as creation evidence. A fresh post-commit graph is still mandatory.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

R = Path(__file__).resolve().parents[1]
CONTENT = R / "Content"
OUTPUTS = R / "Saved/CodexOutputs"
W = OUTPUTS / "OldTownHotelNaming_20261017"
ORIGINAL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_file(package):
    return CONTENT / (package.removeprefix("/Game/") + ".uasset")


def package_for(file):
    return "/Game/" + Path(file).resolve().relative_to(CONTENT).with_suffix("").as_posix()


def runtime_source_literals(packages):
    """Editor modules are conservative roots too; historical Scripts are not."""
    result = defaultdict(list)
    files = [R / "HorrorGame.uproject"]
    for base in (R / "Config", R / "Source"):
        if base.is_dir():
            files.extend(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in (".ini", ".cpp", ".h", ".cs"))
    plugins = R / "Plugins"
    if plugins.is_dir():
        for plugin in plugins.iterdir():
            if not plugin.is_dir():
                continue
            files.extend(plugin.glob("*.uplugin"))
            for area in ("Source", "Config"):
                base = plugin / area
                if base.is_dir():
                    files.extend(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in (".ini", ".cpp", ".h", ".cs"))
    lookup = {package.casefold(): package for package in packages}
    for file in files:
        for number, line in enumerate(file.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
            for token in re.findall(r"/Game/[^\s\"'<>(),;{}\\\[\]]+", line):
                package = token.split(".", 1)[0].split(":", 1)[0].rstrip("/")
                canonical = lookup.get(package.casefold())
                if canonical:
                    result[canonical].append(dict(file=str(file), line=number,
                        source_sha256=sha(file), text=line.strip(),
                        reason="Complete source/config package literal; retained even in an Editor-only creator"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, default=W / "AssetReferences.json")
    args = parser.parse_args()
    assert not (W / "FinalReview.json").exists(), "Accepted stage evidence is immutable"
    references_file = args.references.resolve()
    references = read(references_file)
    assert references["passed"] and references["includes_hard_soft_and_management"]
    refs, dependencies = defaultdict(set), defaultdict(set)
    for row in references["assets"]:
        refs[row["package"]].update(row.get("referencers", []))
        dependencies[row["package"]].update(row.get("dependencies", []))
    copied = read(W / "CopiedPackages.json")
    assert copied["passed"] and copied["all_existing_content_config_unchanged"]
    mapping = copied["package_remapping"]
    restored_file = W / "LegacyCleanupRestored.json"
    restored = read(restored_file)
    restored_paths = {str(Path(row["file"]).resolve()).casefold() for row in restored["restoration"]}
    inputs = {str(path): sha(path) for path in (references_file, W / "CopiedPackages.json", restored_file, Path(__file__).resolve())}

    recipes = (
        ("DoorReuse10", OUTPUTS / "OldTownDoorReuse_20261017/ReusableBlueprints.json",
         OUTPUTS / "OldTownDoorReuse_20261017/ProtectedBefore.json",
         R / "Scripts/BuildAndProbeOldTownReusableDoors.py",
         "/Game/CodexGenerated/OldTown/DoorReuse_20261017/Blueprints/", 10),
        ("CallableLighting19", OUTPUTS / "OldTownCallableLighting_20261016/Applied.json",
         OUTPUTS / "UserLightingReadOnly_20261016/ProtectedBefore.json",
         R / "Scripts/ApplyOldTownCallableLighting.py",
         "/Game/CodexGenerated/OldTown/CallableLighting_20261016/", 19),
        ("FunctionalLighting18", OUTPUTS / "OldTownFunctionalLighting_20261017/Applied.json",
         OUTPUTS / "OldTownFunctionalLighting_20261017/ProtectedBefore.json",
         R / "Scripts/ApplyOldTownFunctionalLighting.py",
         "/Game/CodexGenerated/OldTown/FunctionalLighting_20261017/", 18),
    )
    records, frozen, stage_summaries = [], [], []
    for stage, manifest_file, baseline_file, script_file, scope, expected_count in recipes:
        manifest, baseline = read(manifest_file), read(baseline_file)["file_sha256"]
        assert manifest["passed"] and len(manifest["new_asset_sha256"]) == expected_count
        for file in (manifest_file, baseline_file, script_file):
            inputs[str(file)] = sha(file)
        baseline_paths = {str(Path(file).resolve()).casefold() for file in baseline}
        if stage == "DoorReuse10":
            declared_packages = {row["blueprint"] for row in manifest["groups"]}
        elif stage == "CallableLighting19":
            declared_packages = {scope + "Blueprints/BP_OTS_LightCircuit",
                                 scope + "Materials/M_OTS_Callable_HotelTube",
                                 scope + "Materials/M_OTS_Callable_StreetLens"}
            declared_packages.update(scope + "Materials/Instances/MI_" + row["lamp_actor"] for row in manifest["pairs"])
        else:
            declared_packages = {scope + "Materials/M_OTS_Street03_GlassCallable"}
            declared_packages.update(scope + "Materials/Instances/MI_" + row["lamp_actor"] for row in manifest["pairs"])
        actual_declared = {package_for(file) for file in manifest["new_asset_sha256"]}
        assert actual_declared == declared_packages and len(declared_packages) == expected_count
        stage_records = []
        for file, authored_sha in sorted(manifest["new_asset_sha256"].items()):
            path = Path(file).resolve()
            package = package_for(path)
            assert path.is_relative_to(CONTENT) and path.suffix.lower() == ".uasset" and package.startswith(scope)
            assert str(path).casefold() not in restored_paths, "A restored uncertain material cannot enter this proposal"
            existed_before = str(path).casefold() in baseline_paths
            current_sha = sha(path) if path.is_file() else None
            sidecars = [str(path.with_suffix(extension)) for extension in (".uexp", ".ubulk", ".uptnl", ".m.ubulk", ".upayload") if path.with_suffix(extension).exists()]
            destination = mapping.get(package)
            destination_file = package_file(destination) if destination else None
            copied_sha = copied["new_asset_sha256"].get(str(destination_file)) if destination_file else None
            destination_verified = bool(destination_file and destination_file.is_file()
                                        and copied_sha and sha(destination_file) == copied_sha)
            row = dict(stage=stage, package=package, file=str(path), bytes=path.stat().st_size if path.is_file() else None,
                authored_sha256=authored_sha, current_sha256=current_sha,
                current_bytes_match_authored=current_sha == authored_sha,
                creation_manifest=str(manifest_file), creation_manifest_sha256=inputs[str(manifest_file)],
                creation_hash_field="new_asset_sha256", creation_script=str(script_file),
                creation_script_current_sha256=inputs[str(script_file)],
                creation_time_script_sha_recorded=False,
                creation_scope=scope, exact_output_name_declared_by_stage_recipe=True,
                before_creation_baseline=str(baseline_file), before_creation_baseline_sha256=inputs[str(baseline_file)],
                absent_from_before_creation_baseline=not existed_before,
                cumulative_owned_hash_bag_used=False,
                current_referencers_precommit=sorted(refs[package]),
                source_dependencies=sorted(dependencies[package]),
                mapped_hotel_destination=destination, private_destination_sha256=copied_sha,
                private_destination_exists_with_copy_proof_sha=destination_verified,
                unapproved_sidecars=sidecars, deletion_authorized=False,
                requires_fresh_post_commit_graph=True)
            if existed_before or current_sha != authored_sha or sidecars or not destination_verified:
                row.update(status="FROZEN", reason="Absent-before proof, current authored bytes, sidecar scope or exact named replacement proof failed")
                frozen.append(row)
            else:
                row["status"] = "PROVEN_NEW_BYTES_MATCH_PENDING_POST_COMMIT_REFERENCES"
                records.append(row)
            stage_records.append(row)
        stage_summaries.append(dict(stage=stage, declared_count=expected_count,
            matching_new_ownership_count=sum(row["status"] != "FROZEN" for row in stage_records),
            output_recipe="Explicit generated output names, absent from full pre-creation Content/Config baseline, immediate authored UAsset SHA and exact current bytes"))

    packages = {row["package"] for row in records}
    literals = runtime_source_literals(packages)
    candidates = []
    for row in records:
        row["source_config_literal_roots"] = literals.get(row["package"], [])
        outside = set(refs[row["package"]]) - packages - {ORIGINAL}
        row["precommit_referencers_outside_proposal_or_original"] = sorted(outside)
        if literals.get(row["package"]) or outside:
            row.update(status="RETAINED_EXTERNAL_ROOT", reason="A non-proposal package or source/config literal still refers to this source")
            frozen.append(row)
        else:
            candidates.append(row)
    for row in candidates:
        row["candidate_batch_dependencies"] = sorted(set(row["source_dependencies"]) & {r["package"] for r in candidates})

    old_doors = read(OUTPUTS / "OldTownDoorReuse_20261017/DoorInventory.json")["door_blueprints"]
    window_notes = read(W / "WindowDesignNotes.json")
    protected_packages = set(old_doors) | {p for group in window_notes["window_groups"] for p in group["source_blueprints"]}
    assert len(old_doors) == 15 and len(protected_packages) == 23 and not (protected_packages & packages)
    protected = []
    for package in sorted(protected_packages):
        path = package_file(package)
        referencers = sorted(refs[package])
        v2_refs = [p for p in referencers if "/OldTownVersion2/" in p]
        assert v2_refs and path.is_file(), "Shared V2 source Blueprint must stay present: " + package
        protected.append(dict(package=package, file=str(path), current_sha256=sha(path),
            kind="old_shared_door" if package in old_doors else "old_shared_window",
            referencers=referencers, protected_v2_referencers=v2_refs,
            cleanup_allowed=False, reason="Live OldTownVersion2 asset dependency; preserve original bytes and path"))
    restored_protected = []
    for row in restored["restoration"]:
        path = Path(row["file"])
        restored_protected.append(dict(file=str(path), restored_sha256=row["sha256"],
            current_sha256=sha(path) if path.is_file() else None, cleanup_allowed=False,
            reason="Previously restored because creation provenance was uncertain; explicitly excluded from this proposal"))

    report = dict(passed=True, analysis_only=True, unreal_started=False,
        content_changes_performed=False, deletion_authorized=False,
        generated_utc=datetime.now(timezone.utc).isoformat(),
        references_file=str(references_file), references_map_sha256=references.get("map_sha256"),
        reference_status="PRECOMMIT; current original map intentionally still uses old source packages",
        sources=stage_summaries, proven_creation_records=records,
        candidate_count_pending_fresh_graph=len(candidates), candidates=candidates,
        frozen_or_retained=frozen, frozen_or_retained_count=len(frozen),
        shared_old_door_blueprints_protected=15, shared_old_window_blueprints_protected=8,
        protected_shared_blueprints=protected, restored_uncertain_materials_protected=restored_protected,
        input_sha256=inputs,
        final_gate_requirements=[
            "Commit verified named map and complete a normal-zero-exit fresh full 7986 Actor/Native readback first.",
            "Force disk rescan/export all project hard/soft/searchable/management references against the committed map; compare exact package/file inventory.",
            "Every non-candidate package is a root, including Main, V2, user/unknown assets, all new Hotel copies and any changed hash. Preserve full transitive dependency closure.",
            "Add complete package literals in Source/Plugins/Config and retained package UTF8/UTF16 data as conservative roots; repeat retained dependency/literal closure to a fixed point.",
            "Freeze any current UAsset SHA change, new sidecar or newly found external reference. Candidate-to-candidate references can only be handled as one validated batch.",
            "The Editor-only fixed old BP_OTS_LightCircuit creation path is an external source root and remains retained unless a separate authorized change removes that dependency.",
            "Do not touch the 6 restored uncertain materials, the 15 V2-shared old door BPs or the 8 V2-shared old window BPs.",
            "No delete API, redirector repair or directory deletion. Any later authorized cleanup must isolate exact approved files offline into a fresh Saved backup, with all other bytes verified unchanged.",
        ])
    output = W / "CleanupOwnershipCandidates.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(passed=True, ownership_records=len(records),
        candidates_pending_fresh_graph=len(candidates), frozen_or_retained=len(frozen),
        protected_shared_blueprints=len(protected), output=str(output)), ensure_ascii=False))


if __name__ == "__main__":
    main()
