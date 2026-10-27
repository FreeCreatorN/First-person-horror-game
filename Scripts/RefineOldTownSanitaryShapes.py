"""Make existing toilet bowls hollow and replace faucet elbows with a continuous rounded spout."""
import json,sys,math,traceback,shutil
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from PolishOldTownDetails import actor_bounds
from OldTownSurfaceMeshClones import _geometry
from RepairOldTownBasinConnections import collision_signature
from AuditOldTownHotelV4 import audit,refresh
import AuditOldTownHotelDetails as detail
import OldTownToiletConnectionPlan as toilets
import OldTownFaucetDetailPlan as faucets
import OldTownSanitaryShapePlan as shapes

WORK=ROOT/'Saved/CodexOutputs/SanitaryShapes_20261011'
SOURCE=ROOT/'Saved/CodexOutputs/SanitaryFixtures_20261011'
SOURCE_SHA='412d31cf4b23b5ee16cb3b9d1238dae4c1f7a990a19d6db642cf21611f7349f9'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSETS='/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def result(v):
    if isinstance(v,tuple):assert v[1]==unreal.GeometryScriptOutcomePins.SUCCESS,v;return v[0]
    return v
def shape_recipe(kind):
    return dict(schema=shapes.SCHEMA,pieces=[p for p in shapes.build_pieces() if p['fixture']==kind],removals=[r for r in shapes.source_removal_specs() if r['fixture']==kind])

def section_faces(mesh):
    out=[]
    for sec in range(mesh.get_num_sections(0)):
        data=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh,0,sec)
        vv=[[float(v.x),float(v.y),float(v.z)] for v in data[0]]
        out.append(Counter(tuple(sorted(tuple(vv[int(data[1][i+j])]) for j in range(3))) for i in range(0,len(data[1]),3)))
    return out

def append_piece(dynamic,piece):
    buffers=unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property('vertices',[unreal.Vector(*p) for p in piece['vertices']])
    # The pure recipe uses mathematical outward winding; Unreal render data
    # uses clockwise front faces. Reversing only new faces also makes the
    # normal calculator produce physical outward normals in Unreal.
    buffers.set_editor_property('triangles',[unreal.IntVector(x=t[0],y=t[2],z=t[1]) for t in piece['triangles']])
    buffers.set_editor_property('tri_group_i_ds',piece['smooth_groups'])
    buffers.set_editor_property('uv0',[unreal.Vector2D(p[0]/50.,p[2]/50.) for p in piece['vertices']])
    temporary,_=unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(unreal.DynamicMesh(),buffers,piece['material_id'],False)
    split=unreal.GeometryScriptSplitNormalsOptions()
    split.set_editor_property('split_by_opening_angle',False)
    split.set_editor_property('split_by_face_group',True)
    temporary=unreal.GeometryScript_Normals.compute_split_normals(temporary,split,unreal.GeometryScriptCalculateNormalsOptions())
    temporary=unreal.GeometryScript_Normals.compute_tangents(temporary,unreal.GeometryScriptTangentsOptions())
    return unreal.GeometryScript_MeshEdits.append_mesh(dynamic,temporary,unreal.Transform(),False,unreal.GeometryScriptAppendMeshOptions())

def clone_fixture(kind,allow_owned_update=False):
    package=shapes.TOILET_SOURCE if kind=='Toilet' else shapes.BASIN_SOURCE
    source=unreal.load_asset(package);assert isinstance(source,unreal.StaticMesh)
    source_file=ROOT/('Content/'+package[6:]+'.uasset');source_sha=sha(source_file)
    materials=[s.material_interface.get_path_name() if s.material_interface else None for s in source.static_materials]
    collision=collision_signature(source);recipe=shape_recipe(kind)
    options=unreal.GeometryScriptCopyMeshFromAssetOptions()
    for k,v in dict(apply_build_settings=True,request_tangents=True,use_build_scale=True).items():options.set_editor_property(k,v)
    lod=unreal.GeometryScriptMeshReadLOD();lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.RENDER_DATA);lod.set_editor_property('lod_index',0)
    dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(source,unreal.DynamicMesh(),options,lod,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
    vv,tt=_geometry(dynamic);groups=toilets._groups(vv,tt);by_triangle={tuple(t):i for i,t in enumerate(tt)}
    removed=[];removed_faces=Counter();removal_evidence=[]
    for spec in recipe['removals']:
        candidates=[g for g in groups if len(g)==spec['triangles'] and max(abs(a-b) for aa,bb in zip(toilets._bounds(vv,g),spec['bounds_cm']) for a,b in zip(aa,bb))<.002]
        assert len(candidates)==1,(spec['name'],len(candidates));group=candidates[0]
        for t in group:
            tid=by_triangle[tuple(t)];mat,valid=unreal.GeometryScript_Materials.get_triangle_material_id(dynamic,tid)
            assert valid and mat==spec['material_id'];removed.append(tid)
            removed_faces[tuple(sorted(tuple(vv[i]) for i in t))]+=1
        removal_evidence.append(dict(name=spec['name'],triangles=len(group),bounds_cm=toilets._bounds(vv,group),material_id=spec['material_id']))
    assert len(removed)==len(set(removed))
    _,selection=unreal.GeometryScript_MeshSelection.convert_index_array_to_mesh_selection(dynamic,removed,unreal.GeometryScriptMeshSelectionType.TRIANGLES)
    dynamic,count=unreal.GeometryScript_MeshEdits.delete_selected_triangles_from_mesh(dynamic,selection,False)
    assert count==len(removed)
    for piece in recipe['pieces']:dynamic=append_piece(dynamic,piece)
    dynamic=unreal.GeometryScript_MeshRepair.remove_unused_vertices(dynamic)
    dynamic=unreal.GeometryScript_MeshRepair.compact_mesh(dynamic)
    clonepath=ASSETS+'/SM_OTS_Arch_'+kind+'_Shaped'
    assets=unreal.EditorAssetLibrary
    if assets.does_asset_exist(clonepath):
        assert allow_owned_update,'Review saved output before repeating.'
        clone=assets.load_asset(clonepath)
        assert assets.get_metadata_tag(clone,'CodexShapeSource')==source.get_path_name()
        assert assets.get_metadata_tag(clone,'CodexShapeRecipe')==shapes.SCHEMA
    else:
        assets.make_directory(ASSETS);clone=assets.duplicate_asset(package,clonepath)
    assert clone
    settings=unreal.GeometryScriptCopyMeshToAssetOptions()
    for k,v in dict(enable_recompute_normals=False,enable_recompute_tangents=False,enable_remove_degenerates=False,use_build_scale=True,replace_materials=False,apply_nanite_settings=False,emit_transaction=False,defer_mesh_post_edit_change=False).items():settings.set_editor_property(k,v)
    settings.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
    outlod=unreal.GeometryScriptMeshWriteLOD();outlod.set_editor_property('lod_index',0)
    result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,clone,settings,outlod,True))
    assert collision_signature(clone)==collision
    assert [s.material_interface.get_path_name() if s.material_interface else None for s in clone.static_materials]==materials
    wanted=section_faces(source);actual=section_faces(clone);assert len(wanted)==len(actual)==2
    assert not removed_faces-wanted[0];wanted[0]-=removed_faces
    added=[]
    for i,(old,new) in enumerate(zip(wanted,actual)):
        assert not old-new,(kind,i,'Retained source faces changed in render material section')
        extra=sum((new-old).values());added.append(extra)
        assert i==0 or not extra,(kind,i,'Replacements in wrong material slot')
    assert added[0]==sum(len(p['triangles']) for p in recipe['pieces'])
    assets.set_metadata_tag(clone,'CodexShapeSource',source.get_path_name())
    assets.set_metadata_tag(clone,'CodexShapeRecipe',shapes.SCHEMA)
    assert assets.save_loaded_asset(clone,False) and sha(source_file)==source_sha
    file=ROOT/('Content/'+clonepath[6:]+'.uasset')
    return clone,dict(asset_key=kind,source=source.get_path_name(),source_file=str(source_file),source_sha256=source_sha,asset=clone.get_path_name(),file=str(file),sha256=sha(file),render_indices_reversed=True,removed_part_names=[r['name'] for r in recipe['removals']],shape_recipe=recipe,removed_source_parts=removal_evidence,added_triangles_per_material_section=added,retained_source_faces_verified_in_original_sections=True,collision_signature=collision,materials=materials)

def expected_actor(before,asset,kind):
    state=deepcopy(before)
    for c in state['components']:
        if c.get('mesh'):c['mesh']=asset
    return state

def main():
    assert not (WORK/'Applied.json').exists(),'Already applied.'
    assert shapes.audit_recipe()['passed']
    recipe_file=ROOT/'SourceArt/OldTownSanitaryShapes_20261011/Recipe.json';recipe_file.parent.mkdir(parents=True,exist_ok=True)
    recipe_file.write_text(json.dumps(dict(schema=shapes.SCHEMA,pieces=shapes.build_pieces(),removals=shapes.source_removal_specs()),ensure_ascii=False,indent=2),encoding='utf-8')
    build=read(SOURCE/'BuildReport.json');before=read(SOURCE/'AfterSnapshot.json')
    assert sha(MAP)==SOURCE_SHA==build['map_sha256']==before['source_map_sha256']
    for file,digest in dict(before['shared_asset_sha256'],**build['new_asset_sha256'],**before['protected_map_sha256']).items():assert sha(Path(file))==digest,file
    backup=WORK/'Before';backup.mkdir(parents=True,exist_ok=True)
    for n in ('BuildReport.json','AfterSnapshot.json','PreservationBaseline.json'):shutil.copy2(SOURCE/n,backup/n)
    shutil.copy2(MAP,backup/MAP.name);write('InputSnapshot.json',before)
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert {n:actor_state(a) for n,a in by.items()}==before['actors']
    plan=deepcopy(build['hotel_v4']);assets={};reports=[];changed={};colliders=[]
    for kind in ('Toilet','Washbasin'):
        mesh,report=clone_fixture(kind);assets[kind]=mesh;reports.append(report)
        rows=[r for r in plan['placed_props'] if r.get('asset_key')==kind];assert len(rows)==30
        for r in rows:
            actor=by[r['actor']];component=actor.get_component_by_class(unreal.StaticMeshComponent)
            assert component.static_mesh.get_path_name()==report['source'] and component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
            component.set_static_mesh(mesh)
            r['asset']=mesh.get_path_name();lo,hi=actor_bounds(actor)
            for k,v in dict(world_min=lo,world_max=hi,bounds=[lo,hi],world_bounds_cm=[lo,hi]).items():r[k]=v
            changed[r['actor']]=kind;colliders.extend(c['actor'] for c in r['colliders'])
        plan['asset_catalog'][kind]=mesh.get_path_name().split('.')[0]
    placed={r['id']:r for r in plan['placed_props']}
    for r in plan['props']:
        if r.get('asset_key') in assets:
            q=placed[r['id']];r['asset']=q['asset']
            for k in ('world_min','world_max','bounds','world_bounds_cm'):r[k]=deepcopy(q[k])
    cameras=[]
    camera_specs=(('CAM_Shape_ToiletInterior201','OTS_HotelV4_Room201_Toilet',[-62,-34,92],[-9,0,35],64),
                  ('CAM_Shape_ToiletFullPublic','OTS_HotelV4_PublicWCStall0Toilet',[-115,-52,80],[0,0,38],70))
    for name,target,local_pos,local_look,fov in camera_specs:
        transform=by[target].get_component_by_class(unreal.StaticMeshComponent).get_world_transform()
        pos=unreal.MathLibrary.transform_location(transform,unreal.Vector(*local_pos));look=unreal.MathLibrary.transform_location(transform,unreal.Vector(*local_look))
        a=sub.spawn_actor_from_class(unreal.CameraActor,pos,unreal.MathLibrary.find_look_at_rotation(pos,look),False);assert a
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelV4/ReviewCameras'));a.set_editor_property('tags',[unreal.Name('HotelRedesign_20261008_V4')])
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
        cameras.append(dict(camera=name,position=xyz(pos),look_at=xyz(look),fov=fov,fixture=target))
    actors=list(sub.get_all_level_actors());refresh(actors);current={a.get_actor_label():actor_state(a) for a in actors}
    added={r['camera'] for r in cameras};assert set(current)==set(before['actors'])|added
    for n,state in before['actors'].items():
        expected=expected_actor(state,assets[changed[n]].get_path_name(),changed[n]) if n in changed else state
        assert current[n]==expected,'Unexpected saved-state change: '+n
    assert all(current[n]==before['actors'][n] for n in colliders)
    plan['review_cameras']+=cameras;plan['new_actor_labels']=sorted(set(plan['new_actor_labels'])|added)
    plan['expected_actor_states']={n:current[n] for n in plan['new_actor_labels']};plan['source_map_sha256']=SOURCE_SHA
    baseline=deepcopy(read(SOURCE/'PreservationBaseline.json'));baseline['source_map_sha256']=SOURCE_SHA;write('PreservationBaseline.json',baseline)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    pre=audit(world,plan,baseline,actors);write('PreSaveAudit.json',pre);assert pre['passed'],pre['errors'][:20]
    detail.WORK=WORK;pre_detail=detail.detail_audit(world,plan,actors);write('PreSaveDetailAudit.json',pre_detail);assert pre_detail['passed'],pre_detail['errors'][:20]
    optimization=dict(passed=True,source_map_sha256=SOURCE_SHA,changed_actors=sorted(changed),new_assets=reports,new_cameras=cameras,current_cameras=[r['camera'] for r in cameras]+['CAM_Fixture_FaucetPublicWC','CAM_Basin_Guest201'],preserved_fixture_collision_actors=sorted(colliders),unchanged_existing_actors=len(before['actors'])-len(changed),recipe_file=str(recipe_file),recipe_sha256=sha(recipe_file),design_note='Closed hollow bowls retain seat and base connections; tapered rear shoulders avoid the cavity; faucet spouts have one continuous rounded elbow. All fixture transforms remain unchanged.')
    build.update(status='PENDING',source_map_sha256=SOURCE_SHA,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,sanitary_shape_refinement=optimization,hotel_openings_review_cameras=optimization['current_cameras'],previous_evidence=str(SOURCE/'FinalReview.json'))
    for report in reports:build['new_asset_sha256'][report['file']]=report['sha256']
    write('PendingBuildReport.json',build)
    assert sha(MAP)==SOURCE_SHA and levels.save_current_level()
    digest=sha(MAP);build.update(status='PASS',map_sha256=digest);optimization['map_sha256']=digest
    write('BuildReport.json',build);write('ShapeOptimizationReport.json',optimization);write('ArchitecturePlan.json',plan)
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=SOURCE_SHA,actor_count=len(actors),toilets=30,basins=30,cameras=2))
    unreal.log('SANITARY_SHAPES_APPLY_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
