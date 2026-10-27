"""Independent, read-only fresh-load native preservation and material audit."""
import json,sys,traceback,re,hashlib,math
from pathlib import Path
from copy import deepcopy
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor,light_inventory,expression_nodes
from VerifyOldTownRealismRefinement import verify_baseline,verify_stage,reference,sha,AFTER_SCHEMA
from ValidateEnterableStreet import validate_main_home
W=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
ASSET='/Game/CodexGenerated/OldTown/RealismRefinement_20261013/'
edit=unreal.MaterialEditingLibrary
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(name,d):native.write(W/name,d)
def main():
    baseline=read(W/'Baseline.json');source=verify_baseline(baseline)
    applied=read(W/'Applied.json');plan=read(W/'ApprovedPlan.json');digest=sha(MAP)
    assert digest==applied['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by={a.get_actor_label():a for a in actors};assert len(actors)==len(by)==8014
    states={n:stable_actor(a) for n,a in by.items()}
    assert states==read(W/'ExpectedSnapshot.json')['actors'],'Persisted state differs from exact approved changes.'
    lights=light_inventory(actors);assert lights==read(W/'LightInput.json')['lights']
    actor_report=dict(passed=True,actors=states,actor_count=8014,target_level=TARGET,source_map_sha256=digest,
        main_home=validate_main_home(actors),protected_map_sha256={p:h for p,h in baseline['protected_file_sha256'].items() if p.endswith('.umap')})
    write('AfterSnapshot.json',actor_report)
    native.WORK=W/'AppearanceNative';native.MESH_CACHE.clear();native.MATERIAL_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    components={}
    for i,n in enumerate(sorted(by)):
        components[n]=[native.component_record(c) for c in by[n].get_components_by_class(unreal.SceneComponent)]
        if i%500==0:unreal.log('REFINEMENT_NATIVE_PROGRESS '+str(i)+' / 8014')
    snapshot=dict(actors=states,actor_count=8014,component_records=components,
        blueprints=source['native']['blueprints'],map_sha256=digest,target_level=TARGET,source='fresh_persisted_native_read_only')
    write('AppearanceSnapshot.json',snapshot)
    fresh=dict(schema=AFTER_SCHEMA,source='fresh_persisted_map_load',persisted_map_unchanged=sha(MAP)==digest,
        source_map_sha256=baseline['source_map_sha256'],map_file=str(MAP),map_sha256=digest,
        approved_plan=reference(W/'ApprovedPlan.json'),actor_snapshot=reference(W/'AfterSnapshot.json'),
        native_snapshot=reference(W/'AppearanceSnapshot.json'),new_asset_sha256=plan['new_asset_sha256'],mesh_records={})
    write('After.json',fresh)
    preservation=verify_stage(baseline,plan,fresh)
    build=read(W/'MaterialBuild.json');proofs=[]
    for row in build['assets']:
        obj=unreal.load_asset(row['asset']);record=native.material_record(obj)
        assert record['effective_surface_translation_cm']==row.get('values',{}).get('CodexSurfaceTranslationCM_20261009',[0.,0.,0.])
        if row['kind']=='instance':
            actual=record['effective_instance_parameters']
            for name,v in row['values'].items():
                if isinstance(v,list):assert max(abs(x-y) for x,y in zip(v,actual['vector'][name]))<.00015,(row['asset'],name)
                else:assert abs(float(v)-actual['scalar'][name])<.00015,(row['asset'],name)
        else:
            base=record['chain'][-1];graph=base['connected_graph_nodes'];outputs=base['property_inputs']
            for prop in ('MP_BASE_COLOR','MP_NORMAL','MP_ROUGHNESS','MP_WORLD_POSITION_OFFSET'):assert outputs[prop]['node']
            wpo=graph[outputs['MP_WORLD_POSITION_OFFSET']['node']]
            assert wpo['class_path']=='/Script/Engine.MaterialExpressionVectorParameter'
            assert wpo['properties']['parameter_name']=='CodexSurfaceTranslationCM_20261009'
            assert wpo['properties']['default_value'][:3]==[0.,0.,0.]
            assert base['properties']['always_evaluate_world_position_offset'] is True
            assert base['properties']['max_world_position_offset_displacement']==1.
            glowing=bool(outputs['MP_EMISSIVE_COLOR']['node'])
            assert glowing==(row['kind']=='emissive_master')
            detail=[]
            for node in expression_nodes(obj):
                detail.append(dict(class_path=node.get_class().get_path_name(),object_path=node.get_path_name(),
                    inputs=[native.path_of(x) for x in edit.get_inputs_for_material_expression(obj,node)],
                    names=list(edit.get_material_expression_input_names(node)),properties=native.props(node,[
                        'r','g','b','a','constant','parameter_name','default_value','world_position_shader_offset',
                        'transform_source_type','transform_type','noise_function','scale','levels','quality','output_min','output_max','const_alpha'])))
            proofs.append(dict(asset=row['asset'],category=row.get('category',row.get('fixture')),emissive=glowing,
                wpo_is_original_single_constant_parameter=True,graph=detail,texture_paths=[r['asset'] for r in base['used_textures']]))
    assert len(proofs)==14 and sum(r['emissive'] for r in proofs)==2
    meshproofs=[]
    for path,r in native.MESH_CACHE.items():
        oldfile=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012/AppearanceNative/NativeMeshes'/(unreal.load_asset(path).get_name()+'_'+hashlib.sha256(path.encode()).hexdigest()[:10]+'.json')
        assert oldfile.exists() and r['geometry_sha256']==sha(oldfile),path
        assert r['sha256']=={**baseline['previous_asset_sha256'],**baseline['protected_file_sha256']}[r['file']],path
        meshproofs.append(dict(asset=path,file=r['file'],sha256=r['sha256'],geometry_file=r['geometry_file'],
            geometry_sha256=r['geometry_sha256'],source_geometry_file=str(oldfile),source_geometry_sha256=sha(oldfile),actual_buffers_unchanged=True))
    assert len(meshproofs)==345
    assert all(sha(p)==h for p,h in {**baseline['previous_asset_sha256'],**baseline['protected_file_sha256'],**plan['new_asset_sha256']}.items())
    assert sha(MAP)==digest and lights==light_inventory(actors) and states=={n:stable_actor(a) for n,a in by.items()}
    write('MaterialNativeAudit.json',dict(passed=True,map_sha256=digest,masters=proofs,
        instances=sum(r['kind']=='instance' for r in build['assets']),materials=native.MATERIAL_CACHE,
        lamp_bindings=plan['lamp_bindings'],all_actual_light_photometry_color_direction_and_positions_preserved=True,
        source_package_files_unchanged=True,persisted_map_unchanged=True))
    write('GeometryPreservation.json',dict(passed=True,map_sha256=digest,mesh_records=meshproofs,
        component_poses_parents_collision_envelopes_and_material_wpo_exact=True,mesh_changes=0,
        preexisting_user_pickup=baseline.get('preexisting_actor_reload_change'),
        note='Source pickup mesh is absent after the pre-stage user Blueprint edit; all 345 native meshes (344 rendered, 1 hidden collision stair) have identical native buffers.'))
    write('PreservationAudit.json',preservation)
    write('LightAudit.json',dict(passed=True,map_sha256=digest,lights=lights,total_light_components=len(lights),
        emissive_fixture_count=16,unchanged_from_actual_pre_write_input=True,bindings=plan['lamp_bindings']))
    # Fresh, unrounded full-world render vertices, including the exact slot WPO.
    cache={};records=[];hidden=0
    for a in actors:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            mesh=c.static_mesh
            if not mesh:continue
            if not c.get_editor_property('visible') or c.get_editor_property('hidden_in_game'):
                hidden+=1;continue
            path=mesh.get_path_name()
            if path not in cache:
                g=read(native.MESH_CACHE[path]['geometry_file']);vs=[];ts=[];sign=0
                for sec in g['sections']:
                    offset=len(vs);vs.extend(sec['vertices_cm'])
                    ids=sec['triangle_indices'];ts.extend([[offset+int(ids[i+j]) for j in range(3)] for i in range(0,len(ids),3)])
                    sign+=sec['cross_dot_vertex_normals'].get('positive',0)-sec['cross_dot_vertex_normals'].get('negative',0)
                cache[path]=(vs,ts,sign<0)
            vs,ts,reverse=cache[path];t=c.get_world_transform();ident=a.get_actor_label()+'::'+c.get_name()
            rec=next(r for r in components[a.get_actor_label()] if r['name']==c.get_name())
            assert rec['uniform_slot_surface_translation'],ident
            offset=rec['expected_surface_translation_cm_to_preserve'] or [0.,0.,0.]
            world=[native.value(unreal.MathLibrary.transform_location(t,unreal.Vector(*v))) for v in vs]
            world=[[v[i]+offset[i] for i in range(3)] for v in world]
            negative=math.prod(native.value(t.scale3d))<0
            records.append(dict(id=ident,actor=a.get_actor_label(),component=c.get_name(),mesh=path,
                vertices=world,triangles=ts,render_offset_cm=offset,wpo_verified_from_persisted_material=any(offset),
                reverse_winding=reverse^negative,world_transform_negative_determinant=negative,
                collision=str(c.get_collision_enabled()),materials=[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]))
    native.write(W/'GeometryAfter.json',dict(map_sha256=digest,components=records,hidden_components_excluded=hidden,
        errors=[],unique_meshes=len(cache),coordinate_serialization='unrounded native local positions and unrounded native transformed world positions, plus verified material WPO',
        triangles=sum(len(r['triangles']) for r in records),new_asset_sha256=read(W/'BuildReport.json')['new_asset_sha256']))
    write('AfterSummary.json',dict(passed=True,map_sha256=digest,actors=8014,visible_components=len(records),unique_meshes=len(cache),
        hidden_components_excluded=hidden,errors=[],triangles=sum(len(r['triangles']) for r in records)))
    assert sha(MAP)==digest
    unreal.log('REALISM_REFINEMENT_SAVED_AUDIT_PASS '+json.dumps(dict(actors=8014,components=sum(map(len,components.values())),materials=len(native.MATERIAL_CACHE),mesh_buffers=345)))
if __name__=='__main__':
    try:main()
    except Exception:
        write('SavedAuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
