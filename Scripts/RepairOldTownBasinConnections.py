"""Close the two real fixture gaps, without modifying shared Yastar assets."""
import json,sys,shutil,traceback,math
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from OldTownSurfaceMeshClones import _geometry
from AuditOldTownHotelV4 import audit,refresh
from AuditOldTownHotelDetails import detail_audit
import AuditOldTownHotelDetails as detail

WORK=ROOT/'Saved/CodexOutputs/BasinConnections_20261011'
SOURCE=ROOT/'Saved/CodexOutputs/HotelDetails_20261009'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SOURCE_SHA='f821289afb1e06cb2be98569d42b8cb2ad762be5ddf48dfbf00f1f7a4cd3617a'
ORIGINAL='/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005/SM_OTS_Arch_Washbasin'
CLONE='/Game/CodexGenerated/OldTown/Meshes/BasinConnections_20261011/SM_OTS_Arch_Washbasin_Connected'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def collision_signature(mesh):
    body=mesh.get_editor_property('body_setup');assert body is not None
    geom=body.get_editor_property('agg_geom');counts={}
    for k in ('box_elems','sphere_elems','sphyl_elems','convex_elems','tapered_capsule_elems','level_set_elems','skinned_level_set_elems','ml_level_set_elems','skinned_triangle_mesh_elems'):
        try:counts[k]=len(geom.get_editor_property(k))
        except Exception:continue
    assert counts and not any(counts.values()),'Fixture must retain separate unchanged collider actors.'
    return dict(trace=str(body.get_editor_property('collision_trace_flag')),shapes=counts)

def fixed_mesh():
    original=unreal.load_asset(ORIGINAL);assert isinstance(original,unreal.StaticMesh)
    file=ROOT/('Content/'+ORIGINAL[6:]+'.uasset');digest=sha(file)
    before_collision=collision_signature(original)
    opt=unreal.GeometryScriptCopyMeshFromAssetOptions()
    for k,v in dict(apply_build_settings=True,request_tangents=True,use_build_scale=True).items():opt.set_editor_property(k,v)
    lod=unreal.GeometryScriptMeshReadLOD();lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.RENDER_DATA);lod.set_editor_property('lod_index',0)
    dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(original,unreal.DynamicMesh(),opt,lod,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
    vertices,triangles=_geometry(dynamic);moved=[];counts={'drain_top':0,'tap_bottom':0}
    for i,(x,y,z) in enumerate(vertices):
        name=None;newz=z
        if abs(z-64)<.001 and math.hypot(x-12,y)<=2.501:name='drain_top';newz=73.3
        elif abs(z-81.4)<.001 and math.hypot(x-16,y)<=1.201:name='tap_bottom';newz=80.7
        if name:
            _,valid=unreal.GeometryScript_MeshEdits.set_vertex_position(dynamic,i,unreal.Vector(x,y,newz),False)
            assert valid,i
            counts[name]+=1;moved.append(dict(vertex=i,part=name,before=[x,y,z],after=[x,y,newz]))
    assert all(c>=24 for c in counts.values()),counts
    after,after_triangles=_geometry(dynamic)
    assert triangles==after_triangles and len(after)==len(vertices)
    change_ids={r['vertex'] for r in moved}
    assert all(v==after[i] for i,v in enumerate(vertices) if i not in change_ids)
    assets=unreal.EditorAssetLibrary;assert not assets.does_asset_exist(CLONE),'Use saved audit; do not apply twice.'
    assets.make_directory(CLONE.rsplit('/',1)[0]);clone=assets.duplicate_asset(ORIGINAL,CLONE);assert clone
    settings=unreal.GeometryScriptCopyMeshToAssetOptions()
    for k,v in dict(enable_recompute_normals=False,enable_recompute_tangents=False,enable_remove_degenerates=False,use_build_scale=True,replace_materials=False,apply_nanite_settings=False,emit_transaction=False,defer_mesh_post_edit_change=False).items():settings.set_editor_property(k,v)
    settings.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
    outlod=unreal.GeometryScriptMeshWriteLOD();outlod.set_editor_property('lod_index',0)
    _,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,clone,settings,outlod,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
    assert collision_signature(clone)==before_collision
    assert [m.material_interface.get_path_name() if m.material_interface else None for m in original.static_materials]==[m.material_interface.get_path_name() if m.material_interface else None for m in clone.static_materials]
    assets.set_metadata_tag(clone,'CodexConnectionSource',original.get_path_name())
    assert assets.save_loaded_asset(clone,False)
    assert sha(file)==digest,'Original shared basin changed.'
    clonefile=ROOT/('Content/'+CLONE[6:]+'.uasset')
    return clone,dict(source=original.get_path_name(),source_file=str(file),source_sha256=digest,asset=clone.get_path_name(),file=str(clonefile),sha256=sha(clonefile),moved_vertices=moved,counts=counts,collision_signature=before_collision,source_gap_cm=5,drain_top_cm=73.3,tap_bottom_cm=80.7,unchanged_other_vertices=True)

def main():
    assert not (WORK/'Applied.json').exists(),'Already applied.'
    build=read(SOURCE/'BuildReport.json');original=read(SOURCE/'AfterSnapshot.json')
    assert sha(MAP)==SOURCE_SHA==build['map_sha256']==original['source_map_sha256']
    for file,digest in dict(original['shared_asset_sha256'],**build['new_asset_sha256'],**original['protected_map_sha256']).items():assert sha(Path(file))==digest,file
    backup=WORK/'Before';backup.mkdir(parents=True,exist_ok=True)
    for filename in ('BuildReport.json','AfterSnapshot.json','PreservationBaseline.json'):shutil.copy2(SOURCE/filename,backup/filename)
    shutil.copy2(MAP,backup/MAP.name);write('InputSnapshot.json',original)
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    current={n:actor_state(a) for n,a in by.items()};assert current==original['actors'],'Loaded starting map differs from preserved snapshot.'
    plan=deepcopy(build['hotel_v4']);rows=[r for r in plan['placed_props'] if r.get('asset','').split('.')[0]==ORIGINAL]
    assert len(rows)==30
    mesh,repair=fixed_mesh();targets={r['actor'] for r in rows}
    actual_targets={a.get_actor_label() for a in actors for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh and c.static_mesh.get_path_name().split('.')[0]==ORIGINAL}
    assert actual_targets==targets,'A shared basin instance was omitted.'
    for r in rows:
        c=by[r['actor']].get_component_by_class(unreal.StaticMeshComponent)
        assert c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
        c.set_static_mesh(mesh);r['asset']=mesh.get_path_name()
    for r in plan['props']:
        if r.get('asset_key')=='Washbasin':r['asset']=mesh.get_path_name()
    plan['asset_catalog']['Washbasin']=CLONE
    cameras=[]
    for name,target in (('CAM_Basin_Guest201','OTS_HotelV4_Room201_Basin'),('CAM_Basin_Guest409','OTS_HotelV4_Room409_Basin'),('CAM_Basin_PublicWC','OTS_HotelV4_PublicWCBasin0')):
        c=by[target].get_component_by_class(unreal.StaticMeshComponent);transform=c.get_world_transform()
        # Remain inside the bathroom front partition, with an underside angle
        # in guestrooms and a tap/whole-basin angle in the public WC.
        local_pos=(-20,-50,98) if name=='CAM_Basin_PublicWC' else (-20,-36,56)
        local_look=(12,0,78) if name=='CAM_Basin_PublicWC' else (12,0,70)
        pos=unreal.MathLibrary.transform_location(transform,unreal.Vector(*local_pos))
        look=unreal.MathLibrary.transform_location(transform,unreal.Vector(*local_look))
        a=sub.spawn_actor_from_class(unreal.CameraActor,pos,unreal.MathLibrary.find_look_at_rotation(pos,look),False);assert a
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelV4/ReviewCameras'));a.set_editor_property('tags',[unreal.Name('HotelRedesign_20261008_V4')])
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',65)
        cameras.append(dict(camera=name,position=xyz(pos),look_at=xyz(look),fov=65,fixture=target))
    actors=list(sub.get_all_level_actors());refresh(actors);current={a.get_actor_label():actor_state(a) for a in actors}
    added={r['camera'] for r in cameras}
    assert set(current)==set(original['actors'])|added
    for n,old in original['actors'].items():
        expected=deepcopy(old)
        if n in targets:
            for c in expected['components']:
                if c.get('mesh','').split('.')[0]==ORIGINAL:c['mesh']=mesh.get_path_name()
        assert current[n]==expected,'Unexpected actor change: '+n
    plan['review_cameras']+=cameras;plan['new_actor_labels']=sorted(set(plan['new_actor_labels'])|added)
    plan['expected_actor_states']={n:current[n] for n in plan['new_actor_labels']}
    plan['source_map_sha256']=SOURCE_SHA
    baseline=deepcopy(read(SOURCE/'PreservationBaseline.json'));baseline['source_map_sha256']=SOURCE_SHA
    write('PreservationBaseline.json',baseline)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,plan,baseline,actors);write('PreSaveAudit.json',result);assert result['passed'],result['errors'][:20]
    detail.WORK=WORK;details=detail_audit(world,plan,actors);write('PreSaveDetailAudit.json',details);assert details['passed'],details['errors'][:20]
    repair.update(actors=sorted(targets),new_cameras=cameras,unchanged_existing_actors=len(original['actors'])-len(targets),unchanged_collision_actors=[c['actor'] for r in rows for c in r['colliders']])
    build.update(status='PENDING',source_map_sha256=SOURCE_SHA,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,previous_evidence=str(SOURCE/'FinalReview.json'),basin_connection_repair=repair)
    build['new_asset_sha256'][repair['file']]=repair['sha256']
    # Only fixture closeups are freshly rendered for this isolated mesh change.
    # Earlier 21 camera images remain explicitly historical.
    build['hotel_openings_review_cameras']=[r['camera'] for r in cameras]
    write('PendingBuildReport.json',build)
    assert sha(MAP)==SOURCE_SHA and levels.save_current_level()
    digest=sha(MAP);build.update(status='PASS',map_sha256=digest);repair['map_sha256']=digest
    write('BuildReport.json',build);write('BasinRepairReport.json',repair);write('ArchitecturePlan.json',plan)
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=SOURCE_SHA,basins=30,cameras=3,actor_count=len(actors)))
    unreal.log('BASIN_CONNECTION_REPAIR_PASS '+digest)

if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
