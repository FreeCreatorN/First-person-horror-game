"""Reimport only the owned clock and distinguish soiled collection-cart cloth."""
import json
import sys
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from AuditOldTownHotelOperations import audit,refresh,read,write,WORK,SOURCE,TAG
from OldTownHotelOperationsPlan import measured_plan
from PolishOldTownHotel import sha
ASSETS='/Game/Yastar/Meshes/hOUSE/HotelOperations_20261006'


def main():
    assert not (WORK/'VisualAssetRepair.json').exists(),'Already repaired; audit the saved assets.'
    build=read(WORK/'BuildReport.json')
    mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
    original=sha(mapfile);assert original==build['map_sha256']
    ops=build['hotel_operations']
    manifest=read(SOURCE/'ImportManifest.json')
    source=next(r for r in manifest['assets'] if r['key']=='WallClock')
    old=next(r for r in ops['imports'] if r['key']=='WallClock')
    assert source['source_sha256']!=old['source_sha256'],'Clock source was not repaired.'
    assert all(sha(SOURCE/r['file'])==r['source_sha256'] for r in ops['imports'] if r['key']!='WallClock')
    plan=measured_plan();by_id={r['id']:r for r in plan['props']}
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level('/Game/Yastar/Maps/L_Main')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    ui=unreal.FbxImportUI()
    for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_animations':False,
                'import_materials':False,'import_textures':False,
                'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():ui.set_editor_property(k,v)
    for k,v in {'combine_meshes':True,'auto_generate_collision':False,'generate_lightmap_u_vs':True,
                'convert_scene':True,'convert_scene_unit':True,'import_uniform_scale':1.}.items():ui.static_mesh_import_data.set_editor_property(k,v)
    task=unreal.AssetImportTask()
    for k,v in {'filename':str(SOURCE/source['file']),'destination_path':ASSETS,'destination_name':source['name'],
                'automated':True,'replace_existing':True,'save':False,'options':ui,'factory':unreal.FbxFactory()}.items():task.set_editor_property(k,v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh=unreal.load_asset(old['asset'])
    assert isinstance(mesh,unreal.StaticMesh)
    mats={'DarkMetal':unreal.load_asset(build['hotel_architecture']['material_paths']['dark']),
          'Paper':unreal.load_asset(ASSETS+'/Materials/M_OTS_Ops_Paper')}
    material_assets=[]
    for i,slot in enumerate(mesh.static_materials):
        key=next(k for k in mats if k.lower() in str(slot.material_slot_name).lower())
        mesh.set_material(i,mats[key]);material_assets.append(mats[key].get_path_name())
    unreal.EditorAssetLibrary.set_metadata_tag(mesh,TAG+'_SourceSHA256',source['source_sha256'])
    assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,False)
    old.update(source);old['material_assets']=material_assets
    # This trolley collects soiled bundles inside the dirty store.
    folder=ASSETS+'/Materials';name='M_OTS_Ops_SoiledCloth';path=folder+'/'+name
    m=unreal.load_asset(path)
    if m is None:
        m=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
        edit=unreal.MaterialEditingLibrary
        c=edit.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-300,0)
        c.set_editor_property('constant',unreal.LinearColor(.17,.135,.085,1))
        assert edit.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
        r=edit.create_material_expression(m,unreal.MaterialExpressionConstant,-300,150);r.set_editor_property('r',.97)
        assert edit.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
        edit.recompile_material(m)
        unreal.EditorAssetLibrary.set_metadata_tag(m,TAG+'_Owned','true')
        assert unreal.EditorAssetLibrary.save_loaded_asset(m,False)
    cart_row=next(r for r in ops['imports'] if r['key']=='HousekeepingCart')
    cart=unreal.load_asset(cart_row['asset'])
    for i,slot in enumerate(cart.static_materials):
        if 'linen' in str(slot.material_slot_name).lower():
            cart.set_material(i,m);cart_row['material_assets'][i]=m.get_path_name()
    assert unreal.EditorAssetLibrary.save_loaded_asset(cart,False)
    for collection in (ops['props'],ops['placed_props'],build['hotel_architecture']['props'],build['hotel_architecture']['placed_props']):
        for row in collection:
            if row['id']=='Ops_StoppedClock':row['world_bounds_cm']=by_id[row['id']]['world_bounds_cm']
    ops['soiled_cart_material']=m.get_path_name()
    imported=read(WORK/'OperationsImportReport.json');imported['imports']=ops['imports'];write('OperationsImportReport.json',imported)
    assert level.load_level(build['target_level'])
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    refresh(actors)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report=audit(world,actors,build);write('OperationsAudit.json',report)
    assert report['passed'],report['errors'][:12]
    assert sha(mapfile)==original,'Only owned meshes/materials may be changed.'
    write('BuildReport.json',build)
    write('VisualAssetRepair.json',dict(passed=True,map_unchanged=True,map_sha256=original,
        repaired_clock_source_sha256=source['source_sha256'],soiled_cart_material=m.get_path_name(),
        affected_views=['CAM_OpsHotel_Reception','CAM_OpsHotel_Linen']))
    unreal.log('HOTEL_OPERATIONS_VISUAL_REPAIR_PASS '+str(report['statistics']))


if __name__=='__main__':main()
