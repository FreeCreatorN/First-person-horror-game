"""Import to owned unused packages and measure packing error; never save a map."""
import sys
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import ApplyOldTownSoftGoodsRefinement as build
import VerifyOldTownSoftGoodsRefinement as verifier
def main():
    baseline=verifier.read(build.W/'Baseline.json');_,original=verifier.verify_baseline(baseline)
    manifest_ref=verifier.reference(build.ART/'ModelDataManifest.json');manifest=verifier.read(build.ART/'ModelDataManifest.json')
    digest=verifier.sha(build.MAP);assert digest==baseline['source_map_sha256'] and not (build.W/'Applied.json').exists()
    build.importer.ASSET=build.ASSET;build.pbr.ASSET=build.ASSET;build.native.WORK=build.W/'ProbeNative'
    build.native.MESH_CACHE.clear();build.native.MATERIAL_CACHE.clear();build.native.SOURCE_FILES.clear();build.native.LIMITATIONS.clear()
    axes=verifier.read(R/'Saved/CodexOutputs/OldTownRealism_20261012/AxisVerification.json')
    # This deliberately broad diagnostic compares every unchanged oriented face.
    # It grants no acceptance: production budgets are restored before returning.
    rigid=build.structural_native_proof;budget=verifier.FRAME_BUDGET
    def measure(before,after,roles):
        verifier.FRAME_BUDGET=.01
        try:
            result=rigid(before,after,roles);result['diagnostic_only']=True;return result
        finally:verifier.FRAME_BUDGET=budget
    build.structural_native_proof=measure;rows=[]
    for variant in manifest['variants']:
        _,record,proof=build.build_variant(variant,original[variant['source_asset']],axes)
        rows.append(dict(key=variant['key'],asset=record['asset'],native_geometry=verifier.reference(record['geometry_file']),
            original_native_geometry=verifier.reference(original[variant['source_asset']]['geometry_file']),
            diagnostic=proof['rigid_structure']))
        unreal.log('SOFT_GOODS_NATIVE_CORNER_PROBE '+variant['key'])
    assert verifier.reference(build.ART/'ModelDataManifest.json')==manifest_ref and verifier.sha(build.MAP)==digest
    build.hashes({**baseline['previous_asset_sha256'],**baseline['protected_file_sha256']})
    build.write('NativeCornerProbe.json',dict(diagnostic_only=True,source_map_sha256=digest,manifest=manifest_ref,
        map_save_requested=False,components_replaced=0,rows=rows,production_budget_unchanged=verifier.FRAME_BUDGET==budget))
    unreal.log('SOFT_GOODS_NATIVE_CORNER_PROBE_COMPLETE 20 no map save')
if __name__=='__main__':main()
