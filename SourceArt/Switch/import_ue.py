import unreal, json, traceback
from pathlib import Path
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\Switch')
ROOT='/Game/Yastars/Mesh/Switch'
report={'success':False,'assets':{}}
try:
    e=unreal.EditorAssetLibrary
    t=unreal.AssetToolsHelpers.get_asset_tools()
    ml=unreal.MaterialEditingLibrary
    e.make_directory(ROOT+'/Materials')
    mats={}
    for name,col,metal,rough in [('M_Switch_Ivory',(.72,.70,.64),0,.29),('M_Switch_Charcoal',(.025,.029,.031),0,.52),('M_Switch_Steel',(.34,.37,.40),.8,.32)]:
        existing=e.load_asset(ROOT+'/Materials/'+name)
        m=existing or t.create_asset(name,ROOT+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        assert m,name
        # Preserve any material already edited by the user on later reimports.
        if not existing:
            c=ml.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-300,0)
            c.constant=unreal.LinearColor(*col,1)
            ml.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
            for value,prop,y in [(metal,unreal.MaterialProperty.MP_METALLIC,150),(rough,unreal.MaterialProperty.MP_ROUGHNESS,260)]:
                n=ml.create_material_expression(m,unreal.MaterialExpressionConstant,-300,y)
                n.r=value;ml.connect_material_property(n,'',prop)
            ml.recompile_material(m)
        mats[name]=m
    imported=[]
    for name,expected_hulls in [('SM_Switch_Base',5),('SM_Switch_Rocker',1)]:
        opt=unreal.FbxImportUI()
        for key,value in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
            opt.set_editor_property(key,value)
        for key,value in {'import_uniform_scale':100.,'combine_meshes':True,'auto_generate_collision':False,'one_convex_hull_per_ucx':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,'transform_vertex_to_absolute':True,'bake_pivot_in_vertex':False}.items():
            opt.static_mesh_import_data.set_editor_property(key,value)
        task=unreal.AssetImportTask()
        task.filename=str(OUT/(name+'.fbx'));task.destination_path=ROOT;task.destination_name=name
        task.automated=True;task.replace_existing=True;task.save=False;task.options=opt
        t.import_asset_tasks([task])
        mesh=e.load_asset(ROOT+'/'+name);assert mesh,name
        for i,slot in enumerate(mesh.static_materials):
            mat_name=str(slot.material_slot_name);assert mat_name in mats,mat_name
            mesh.set_material(i,mats[mat_name])
        mesh.set_editor_property('light_map_resolution',128)
        bounds=mesh.get_bounds();ext=bounds.box_extent;origin=bounds.origin
        body=mesh.get_editor_property('body_setup')
        agg=body.get_editor_property('agg_geom')
        convex=len(agg.get_editor_property('convex_elems'))
        assert convex==expected_hulls,(name,convex)
        dims=[ext.x*2,ext.y*2,ext.z*2]
        assert 8.59<max(dims)<8.61 if name.endswith('Base') else 5.79<max(dims)<5.81,(name,dims)
        report['assets'][name]={'asset':mesh.get_path_name(),'dimensions_cm':dims,'bounds_origin_cm':[origin.x,origin.y,origin.z],'convex_collision_hulls':convex,'materials':[slot.material_interface.get_path_name() for slot in mesh.static_materials]}
        imported.append(mesh)
    # Determine the FBX axis conversion from the intentionally asymmetric base.
    base_origin=report['assets']['SM_Switch_Base']['bounds_origin_cm']
    depth_axis=max(range(2),key=lambda i:abs(base_origin[i]))
    offset=[0.,0.,0.];offset[depth_axis]=-.3 if base_origin[depth_axis]>0 else .3
    report['assembly']={'rocker_relative_location_cm':offset,'rocker_rotation_axis':'Y' if depth_axis==0 else 'X','rocker_angle_degrees':[-4,4],'base_wall_origin':[0,0,0]}
    for asset in list(mats.values())+imported:assert e.save_loaded_asset(asset,False),asset.get_path_name()
    report['success']=True
except Exception:
    report['error']=traceback.format_exc()
(OUT/'ue_import_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('SWITCH_IMPORT '+json.dumps(report))
