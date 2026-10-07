"""Add daily-operation furnishings without editing the saved architecture/street."""
import json
import shutil
import sys
import traceback
from copy import deepcopy
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from ImportOldTownBlenderFurniture import _infer_axes
from AuditOldTownHotelOperations import audit, refresh
from OldTownHotelOperationsPlan import measured_plan
WORK=ROOT/'Saved/CodexOutputs/HotelOperations_20261006'
BASE=ROOT/'Saved/CodexOutputs/HotelArchitecture_20261005'
SOURCE=ROOT/'SourceArt/OldTownHotelOperations_20261006'
ASSETS='/Game/Yastar/Meshes/hOUSE/HotelOperations_20261006'
TAG='HotelOperations_20261006'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(name,data):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def import_assets(world,base):
    manifest=read(SOURCE/'ImportManifest.json')
    verify=read(SOURCE/'IndependentFBXVerification.json')
    assert verify['passed'] and verify['asset_count']==len(manifest['assets'])==15
    mats={k:unreal.load_asset(v) for k,v in base['hotel_architecture']['material_paths'].items()}
    mapping={'Wood':mats['wood'],'DarkMetal':mats['dark'],'Linen':mats['linen'],
             'Ceramic':mats['ceramic'],'Letters':mats['letters']}
    folder=ASSETS+'/Materials'
    unreal.EditorAssetLibrary.make_directory(folder)
    edit=unreal.MaterialEditingLibrary
    for key,color in {'Paper':[.48,.42,.29],'Upholstery':[.13,.105,.07]}.items():
        path=folder+'/M_OTS_Ops_'+key
        m=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
        if m:
            assert unreal.EditorAssetLibrary.get_metadata_tag(m,TAG+'_Owned')=='true',path
            mapping[key]=m
            continue
        m=unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit('/',1)[1],folder,unreal.Material,unreal.MaterialFactoryNew())
        c=edit.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-300,0)
        c.set_editor_property('constant',unreal.LinearColor(*color,1))
        assert edit.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
        r=edit.create_material_expression(m,unreal.MaterialExpressionConstant,-300,150)
        r.set_editor_property('r',.95)
        assert edit.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
        edit.recompile_material(m)
        unreal.EditorAssetLibrary.set_metadata_tag(m,TAG+'_Owned','true')
        assert unreal.EditorAssetLibrary.save_loaded_asset(m,False)
        mapping[key]=m
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    assets,named,rows={},{},[]
    for row in manifest['assets']:
        assert sha(SOURCE/row['file'])==row['source_sha256']
        asset_path=ASSETS+'/'+row['name']
        existing=unreal.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
        if existing:
            assert unreal.EditorAssetLibrary.get_metadata_tag(existing,TAG+'_SourceSHA256')==row['source_sha256'],row['name']
        ui=unreal.FbxImportUI()
        for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_animations':False,
                    'import_materials':False,'import_textures':False,
                    'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():ui.set_editor_property(k,v)
        for k,v in {'combine_meshes':True,'auto_generate_collision':False,'generate_lightmap_u_vs':True,
                    'convert_scene':True,'convert_scene_unit':True,'import_uniform_scale':1.}.items():ui.static_mesh_import_data.set_editor_property(k,v)
        task=unreal.AssetImportTask()
        for k,v in {'filename':str(SOURCE/row['file']),'destination_path':ASSETS,'destination_name':row['name'],
                    'automated':True,'replace_existing':False,'save':False,'options':ui,'factory':unreal.FbxFactory()}.items():task.set_editor_property(k,v)
        if not existing:unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        mesh=existing or unreal.load_asset(asset_path)
        assert isinstance(mesh,unreal.StaticMesh),row['name']
        material_assets=[]
        for index,slot in enumerate(mesh.static_materials):
            key=next((k for k in mapping if k.lower() in str(slot.material_slot_name).lower()),None)
            assert key,str(slot.material_slot_name)
            mesh.set_material(index,mapping[key]);material_assets.append(mapping[key].get_path_name())
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,TAG+'_SourceSHA256',row['source_sha256'])
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,False)
        assets[row['key']]=mesh;named[row['name']]=mesh
        rows.append(dict(row,asset=mesh.get_path_name(),material_assets=material_assets))
    axes=_infer_axes(manifest['assets'],named)
    assert tuple(axes['order'])==(0,1,2) and axes['signs'][0]==axes['signs'][2]==1,axes
    write('OperationsImportReport.json',dict(passed=True,imports=rows,axes=axes))
    return assets,rows,axes


def main():
    assert not (WORK/'OperationsApplied.json').exists(),'Already saved. Use the fresh reload audit.'
    base=read(BASE/'BuildReport.json')
    mapfile=ROOT/('Content/'+base['target_level'].removeprefix('/Game/')+'.umap')
    assert sha(mapfile)==base['map_sha256'],'Current map changed since architecture review.'
    p=measured_plan()
    before=WORK/'Before';before.mkdir(exist_ok=True)
    for f in (mapfile,BASE/'BuildReport.json'):
        if not (before/f.name).exists():shutil.copy2(f,before/f.name)
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(base['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(sub.get_all_level_actors())
    assert len(actors)==base['actor_count']
    baseline=dict(source_map_sha256=base['map_sha256'],actors={a.get_actor_label():actor_state(a) for a in actors},shared_asset_sha256=shared_asset_hashes(actors))
    write('PreservationBaseline.json',baseline)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assets,imports,axes=import_assets(world,base)
    new_names=[]
    cube=unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
    dark=unreal.load_asset(base['hotel_architecture']['material_paths']['dark'])
    def spawn(name,mesh,pos,role,yaw=0,scale=(1,1,1),collision=False,hidden=False):
        assert name not in baseline['actors'] and name not in new_names,name
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelOperations/'+role))
        a.set_editor_property('tags',[unreal.Name(TAG)])
        a.set_actor_scale3d(unreal.Vector(*scale))
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(mesh)
        c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        if hidden:
            c.set_material(0,dark);c.set_editor_property('visible',False)
            c.set_editor_property('hidden_in_game',True);c.set_editor_property('cast_shadow',False)
        new_names.append(name)
        return a
    p['placed_props']=[]
    for row in p['props']:
        name='OTS_Hotel'+row['id']
        # Legacy FBX import reflects authored Y; actor reflection restores the modeled orientation.
        scale=[row['scale'][i]*axes['signs'][i] for i in range(3)]
        mesh=assets[row['asset_key']]
        spawn(name,mesh,row['position_cm'],row['role'],row['yaw'],scale)
        colliders=[]
        for i,(lo,hi) in enumerate(row['collision_boxes']):
            id=row['id']+'_Collision%d'%i
            actor='OTS_Hotel'+id
            spawn(actor,cube,[(lo[k]+hi[k])/2 for k in range(3)],'Collision',
                  scale=[(hi[k]-lo[k])/100 for k in range(3)],collision=True,hidden=True)
            colliders.append(dict(id=id,actor=actor,role='FixtureCollision',world_min=lo,world_max=hi,
                material='dark',material_asset=dark.get_path_name(),asset=cube.get_path_name(),collision=True,floor=0))
        p['placed_props'].append(dict(row,actor=name,actor_scale=scale,asset=mesh.get_path_name(),colliders=colliders))
    for row in p['review_cameras']:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*row['position']),unreal.Vector(*row['look_at']))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*row['position']),rot,False)
        a.set_actor_label(row['camera']);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelOperations/ReviewCameras'))
        a.set_editor_property('tags',[unreal.Name(TAG)])
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',row['fov'])
        new_names.append(row['camera'])
    build=deepcopy(base)
    build['source_map_sha256']=base['map_sha256']
    build['previous_evidence']=str(BASE/'FinalReview.json')
    build['hotel_operations']=dict(p,new_actor_labels=new_names,imports=imports,axes=axes)
    arch=build['hotel_architecture']
    arch['props'].extend(p['props']);arch['placed_props'].extend(p['placed_props']);arch['routes'].extend(p['routes'])
    arch['new_actor_labels'].extend(new_names)
    build['hotel_openings_review_cameras']=[r['camera'] for r in p['review_cameras']]
    actors=list(sub.get_all_level_actors());build['actor_count']=len(actors)
    refresh(actors)
    write('ApplyStage.json',dict(stage='auditing_unsaved',new_actors=len(new_names)))
    report=audit(world,actors,build);write('PreSaveAudit.json',report)
    assert report['passed'],report['errors'][:12]
    assert level.save_current_level()
    build['map_sha256']=sha(mapfile);build['status']='PASS'
    write('BuildReport.json',build)
    write('OperationsApplied.json',dict(passed=True,map_sha256=build['map_sha256'],new_actors=new_names))
    unreal.log('HOTEL_OPERATIONS_APPLY_PASS '+str(report['statistics']))


if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()))
        raise
