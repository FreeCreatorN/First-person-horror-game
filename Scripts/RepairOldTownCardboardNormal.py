"""Rebuild only the two owned Cardboard masters, without loading/saving a map.

World plain material normals must use VertexNormalWS with tangent space off;
UV plain normals remain (0,0,1) in tangent space. Existing material instances,
textures, meshes, original packages and map/report appearance refs stay intact.
Run only with the root agent's UE helper after the wardrobe UV repair.
"""
import json
from pathlib import Path
import shutil
import sys
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "Scripts"))
import OldTownRealismMaterials as pbr

WORK = ROOT / "Saved/CodexOutputs/OldTownRealism_20261012"
MAP = ROOT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
MAP_SHA = "6025a94eb391fb43d09cc4972ce3d7c8192b7e712578155d517a00b035caeb43"
OWNED = ROOT / "Content/CodexGenerated/OldTown/Realism_20261012"
LOG = WORK / "CardboardNormalRepair.stdout.log"
TARGETS = {mode: pbr.ASSET + "/Materials/M_R_Cardboard_" + mode + ".M_R_Cardboard_" + mode
           for mode in ("UV", "World")}


def read(name):
    return json.loads((WORK / name).read_text(encoding="utf-8-sig"))


def write(name, data):
    path = WORK / name
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


def merge_hashes(destination, incoming):
    for path, digest in incoming.items():
        path = str(Path(path).resolve())
        assert path not in destination or destination[path] == digest, ("Conflicting input SHA", path)
        destination[path] = digest


def check_hashes(values, label):
    for path, digest in values.items():
        assert Path(path).is_file() and pbr.sha(path) == digest, (label, path)


def main():
    build = read("BuildReport.json")
    material = read("MaterialBuild.json")
    assert build["map_sha256"] == pbr.sha(MAP) == MAP_SHA
    assert material.get("passed") is True and pbr.SPEC["Cardboard"][0] is None
    assert material.get("physical_uv_cm_per_unit") == 100.
    originals = {}
    for name in ("RealismInput.json", "RealismStreetInput.json"):
        inventory = read(name)
        for field in ("source_asset_file_sha256", "original_400_shared_asset_sha256"):
            merge_hashes(originals, inventory[field])
    # The street read binds the latest accepted protected MainHome save.
    merge_hashes(originals, read("RealismStreetInput.json")["protected_map_sha256"])
    check_hashes(originals, "Original/protected input changed before Cardboard repair")
    old_assets = material["assets"]
    assert len(old_assets) == len({row["asset"] for row in old_assets})
    old_by_asset = {row["asset"]: row for row in old_assets}
    assert all(asset in old_by_asset and unreal.EditorAssetLibrary.does_asset_exist(asset)
               for asset in TARGETS.values()), "Only existing registered Cardboard masters may be rebuilt"
    texture_files, texture_sources = {}, {}
    for row in old_assets:
        if row.get("kind") != "texture":
            continue
        merge_hashes(texture_files, {row["file"]: row["sha256"]})
        source = row.get("source_file") or row.get("source")
        assert source, ("Texture source is absent", row["asset"])
        merge_hashes(texture_sources, {source: row["source_sha256"]})
    check_hashes(texture_files, "Texture package changed before Cardboard repair")
    check_hashes(texture_sources, "Texture source changed before Cardboard repair")
    all_owned = {str(path.resolve()): pbr.sha(path) for path in OWNED.rglob("*") if path.is_file()}
    manifest_owned = {str(Path(path).resolve()): digest for path, digest in build["new_asset_sha256"].items()
                      if Path(path).resolve().is_relative_to(OWNED.resolve())}
    assert all_owned == manifest_owned, "Build owned package hashes must be current before this targeted repair"
    target_files = {str(Path(old_by_asset[asset]["file"]).resolve()) for asset in TARGETS.values()}
    assert len(target_files) == 2 and all(Path(path).is_relative_to(OWNED.resolve()) for path in target_files)
    backup = WORK / "BeforeCardboardNormal"
    backup.mkdir(exist_ok=True)
    for name in ("BuildReport.json", "MaterialBuild.json"):
        target = backup / name
        if not target.exists():
            shutil.copy2(WORK / name, target)
    for path in target_files:
        target = backup / (Path(path).name + ".bak")
        if not target.exists():
            shutil.copy2(path, target)
    start = len(pbr._report)
    normal_proof = {}
    # Do not initialize scanned textures: neither of these plain masters uses one.
    for mode, asset in TARGETS.items():
        pbr._cache.pop(("Cardboard", mode), None)
        master = pbr.master("Cardboard", mode)
        assert master.get_path_name() == asset
        tangent = master.get_editor_property("tangent_space_normal")
        assert tangent == (mode == "UV")
        normal = unreal.MaterialEditingLibrary.get_material_property_input_node(master, unreal.MaterialProperty.MP_NORMAL)
        expected = unreal.MaterialExpressionConstant3Vector if mode == "UV" else unreal.MaterialExpressionVertexNormalWS
        assert isinstance(normal, expected), (asset, normal.get_class().get_path_name())
        if mode == "UV":
            value = normal.get_editor_property("constant")
            assert [value.r, value.g, value.b] == [0., 0., 1.]
        normal_proof[asset] = dict(tangent_space_normal=tangent, normal_class=normal.get_class().get_path_name())
    rebuilt = pbr._report[start:]
    assert len(rebuilt) == 2 and {row["asset"] for row in rebuilt} == set(TARGETS.values())
    assert all(row["kind"] == "master" and row["role"] == "Cardboard" and row["scan"] is None for row in rebuilt)
    after_owned = {str(path.resolve()): pbr.sha(path) for path in OWNED.rglob("*") if path.is_file()}
    assert set(after_owned) == set(all_owned), "Targeted repair added or removed an owned file"
    assert all(after_owned[path] == digest for path, digest in all_owned.items() if path not in target_files), \
        "Targeted repair changed another mesh/material/instance/texture"
    assert pbr.sha(MAP) == MAP_SHA, "Material repair unexpectedly changed the persisted map"
    check_hashes(originals, "Original/protected input changed during Cardboard repair")
    check_hashes(texture_files, "Texture package changed during Cardboard repair")
    check_hashes(texture_sources, "Texture source changed during Cardboard repair")
    for row in rebuilt:
        assert pbr.sha(row["file"]) == row["sha256"]
        old_by_asset[row["asset"]] = row
        build["new_asset_sha256"][str(Path(row["file"]).resolve())] = row["sha256"]
    material["assets"] = [old_by_asset[row["asset"]] for row in old_assets]
    logs = material.get("final_compile_logs", [])
    if isinstance(logs, str):
        logs = [logs]
    if str(LOG) not in logs:
        logs.append(str(LOG))
    material["final_compile_logs"] = logs
    write("MaterialBuild.json", material)
    write("BuildReport.json", build)
    write("CardboardNormalRepair.json", dict(schema="OldTownCardboardNormalRepairV1", passed=True,
        map_sha256=MAP_SHA, map_sha256_after=pbr.sha(MAP), persisted_map_unchanged=True,
        rebuilt_master_assets=TARGETS, actual_normal_connections=normal_proof,
        changed_owned_file_sha256={path: after_owned[path] for path in sorted(target_files)},
        unchanged_owned_files=len(all_owned) - 2, texture_asset_sha256=texture_files,
        texture_source_sha256=texture_sources, original_input_sha256=originals,
        material_source_script_sha256=pbr.sha(ROOT / "Scripts/OldTownRealismMaterials.py"),
        helper_script_sha256=pbr.sha(__file__), final_compile_log=str(LOG),
        no_texture_initialization=True, map_load_or_save_requested=False))
    assert pbr.sha(MAP) == MAP_SHA
    unreal.log("CARDBOARD_NORMAL_REPAIR_PASS " + MAP_SHA + " masters=2 other_owned_files_unchanged=" + str(len(all_owned) - 2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write("CardboardNormalRepairFailure.json", dict(passed=False, error=traceback.format_exc(),
            map_sha256=pbr.sha(MAP), map_expected_sha256=MAP_SHA))
        raise
