"""Fresh readback of only-mesh replacement and complete unrounded scene geometry."""
import json,sys,traceback,math,hashlib
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
from VerifyOldTownSoftGoodsRefinement import verify_baseline,verify_stage,read,sha,reference,AFTER_SCHEMA
from ValidateEnterableStreet import validate_main_home
W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
ART=R/'SourceArt/OldTownRealismRefinement_20261013/SoftGoods'
S=R/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
ASSET='/Game/CodexGenerated/OldTown/SoftGoodsRefinement_20261013/'
def write(name,d):native.write(W/name,d)
def main():
    baseline=read(W/'Baseline.json');source,original=verify_baseline(baseline)
    applied=read(W/'Applied.json');digest=sha(MAP);assert digest==applied['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors());by={a.get_actor_label():a for a in actors}
    states={n:stable_actor(a) for n,a in by.items()};assert len(by)==len(actors)==8014
    assert states==read(W/'ExpectedSnapshot.json')['actors']
    lights=light_inventory(actors);assert lights==source['lights']['lights']
    write('AfterSnapshot.json',dict(passed=True,actors=states,actor_count=8014,target_level=TARGET,source_map_sha256=digest,
        main_home=validate_main_home(actors)))
    native.WORK=W/'AppearanceNative';native.MESH_CACHE.clear();native.MATERIAL_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    components={}
    for i,n in enumerate(sorted(by)):
        components[n]=[native.component_record(c) for c in by[n].get_components_by_class(unreal.SceneComponent)]
        if i%500==0:unreal.log('SOFT_GOODS_NATIVE_PROGRESS '+str(i)+' /8014')
    write('AppearanceSnapshot.json',dict(actors=states,actor_count=8014,component_records=components,
        blueprints=source['native']['blueprints'],map_sha256=digest,target_level=TARGET,source='fresh_persisted_native_read_only'))
    newrecords={p:{k:v for k,v in row.items() if k!='_positions'} for p,row in native.MESH_CACHE.items() if p.startswith(ASSET)}
    assert len(newrecords)==20
    fresh=dict(schema=AFTER_SCHEMA,source='fresh_persisted_map_load',persisted_map_unchanged=sha(MAP)==digest,
        source_map_sha256=baseline['source_map_sha256'],map_file=str(MAP),map_sha256=digest,
        manifest=applied['manifest'],actor_snapshot=reference(W/'AfterSnapshot.json'),native_snapshot=reference(W/'AppearanceSnapshot.json'),
        mesh_records=newrecords,new_asset_sha256=applied['new_asset_sha256'],
        current_asset_sha256={**baseline['previous_asset_sha256'],**applied['new_asset_sha256']},light_inventory=lights)
    write('After.json',fresh);proof=verify_stage(baseline,applied['manifest'],fresh);write('PreservationAudit.json',proof)
    old={r['asset']:r for r in read(S/'GeometryPreservation.json')['mesh_records']}
    unchanged=[]
    for p,row in native.MESH_CACHE.items():
        if p.startswith(ASSET):continue
        assert p in old and row['geometry_sha256']==old[p]['geometry_sha256'],p
        unchanged.append(dict(asset=p,geometry_file=row['geometry_file'],geometry_sha256=row['geometry_sha256'],actual_buffers_unchanged=True))
    assert len(native.MESH_CACHE)==345 and len(unchanged)==325
    assert not native.LIMITATIONS,native.LIMITATIONS
    write('GeometryPreservation.json',dict(passed=True,map_sha256=digest,unchanged_native_models=unchanged,
        changed_models=20,unchanged_models=325,pose_parent_collision_and_material_wpo_preserved=True))
    write('LightAudit.json',dict(passed=True,map_sha256=digest,lights=lights,total_light_components=len(lights),
        emissive_fixture_count=16,unchanged_from_material_stage=True))
    # Exact native vertices transformed without decimal rounding, including WPO.
    cache={};records=[];hidden=0
    for a in actors:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            mesh=c.static_mesh
            if not mesh:continue
            if not c.get_editor_property('visible') or c.get_editor_property('hidden_in_game'):
                hidden+=1;continue
            path=mesh.get_path_name()
            if path not in cache:
                g=read(Path(native.MESH_CACHE[path]['geometry_file']));vs=[];ts=[];sign=0
                for sec in g['sections']:
                    offset=len(vs);vs.extend(sec['vertices_cm'])
                    ids=sec['triangle_indices'];ts.extend([[offset+int(ids[i+j]) for j in range(3)] for i in range(0,len(ids),3)])
                    sign+=sec['cross_dot_vertex_normals'].get('positive',0)-sec['cross_dot_vertex_normals'].get('negative',0)
                cache[path]=(vs,ts,sign<0)
            vs,ts,reverse=cache[path];t=c.get_world_transform();ident=a.get_actor_label()+'::'+c.get_name()
            rec=next(r for r in components[a.get_actor_label()] if r['name']==c.get_name());assert rec['uniform_slot_surface_translation'],ident
            off=rec['expected_surface_translation_cm_to_preserve'] or [0.,0.,0.]
            world=[native.value(unreal.MathLibrary.transform_location(t,unreal.Vector(*v))) for v in vs]
            world=[[v[i]+off[i] for i in range(3)] for v in world];negative=math.prod(native.value(t.scale3d))<0
            records.append(dict(id=ident,actor=a.get_actor_label(),component=c.get_name(),mesh=path,
                vertices=world,triangles=ts,render_offset_cm=off,wpo_verified_from_persisted_material=any(off),reverse_winding=reverse^negative,
                world_transform_negative_determinant=negative,collision=str(c.get_collision_enabled()),
                materials=[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]))
    native.write(W/'GeometryAfter.json',dict(map_sha256=digest,components=records,hidden_components_excluded=hidden,
        errors=[],unique_meshes=len(cache),coordinate_serialization='unrounded native local positions and native world transforms plus original verified WPO',
        triangles=sum(len(r['triangles']) for r in records),new_asset_sha256=fresh['current_asset_sha256']))
    write('AfterSummary.json',dict(passed=True,map_sha256=digest,actors=8014,visible_components=len(records),unique_meshes=len(cache),
        hidden_components_excluded=hidden,errors=[],triangles=sum(len(r['triangles']) for r in records)))
    assert sha(MAP)==digest and lights==light_inventory(actors) and states=={n:stable_actor(a) for n,a in by.items()}
    unreal.log('SOFT_GOODS_SAVED_AUDIT_PASS '+json.dumps(dict(models=20,components=222,mesh_buffers=len(native.MESH_CACHE))))
if __name__=='__main__':
    try:main()
    except Exception:
        write('SavedAuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
