import unreal,json,traceback
OUT=r'D:\UE\Project\HorrorGame\SourceArt\FlowerPot';ROOT='/Game/Yastars/Mesh/FlowerPot';report={}
try:
 e=unreal.EditorAssetLibrary;t=unreal.AssetToolsHelpers.get_asset_tools();ml=unreal.MaterialEditingLibrary;e.make_directory(ROOT+'/Materials');mats={}
 for name,col,metal,rough in [('M_FlowerPot_Terracotta',(.36,.13,.062),0,.82),('M_FlowerPot_Soil',(.046,.026,.012),0,.9),('M_FlowerPot_Green',(.07,.19,.035),0,.7),('M_FlowerPot_Petals',(.88,.82,.66),0,.7),('M_FlowerPot_Pollen',(.65,.30,.022),0,.8)]:
  m=e.load_asset(ROOT+'/Materials/'+name) or t.create_asset(name,ROOT+'/Materials',unreal.Material,unreal.MaterialFactoryNew());ml.delete_all_material_expressions(m)
  c=ml.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-300,0);c.constant=unreal.LinearColor(*col,1);ml.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
  for value,prop,y in [(metal,unreal.MaterialProperty.MP_METALLIC,150),(rough,unreal.MaterialProperty.MP_ROUGHNESS,260)]:
   n=ml.create_material_expression(m,unreal.MaterialExpressionConstant,-300,y);n.r=value;ml.connect_material_property(n,'',prop)
  ml.recompile_material(m);e.save_loaded_asset(m,False);mats[name]=m
 opt=unreal.FbxImportUI()
 for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():opt.set_editor_property(k,v)
 for k,v in {'import_uniform_scale':100.0,'combine_meshes':True,'auto_generate_collision':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():opt.static_mesh_import_data.set_editor_property(k,v)
 task=unreal.AssetImportTask();task.filename=OUT+'/SM_FlowerPot.fbx';task.destination_path=ROOT;task.destination_name='SM_FlowerPot';task.automated=True;task.replace_existing=True;task.save=True;task.options=opt;t.import_asset_tasks([task])
 mesh=e.load_asset(ROOT+'/SM_FlowerPot');assert mesh
 for i,slot in enumerate(mesh.static_materials):
  name=str(slot.material_slot_name);assert name in mats,name;mesh.set_material(i,mats[name])
 mesh.set_editor_property('light_map_resolution',128);e.save_loaded_asset(mesh,False)
 ext=mesh.get_bounds().box_extent;report['dimensions_cm']=[ext.x*2,ext.y*2,ext.z*2];assert 45<ext.z*2<50,report
 report['asset']=mesh.get_path_name();report['materials']=[x.material_interface.get_path_name() for x in mesh.static_materials];report['success']=True
except Exception:report['success']=False;report['error']=traceback.format_exc()
with open(OUT+'/ue_import_report.json','w') as f:json.dump(report,f,indent=2)
unreal.log('DOOR_HANDLE_IMPORT '+json.dumps(report))



