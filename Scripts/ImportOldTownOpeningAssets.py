"""Import this phase's Blender parts without loading or saving the target map."""
import unreal,json,hashlib,sys
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownOpeningSpecs import ASSET_ROOT
from ImportOldTownBlenderFurniture import _infer_axes
SOURCE=ROOT/'SourceArt/OldTownHotelOpenings_20261004'
WORK=ROOT/'Saved/CodexOutputs/HotelOpenings_20261004'

def import_assets():
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    manifest=json.loads((SOURCE/'ImportManifest.json').read_text());assets={};imports=[]
    mats={k:unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/'+p) for k,p in {
        'Trim':'Props/Detailed/Materials/M_P2_Wood','Green':'Materials/M_OTS_OldGreenMetal',
        'Metal':'Materials/M_OTS_RustMetal','Glass':'Materials/M_OTS_DarkGlass','Concrete':'Materials/M_OTS_OldConcrete'}.items()}
    assert all(mats.values())
    unreal.EditorAssetLibrary.make_directory(ASSET_ROOT)
    for e in manifest['assets']:
        path=ASSET_ROOT+'/'+e['name']
        options=unreal.FbxImportUI()
        for p,v in {'import_mesh':True,'import_as_skeletal':False,'import_animations':False,'import_materials':False,'import_textures':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():options.set_editor_property(p,v)
        data=options.static_mesh_import_data
        for p,v in {'combine_meshes':True,'auto_generate_collision':False,'generate_lightmap_u_vs':True,'convert_scene':True,'convert_scene_unit':True,'import_uniform_scale':1.}.items():data.set_editor_property(p,v)
        task=unreal.AssetImportTask()
        for p,v in {'filename':str(SOURCE/e['file']),'destination_path':ASSET_ROOT,'destination_name':e['name'],'automated':True,'replace_existing':True,'save':False,'options':options,'factory':unreal.FbxFactory()}.items():task.set_editor_property(p,v)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);mesh=unreal.load_asset(path);assert isinstance(mesh,unreal.StaticMesh)
        for i,slot in enumerate(mesh.static_materials):
            name=str(slot.material_slot_name);mat=next((v for k,v in mats.items() if k.lower() in name.lower()),None);assert mat,name;mesh.set_material(i,mat)
        source_sha=hashlib.sha256((SOURCE/e['file']).read_bytes()).hexdigest()
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,'OldTownOpeningSourceSHA256',source_sha)
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,False)
        assets[e['name']]=mesh;imports.append({'asset':mesh.get_path_name(),'source':e['file'],'source_sha256':source_sha})
    axes=_infer_axes(manifest['assets'],assets)
    assert tuple(axes['order'])==(0,1,2) and axes['signs'][0]==1 and axes['signs'][2]==1,axes
    (SOURCE/'UnrealAxisVerification.json').write_text(json.dumps(axes,indent=2))
    (WORK/'OpeningImportReport.json').write_text(json.dumps({'imports':imports,'axes':axes},indent=2))
    unreal.log('OPENING_ASSETS_IMPORT_PASS '+str(len(assets)))
    return assets,imports,axes

if __name__=='__main__':import_assets()
