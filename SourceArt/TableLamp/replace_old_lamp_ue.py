import unreal,json,os,traceback
OUT=r'D:\UE\Project\HorrorGame\SourceArt\TableLamp';ROOT='/Game/Yastars/Mesh'
try:
 edit=unreal.EditorAssetLibrary;mesh=edit.load_asset(ROOT+'/SM_TableLamp');assert isinstance(mesh,unreal.StaticMesh)
 old_slots=[slot.material_interface for slot in mesh.static_materials]
 assert edit.delete_asset(ROOT+'/SM_TableLamp'),'Could not delete the old lamp'
 assert not edit.does_asset_exist(ROOT+'/SM_TableLamp'),'Old lamp still exists'
 opts=unreal.FbxImportUI()
 for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():opts.set_editor_property(k,v)
 for k,v in {'import_uniform_scale':100.0,'remove_degenerates':False,'combine_meshes':True,'auto_generate_collision':False,'one_convex_hull_per_ucx':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():opts.static_mesh_import_data.set_editor_property(k,v)

 t=unreal.AssetImportTask();t.filename=os.path.join(OUT,'SM_TableLamp.fbx');t.destination_path=ROOT;t.destination_name='SM_TableLamp';t.automated=True;t.replace_existing=True;t.replace_existing_settings=True;t.save=True;t.options=opts
 unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t]);mesh=edit.load_asset(ROOT+'/SM_TableLamp')
 assert len(mesh.static_materials)==len(old_slots)==5
 for i,m in enumerate(old_slots):mesh.set_material(i,m)
 mesh.set_editor_property('light_map_resolution',128);mesh.set_editor_property('light_map_coordinate_index',1)
 height=mesh.get_bounds().box_extent.z*2;assert abs(height-54.8)<.1,height
 sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem);hulls=sub.get_convex_collision_count(mesh);assert hulls==3,hulls
 assert edit.save_loaded_asset(mesh,False)
 report={'asset':mesh.get_path_name(),'height_cm':height,'material_slots':[str(x.material_slot_name) for x in mesh.static_materials],'convex_collision_hulls':hulls,'old_asset_deleted':True,'connections_fixed':True,'saved':True}
 with open(os.path.join(OUT,'ue_replacement_report.json'),'w') as f:json.dump(report,f,indent=2)
 unreal.log('LAMP_CONNECTION_UPDATE_SUCCESS '+json.dumps(report))
except Exception:
 with open(os.path.join(OUT,'ue_replacement_report.json'),'w') as f:json.dump({'saved':False,'error':traceback.format_exc()},f,indent=2)
 raise

