"""Reprove corrected native geometry against every static component in V2."""
from pathlib import Path
import json
from OldTownMainLightingCommon import R,sha,read,write,ref
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016';S=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def main():
    i=read(W/'Input.json');v=read(W/'V2Snapshot.json');after=read(S/'AppearanceSnapshot.json')
    old={n+'::'+c['name']:c for n,cs in after['component_records'].items() for c in cs if c.get('mesh')}
    now={n:c for n,c in i['exact_scene_components'].items() if c.get('mesh')}
    assert set(old)==set(now) and len(now)==12361
    for ident,c in now.items():
        src=old[ident]
        assert c['world_transform']==src['world_pose'] and c['mesh']==src['mesh'],ident
        assert c['parent']==src['parent_path'] and c['local']['mobility']==src['mobility'],ident
        assert all(c['local'][k]==val for k,val in src['relative_pose'].items()),ident
        assert c['materials']==[m['asset'] for m in src['materials']],ident
        assert c['collision']==src['collision_enabled'] and c['collision_profile']==src['collision_profile'],ident
        for k in ('visible','hidden_in_game'):assert c['local'][k]==src['primitive_properties'][k],ident
        for k in ('cast_shadow','evaluate_world_position_offset','world_position_offset_disable_distance'):
            assert c['geometry_properties'][k]==src['primitive_properties'][k],ident
    # All material masters/instances, texture sources, native models and BodySetup
    # bytes used by the prior actual export remain the same; user edits are sky,
    # fog, postprocess, environment controls and the two already matching lights.
    baseline=read(S/'Baseline.json');applied=read(S/'Applied.json')
    files={**baseline['previous_asset_sha256'],**baseline['protected_file_sha256'],**applied['new_asset_sha256']}
    ignored=[];user_blueprint_changes=[]
    for p,h in files.items():
        if Path(p).suffix=='.umap':ignored.append(p);continue
        current_sha=sha(p)
        if current_sha!=h:
            # The user explicitly changed this pickup Blueprint after Stage3.
            # Its current constructed static components were compared above;
            # none added, removed or moved geometry. Preserve its new bytes.
            assert Path(p).resolve()==(R/'Content/Yastar/Items/BP_ItemPickup.uasset').resolve(),p
            assert i['referenced_game_package_sha256'][p]==current_sha,p
            user_blueprint_changes.append(dict(file=p,before_sha256=h,current_sha256=current_sha,
                reason='User-edited Blueprint adopted; all current constructed mesh components exactly match exported geometry.'))
    assert read(S/'PreservationAudit.json')['passed'] and read(S/'SourceAudit.json')['passed']
    summary=read(S/'AfterSummary.json');assert summary['passed'] and summary['visible_components']==8719
    assert v['raw_visible_instance_triangles']==summary['triangles']==9281596
    source=S/'GeometryAfter.json';source_ref=ref(source)
    proof=dict(passed=True,target_level=v['target_level'],map_sha256=v['map_sha256'],
        source_native_geometry=source_ref,source_native_appearance=ref(S/'AppearanceSnapshot.json'),
        source_native_preservation=ref(S/'PreservationAudit.json'),source_audit=ref(S/'SourceAudit.json'),
        source_overlap_correction=ref(S/'OverlapCorrection.json'),fresh_user_input=ref(W/'Input.json'),fresh_v2_snapshot=ref(W/'V2Snapshot.json'),
        static_mesh_components_compared_exactly=12361,visible_components=8719,triangles=9281596,
        unchanged_geometry_asset_files=len(files)-len(ignored)-len(user_blueprint_changes),map_files_excluded_as_authorized_user_changes=ignored,
        adopted_user_blueprint_changes_without_static_geometry_change=user_blueprint_changes,
        source_unrounded_world_pose_parent_mesh_material_collision_visibility_and_WPO_asset_bytes_equal=True,
        derivation='Reuse actual corrected native vertex buffers only after exact current-world component and asset invariance proof; this is not a new native mesh export.')
    write(W/'GeometryDerivation.json',proof)
    header=(json.dumps(dict(geometry_derivation=ref(W/'GeometryDerivation.json')),ensure_ascii=False,separators=(',',':'))[:-1]+',').encode('utf-8')
    token=('"map_sha256":"'+summary['map_sha256']+'"').encode();replacement=('"map_sha256":"'+v['map_sha256']+'"').encode()
    dest=W/'GeometryCurrentV2.json'
    with source.open('rb') as src,dest.open('wb') as out:
        prefix=src.read(256);assert prefix.startswith(b'{') and token in prefix
        out.write(header);out.write(prefix[1:].replace(token,replacement,1))
        for block in iter(lambda:src.read(4*1024*1024),b''):out.write(block)
    assert sha(source)==source_ref['sha256']
    write(W/'AfterSummary.json',dict(passed=True,map_sha256=v['map_sha256'],actors=v['actor_count'],visible_components=8719,
        unique_meshes=344,hidden_components_excluded=3642,errors=[],triangles=9281596,geometry_derivation=ref(W/'GeometryDerivation.json')))
    write(W/'GeometryReady.json',dict(passed=True,geometry=ref(dest),derivation=ref(W/'GeometryDerivation.json'),map_sha256=v['map_sha256']))
    print('CURRENT_V2_GEOMETRY_REPROVEN',12361,8719,9281596,flush=True)
if __name__=='__main__':main()
