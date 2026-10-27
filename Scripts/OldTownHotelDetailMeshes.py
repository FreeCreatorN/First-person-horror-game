"""Independent immutable hinge meshes; no changes to shared source assets."""
import hashlib,json
from pathlib import Path
import unreal
from OldTownDoorHingeGeometry import primitive_specs,validate_recipe
ROOT=Path(unreal.Paths.project_dir()).resolve()
ASSETS='/Game/CodexGenerated/OldTown/Meshes/HotelDetails_20261009'

def _result(r):
    if isinstance(r,tuple):
        assert r[1]==unreal.GeometryScriptOutcomePins.SUCCESS,r
        return r[0]
    return r

def hinge_asset(row,moving,material):
    recipe=primitive_specs(row['width'],row['height'],row.get('depth',20),row.get('hinge_side',1))
    assert validate_recipe(row)['passed']
    pieces=recipe['moving' if moving else 'fixed']
    encoded=json.dumps(pieces,sort_keys=True,separators=(',',':'))
    suffix=hashlib.sha256(encoded.encode()).hexdigest()[:12]
    path=ASSETS+'/SM_OTS_Hinge_'+('Moving_' if moving else 'Fixed_')+suffix
    assets=unreal.EditorAssetLibrary
    if assets.does_asset_exist(path):
        mesh=unreal.load_asset(path)
        assert assets.get_metadata_tag(mesh,'CodexHingeRecipe')==encoded
    else:
        assets.make_directory(ASSETS)
        dynamic=unreal.DynamicMesh();options=unreal.GeometryScriptPrimitiveOptions()
        options.set_editor_property('material_id',0)
        for part in pieces:
            rot=unreal.Rotator(pitch=0,yaw=part.get('yaw_deg',0),roll=0)
            transform=unreal.Transform(location=unreal.Vector(*part['center']),rotation=rot,scale=unreal.Vector(1,1,1))
            if part['kind']=='box':
                dynamic=_result(unreal.GeometryScript_Primitives.append_box(dynamic,options,transform,
                    *part['size'],0,0,0,unreal.GeometryScriptPrimitiveOriginMode.CENTER))
            else:
                dynamic=_result(unreal.GeometryScript_Primitives.append_cylinder(dynamic,options,transform,
                    part['radius'],part['height'],24,1,True,unreal.GeometryScriptPrimitiveOriginMode.CENTER))
        create=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        for k,v in dict(enable_recompute_normals=True,enable_recompute_tangents=True,enable_nanite=False,enable_collision=False).items():create.set_editor_property(k,v)
        mesh=_result(unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,path,create))
        copy=unreal.GeometryScriptCopyMeshToAssetOptions()
        for k,v in dict(enable_recompute_normals=True,enable_recompute_tangents=True,replace_materials=True,
            new_materials=[material],new_material_slot_names=[unreal.Name('OldMetal')],emit_transaction=False).items():copy.set_editor_property(k,v)
        lod=unreal.GeometryScriptMeshWriteLOD();lod.set_editor_property('lod_index',0)
        _result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,mesh,copy,lod,True))
        assets.set_metadata_tag(mesh,'CodexHingeRecipe',encoded)
        assert assets.save_loaded_asset(mesh,False),path
    file=ROOT/('Content/'+path[6:]+'.uasset')
    return mesh,dict(asset=mesh.get_path_name(),file=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
        assembly='moving' if moving else 'fixed',primitive_count=len(pieces),hinges=3,recipe=recipe,
        no_collision=True,source='independent GeometryScript closed box/cylinder mesh')
