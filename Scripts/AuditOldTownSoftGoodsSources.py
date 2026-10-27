"""Independent source-only audit; writes only the new stage SourceAudit.json."""
from datetime import datetime, timezone
from pathlib import Path
import json

import VerifyOldTownSoftGoodsRefinement as verifier


def main():
    manifest_file=verifier.ART/"ModelDataManifest.json"
    digest=verifier.sha(manifest_file)
    manifest=verifier.read(manifest_file)
    verifier.require(manifest.get("passed") is True and manifest.get("status")=="READY"
        and len(manifest["variants"])==manifest.get("completed_variant_count")==20,
        "Complete frozen20-model source is not ready; no final SourceAudit is written.")
    previews=manifest.get("source_previews",[])
    verifier.require(len(previews)>=2 and len({p["file"] for p in previews})==len(previews),
        "Final distinct source preview generation has not completed.")
    verifier.require({v["key"]:v["source_asset"] for v in manifest["variants"]}==verifier.expected_selection(),
        "Original20-model selection differs.")
    inputs={str(manifest_file):digest,str(Path(verifier.__file__).resolve()):verifier.sha(verifier.__file__),
            str(Path(__file__).resolve()):verifier.sha(__file__)}
    baseline_file=verifier.WORK/"Baseline.json"
    baseline=verifier.read(baseline_file);verifier.verify_baseline(baseline)
    inputs[str(baseline_file)]=verifier.sha(baseline_file)
    for preview in manifest["source_previews"]:
        verifier.require(verifier.sha(preview["file"])==preview["sha256"],"Final source preview file differs.")
        inputs[preview["file"]]=preview["sha256"]
    verifier.require(verifier.sha(manifest["blend_file"])==manifest["blend_sha256"],"Frozen source blend differs.")
    inputs[manifest["blend_file"]]=manifest["blend_sha256"]
    proofs=[]
    for variant in manifest["variants"]:
        verifier.require(variant.get("passed") is True,"Source variant is incomplete.")
        proof=verifier.source_variant_proof(variant);proofs.append(proof)
        paths=[Path(variant["geometry_recipe_file"]),Path(variant["source_recipe_file"])]
        fbx=Path(variant["fbx_file"])
        if not fbx.is_absolute():fbx=verifier.ART/fbx
        paths.append(fbx)
        for path in paths:inputs[str(path.resolve())]=verifier.sha(path)
        print("SOURCE_VARIANT_PASS",variant["key"],proof["recipe"]["triangles"],flush=True)
    verifier.require(verifier.sha(manifest_file)==digest,"Source manifest changed during the audit; source is not frozen.")
    verifier.hashes(inputs,"Frozen independent source inputs")
    result=dict(schema="OldTownSoftGoodsIndependentSourceAuditV1",passed=True,
        source_map_sha256=baseline["source_map_sha256"],manifest=verifier.reference(manifest_file),
        variant_count=20,component_count=222,source_recipe_binary_fbx_and_float32_all_closed_valid=True,
        original_structural_faces_and_corner_buffers_preserved=True,errors=[],variants=proofs,
        input_sha256=inputs,generated_utc=datetime.now(timezone.utc).isoformat(),
        scope="Source-only verification; actual UE readback and saved map acceptance are separate.")
    output=verifier.WORK/"SourceAudit.json"
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SOURCE_AUDIT_COMPLETE",len(proofs),verifier.sha(output),flush=True)


if __name__=="__main__":
    main()
