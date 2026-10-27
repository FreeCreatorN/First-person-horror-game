"""Pure positive/negative tests of the real frozen native-closure stage.

Only the test report is written. Negative evidence is supplied in memory; no
maps, assets, original reports, source art or UE processes are changed.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import json

import FinalizeOldTownRealism as f


def main():
    original_read, original_sha = f.read, f.sha
    read_cache, hash_cache, file_stats = {}, {}, {}
    def actual_read(path):
        key = str(Path(path).resolve())
        if key not in read_cache:
            read_cache[key] = original_read(path)
        return read_cache[key]
    def actual_sha(path):
        key = str(Path(path).resolve())
        if key not in hash_cache:
            p = Path(key)
            before = p.stat()
            hash_cache[key] = original_sha(p)
            after = p.stat()
            assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            file_stats[key] = (after.st_size, after.st_mtime_ns)
        return hash_cache[key]
    cases = []
    def positive(name, callback):
        result = callback()
        cases.append(dict(name=name, passed=True, expected="accepted", actual="accepted"))
        print("PASS", name, flush=True)
        return result
    def negative(name, callback, marker=None):
        try:
            callback()
        except (RuntimeError, AssertionError, KeyError, ValueError, IndexError) as error:
            message = str(error)
            if marker is not None:
                assert marker in message, (name, marker, message)
            cases.append(dict(name=name, passed=True, expected="rejected", actual="rejected", reason=message))
            print("PASS", name, flush=True)
            return
        raise AssertionError("Invalid evidence was accepted: " + name)
    with patch.object(f, "read", actual_read), patch.object(f, "sha", actual_sha):
        build = actual_read(f.WORK / "BuildReport.json")
        inp = f.whole_map_input(actual_read(f.WORK / "RealismInput.json"), actual_read(f.WORK / "RealismStreetInput.json"))
        apply = actual_read(f.WORK / "RealismApply.json")
        applied = actual_read(f.WORK / "Applied.json")
        digest = actual_sha(f.MAP)
        proof = positive("actual_905_to_927_full_stage_chain", lambda: f.verify_appearance_stage_chain(build, inp, apply, applied, digest))[-1]
        assert len(proof["actual_binary_source_face_bijections"]) == 22
        original_report = build["model_closure_import_repairs"]
        report_path = str((f.WORK / "ModelClosureImportRepairs.json").resolve())
        def reject_report(name, change, marker):
            fake = deepcopy(original_report)
            change(fake)
            fake_build = deepcopy(build)
            fake_build["model_closure_import_repairs"] = fake
            def altered_read(path):
                return fake if str(Path(path).resolve()) == report_path else actual_read(path)
            with patch.object(f, "read", altered_read):
                negative(name, lambda: f.verify_model_closure_import_repairs(fake_build, inp, apply, applied, digest), marker)
        reject_report("reject_extra_component_change", lambda r:r.update(components_or_actors_changed=1), "22/880 scope")
        reject_report("reject_false_map_preservation", lambda r:r.update(map_unchanged=False), "22/880 scope")
        reject_report("reject_duplicate_target", lambda r:r["rows"].__setitem__(1,deepcopy(r["rows"][0])), "duplicated")
        reject_report("reject_omitted_source_package", lambda r:r["source_asset_sha256"].pop(next(iter(r["source_asset_sha256"]))), "source asset manifest")
        reject_report("reject_omitted_frozen_report", lambda r:r["frozen_report_sha256"].pop(next(iter(r["frozen_report_sha256"]))), "frozen report list")
        reject_report("reject_changed_material_slot", lambda r:r["rows"][0]["after_native"]["static_material_slots"][0].update(slot_name="WrongRole"), "Native buffers, slots")
        reject_report("reject_wrong_recovered_face_count", lambda r:r["rows"][0].update(recovered_triangles=0), "Recovered face counts")
        reject_report("reject_degenerate_merging_enabled", lambda r:r["rows"][0].update(copy_remove_degenerates=True), "import settings/envelope")
        reject_report("reject_nonboolean_uv_chart_flag", lambda r:r["rows"][0].update(uv_chart_separation="False"), "import settings/envelope")
        reject_report("reject_report_selected_positive_winding", lambda r:r["rows"][0]["frames"].update(expected_corner_normal_sign=1), "Native buffers, slots")
        bad_apply = deepcopy(apply)
        bad_apply["closure_extra_component"] = "unapproved"
        negative("reject_changed_apply_document", lambda:f.verify_model_closure_import_repairs(build, inp, bad_apply, applied, digest), "application or expected state")
        negative("reject_current_927_as_historical_followup_input", lambda:f.verify_followup_surface_repairs(build, inp, apply, applied, digest))
        row = original_report["rows"][0]
        geometry = actual_read(row["after_native"]["geometry_file"])
        recipe = actual_read(row["source_recipe_file"])
        positive("actual_recovered_mesh_clockwise_frames", lambda:f.native_frame_proof(geometry))
        positive("actual_recovered_mesh_closed_topology", lambda:f.native_closed_solid(geometry))
        positive("actual_recovered_binary_source_face_and_role_bijection", lambda:f.native_binary_source_face_proof(geometry, row["after_native"], recipe, Path(row["source_fbx_file"])))
        section = next(i for i,s in enumerate(geometry["sections"]) if s["triangle_indices"])
        vertex = geometry["sections"][section]["triangle_indices"][0]
        bad = deepcopy(geometry)
        bad["sections"][section]["normals"][vertex] = [-v for v in bad["sections"][section]["normals"][vertex]]
        negative("reject_flipped_actual_corner_normal", lambda:f.native_frame_proof(bad), "normals/tangents/UV")
        bad = deepcopy(geometry)
        bad["sections"][section]["tangents"][vertex]["tangent_x"] = [0,0,0]
        negative("reject_zero_actual_tangent", lambda:f.native_frame_proof(bad), "normals/tangents/UV")
        bad = deepcopy(geometry)
        tri = bad["sections"][section]["triangle_indices"][:3]
        for index in tri:
            bad["sections"][section]["uv0"][index] = [0,0]
        negative("reject_collapsed_actual_uv_triangle", lambda:f.native_frame_proof(bad), "normals/tangents/UV")
        bad = deepcopy(geometry)
        del bad["sections"][section]["triangle_indices"][:3]
        negative("reject_missing_actual_face", lambda:f.native_closed_solid(bad), "mesh is open")
        bad = deepcopy(geometry)
        indices = bad["sections"][section]["triangle_indices"]
        indices[1],indices[2] = indices[2],indices[1]
        negative("reject_reversed_actual_face", lambda:f.native_binary_source_face_proof(bad,row["after_native"],recipe,Path(row["source_fbx_file"])), "oriented faces or material")
        bad = deepcopy(geometry)
        bad["sections"][section]["material_slot_index"] = (bad["sections"][section]["material_slot_index"]+1)%len(row["after_native"]["static_material_slots"])
        negative("reject_reassigned_actual_face_material", lambda:f.native_binary_source_face_proof(bad,row["after_native"],recipe,Path(row["source_fbx_file"])), "oriented faces or material")
        bad = deepcopy(geometry)
        bad["sections"][section]["vertices_cm"][vertex][0] += .001
        negative("reject_changed_actual_source_coordinate", lambda:f.native_binary_source_face_proof(bad,row["after_native"],recipe,Path(row["source_fbx_file"])), "source coordinate")
    for key, expected in file_stats.items():
        current = Path(key).stat()
        assert (current.st_size,current.st_mtime_ns) == expected, "Input changed during pure tests: "+key
    for path in (Path(__file__),Path(f.__file__),f.ROOT/"Scripts/AuditOldTownRealismAppearance.py"):
        hash_cache[str(path.resolve())] = original_sha(path)
    report = dict(schema="OldTownRealismModelClosureStageContractTestsV1", passed=True,
        generated_utc=datetime.now(timezone.utc).isoformat(), map_sha256=digest,
        test_count=len(cases), tests=cases, input_sha256=hash_cache,
        actual_stage_proof=proof, assets_maps_and_original_reports_unchanged=True,
        negative_evidence_only_in_memory=True)
    output = f.WORK/"ModelClosureStageContractTests.json"
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMPLETE",len(cases),original_sha(output),flush=True)


if __name__ == "__main__":
    main()
