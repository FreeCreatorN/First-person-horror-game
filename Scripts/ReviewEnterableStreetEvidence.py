"""Check saved reports and fresh PNG artifacts without launching UE."""
import hashlib
import json
from pathlib import Path
import struct

project = Path(__file__).resolve().parents[1]
output = project / "Saved/CodexOutputs/EnterableStreet_20261002"
map_file = project / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
map_hash = hashlib.sha256(map_file.read_bytes()).hexdigest()


def read(name):
    return json.loads((output / name).read_text(encoding="utf-8-sig"))


build, saved, furniture, player = [read(n) for n in
    ("BuildReport.json", "SavedVerification.json", "FurnitureAudit.json", "PlayerCapsule.json")]
assert build["status"] == "PASS" and saved["passed"] and furniture["passed"]
assert map_hash == build["map_sha256"] == saved["map_sha256"]
assert player["radius_cm"] == saved["collision"]["capsule_radius_cm"]
assert player["half_height_cm"] * 2 <= saved["collision"]["capsule_height_cm"]
assert player["max_step_height_cm"] == saved["collision"]["step_up_clearance_cm"]
cameras = (tuple(build['detail_review_cameras']) if build.get('detail_review_cameras') else
          (tuple(build['architecture_review_cameras']) if build.get('architecture_review_cameras') else
          (tuple(build['cleanup_review_cameras']) if build.get('cleanup_review_cameras') else
           (("CAM_Revision_TableHuman", "CAM_Revision_AlleyHuman", "CAM_Revision_StairClosed",
            "CAM_Revision_EntranceFlush", "CAM_Revision_BedHuman", "CAM_Revision_RoadPlan")
           if build.get("furniture_manifest") else
           ("CAM_OTS_Hero", "CAM_OTS_MainHome", "CAM_Enterable_ShopEntry",
            "CAM_Enterable_SchoolEntry", "CAM_Enterable_Stair", "CAM_Enterable_Bedroom")))))
captures = []
for camera in cameras:
    metadata = read("Renders/" + camera + ".json")
    path = output / "Renders" / (camera + ".png")
    data = path.read_bytes()
    assert metadata["status"] == "PASS" and metadata["camera"] == camera
    assert metadata["map_sha256"] == map_hash
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    dimensions = struct.unpack(">II", data[16:24])
    assert dimensions == (1280, 720) and len(data) == metadata["bytes"]
    captures.append({"camera": camera, "path": str(path), "dimensions": list(dimensions),
                     "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     "view_mode_requested": metadata.get('view_mode_requested','lit'),
                     "view_mode_verified": metadata.get('view_mode_verified'),
                     "map_sha256": metadata["map_sha256"]})
original_hash = hashlib.sha256((project / "Content/Yastar/Maps/Blockout/L_Chapter01_Blockout.umap").read_bytes()).hexdigest()
assert original_hash == "d15f1749800233495469acb72e60a7c0d837319eecf57fb14bff25fdbbd9de09"
revision_audit = read("RevisionAudit.json") if build.get("furniture_manifest") else None
if revision_audit is not None:
    assert revision_audit["passed"]
cleanup_audit = read('LightingCleanupAudit.json') if build.get('lighting_cleanup') else None
if cleanup_audit is not None:
    assert cleanup_audit['passed']
architecture_audit = read('ArchitectureSealAudit.json') if build.get('architecture_seal') else None
if architecture_audit is not None:
    assert architecture_audit['passed']
    assert all(c['view_mode_verified'] in ('lit','unlit') for c in captures)
detail_audit = read('DetailPolishAudit.json') if build.get('detail_polish') else None
if detail_audit is not None:
    assert detail_audit['passed'] and detail_audit['map_sha256'] == map_hash
triangle_audit = read('DetailTriangleAudit.json') if build.get('detail_polish') else None
if triangle_audit is not None:
    assert triangle_audit['passed'] and triangle_audit['map_sha256'] == map_hash
for path, expected_hash in build.get("protected_map_sha256", {}).items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected_hash
report = {"scene_and_capture_artifacts_passed": True, "map_sha256": map_hash,
          "original_blockout_sha256": original_hash, "player_capsule": player,
          "saved_scene_statistics": saved["statistics"], "furniture_statistics": furniture["statistics"],
          "capture_count": len(captures), "captures": captures,
          "revision_audit_statistics": revision_audit["statistics"] if revision_audit else None,
          "lighting_cleanup_statistics": cleanup_audit['statistics'] if cleanup_audit else None,
          "architecture_statistics": architecture_audit['statistics'] if architecture_audit else None,
          "detail_statistics": detail_audit['statistics'] if detail_audit else None,
          "imported_triangle_statistics": triangle_audit['statistics'] if triangle_audit else None,
          "capture_process_exit_check": read("CaptureRuns.json"),
          "limitations": ["Capture-only helpers may need bounded cleanup after PNG completion; map and image hashes are independently checked.",
                          "Collision sampling is not a real-time player traversal or AI navigation test."]}
(output / "FinalReview.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("OTS_FINAL_ARTIFACT_REVIEW_PASS captures=" + str(len(captures)))
