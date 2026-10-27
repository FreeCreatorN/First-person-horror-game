"""Improve existing toilet support/orientation and faucets without rebuilding rooms."""
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

WORK=ROOT/'Saved/CodexOutputs/SanitaryFixtures_20261011'
SOURCE=ROOT/'Saved/CodexOutputs/BasinConnections_20261011'
SOURCE_SHA='684f1f0533cef3ab50b6c7e3b270cb0a4dab924b839139e5d9a8e2048503f33d'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSETS='/Game/CodexGenerated/OldTown/Meshes/SanitaryFixtures_20261011'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def result(v):
    if isinstance(v,tuple):assert v[1]==unreal.GeometryScriptOutcomePins.SUCCESS,v;return v[0]
    return v
def section_faces(mesh,kind,move=False):
    out=[]
    for s in range(mesh.get_num_sections(0)):
        data=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh,0,s)
        vv=[[float(v.x),float(v.y),float(v.z)] for v in data[0]]
        if kind=='Toilet' and move:
            for i in toilets.bowl_top_vertex_ids(vv):vv[i][2]=toilets.NEW_BOWL_TOP
        out.append(Counter(tuple(sorted(tuple(round(x,3) for x in vv[int(data[1][i+j])]) for j in range(3))) for i in range(0,len(data[1]),3)))
    return out

def clone_fixture(kind):
    module=toilets if kind=='Toilet' else faucets
    source=unreal.load_asset(module.SOURCE_ASSET);assert isinstance(source,unreal.StaticMesh)
    source_file=ROOT/('Content/'+module.SOURCE_ASSET[6:]+'.uasset');source_sha=sha(source_file)
    materials=[s.material_interface.get_path_name() if s.material_interface else None for s in source.static_materials]
    assert ('Ceramic' if kind=='Toilet' else 'DarkTrim') in materials[0],materials
    collision=collision_signature(source)
    options=unreal.GeometryScriptCopyMeshFromAssetOptions()
    for k,v in dict(apply_build_settings=True,request_tangents=True,use_build_scale=True).items():options.set_editor_property(k,v)
    lod=unreal.GeometryScriptMeshReadLOD();lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.RENDER_DATA);lod.set_editor_property('lod_index',0)
    dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(source,unreal.DynamicMesh(),options,lod,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
    before_v,before_t=_geometry(dynamic);moved=[]
    if kind=='Toilet':
        expected=toilets.expected_original_vertices(before_v)
        for i in toilets.bowl_top_vertex_ids(before_v):
            _,valid=unreal.GeometryScript_MeshEdits.set_vertex_position(dynamic,i,unreal.Vector(*expected[i]),False)
            assert valid;moved.append(i)
    primitives=module.primitive_specs()
    for part in primitives:
        opt=unreal.GeometryScriptPrimitiveOptions();opt.set_editor_property('material_id',part['material_id'])
        axis=part['axis'];pitch=-math.degrees(math.acos(axis[2]));yaw=math.degrees(math.atan2(axis[1],axis[0]))
        scale=[*part['radii'],1.] if part['kind']=='elliptical_cylinder' else [1.,1.,1.]
        transform=unreal.Transform(location=unreal.Vector(*part['center']),rotation=unreal.Rotator(pitch=pitch,yaw=yaw,roll=0),scale=unreal.Vector(*scale))
        dynamic=result(unreal.GeometryScript_Primitives.append_cylinder(dynamic,opt,transform,part['radius'],part['height'],24,1,True,unreal.GeometryScriptPrimitiveOriginMode.CENTER))
    after_v,after_t=_geometry(dynamic)
    if kind=='Toilet':
        preview=toilets.audit_geometry(before_v,before_t,after_v,after_t)
        assert preview['passed'],preview['errors']
    clonepath=ASSETS+'/SM_OTS_Arch_'+kind+'_Functional'
    assets=unreal.EditorAssetLibrary;assert not assets.does_asset_exist(clonepath),'Review saved results; do not apply twice.'
    assets.make_directory(ASSETS);clone=assets.duplicate_asset(module.SOURCE_ASSET,clonepath);assert clone
    settings=unreal.GeometryScriptCopyMeshToAssetOptions()
    for k,v in dict(enable_recompute_normals=False,enable_recompute_tangents=False,enable_remove_degenerates=False,use_build_scale=True,replace_materials=False,apply_nanite_settings=False,emit_transaction=False,defer_mesh_post_edit_change=False).items():settings.set_editor_property(k,v)
    settings.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
    outlod=unreal.GeometryScriptMeshWriteLOD();outlod.set_editor_property('lod_index',0)
    result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,clone,settings,outlod,True))
    assert collision_signature(clone)==collision
    assert [s.material_interface.get_path_name() if s.material_interface else None for s in clone.static_materials]==materials
    assets.set_metadata_tag(clone,'CodexFixtureSource',source.get_path_name())
    assert assets.save_loaded_asset(clone,False)
    # Verify actual persisted render sections: original faces stay in their
    # existing material section; every new connector is in the intended slot.
    wanted=section_faces(source,kind,True);actual=section_faces(clone,kind)
    assert len(wanted)==len(actual)==2
    added=[]
    for i,(old,new) in enumerate(zip(wanted,actual)):
        assert not old-new,(kind,i,'Original section lost faces')
        extra=sum((new-old).values());added.append(extra)
        assert i==0 or not extra,(kind,i,'New faces received wrong material')
    assert added[0]>0 and sha(source_file)==source_sha
    file=ROOT/('Content/'+clonepath[6:]+'.uasset')
    return clone,dict(asset_key=kind,source=source.get_path_name(),source_file=str(source_file),source_sha256=source_sha,asset=clone.get_path_name(),file=str(file),sha256=sha(file),primitive_specs=primitives,moved_vertex_ids=moved,added_triangles_per_material_section=added,original_faces_retained=True,collision_signature=collision,materials=materials)

def expected_actor(before,asset,kind):
    state=deepcopy(before)
    if kind=='Toilet':state['rotation']=[0.,0.,0.]
    for c in state['components']:
        if c.get('mesh'):
            c['mesh']=asset
            if kind=='Toilet':c['rotation']=[0.,0.,0.]
    return state

def main():
    assert not (WORK/'Applied.json').exists(),'Already applied.'
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
            if kind=='Toilet':assert actor.set_actor_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0),False)
            r['asset']=mesh.get_path_name();lo,hi=actor_bounds(actor)
            for k,v in dict(world_min=lo,world_max=hi,bounds=[lo,hi],world_bounds_cm=[lo,hi]).items():r[k]=v
            if kind=='Toilet':r.update(yaw=0.,rotation=[0.,0.,0.])
            changed[r['actor']]=kind;colliders.extend(c['actor'] for c in r['colliders'])
        plan['asset_catalog'][kind]=mesh.get_path_name().split('.')[0]
    placed={r['id']:r for r in plan['placed_props']}
    for r in plan['props']:
        if r.get('asset_key') in assets:
            q=placed[r['id']];r['asset']=q['asset']
            for k in ('world_min','world_max','bounds','world_bounds_cm'):r[k]=deepcopy(q[k])
            if r['asset_key']=='Toilet':r.update(yaw=0.,rotation=[0.,0.,0.])
    cameras=[]
    camera_specs=(('CAM_Fixture_ToiletGuest201','OTS_HotelV4_Room201_Toilet',[-82,-40,66],[4,0,38],74),
                  ('CAM_Fixture_ToiletPublicWC','OTS_HotelV4_PublicWCStall0Toilet',[-88,-38,62],[4,0,38],74),
                  ('CAM_Fixture_FaucetPublicWC','OTS_HotelV4_PublicWCBasin0',[-14,-34,104],[11,0,92],58))
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
    optimization=dict(passed=True,source_map_sha256=SOURCE_SHA,changed_actors=sorted(changed),new_assets=reports,new_cameras=cameras,current_cameras=[r['camera'] for r in cameras]+['CAM_Basin_Guest201'],preserved_fixture_collision_actors=sorted(colliders),unchanged_existing_actors=len(before['actors'])-len(changed),toilet_yaw_before=180.,toilet_yaw_after=0.,guest_shower_tray_front_clearance_cm=40.49,design_note='Seat joins bowl; grounded rear ceramic supports join tank. Toilet faces inward; guest wet-area tray still lies ahead. Faucets gain spout, aerator and control handle.')
    build.update(status='PENDING',source_map_sha256=SOURCE_SHA,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,fixture_optimization=optimization,hotel_openings_review_cameras=optimization['current_cameras'],previous_evidence=str(SOURCE/'FinalReview.json'))
    for report in reports:build['new_asset_sha256'][report['file']]=report['sha256']
    write('PendingBuildReport.json',build)
    assert sha(MAP)==SOURCE_SHA and levels.save_current_level()
    digest=sha(MAP);build.update(status='PASS',map_sha256=digest);optimization['map_sha256']=digest
    write('BuildReport.json',build);write('FixtureOptimizationReport.json',optimization);write('ArchitecturePlan.json',plan)
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=SOURCE_SHA,actor_count=len(actors),toilets=30,basins=30,cameras=3))
    unreal.log('SANITARY_FIXTURES_APPLY_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
