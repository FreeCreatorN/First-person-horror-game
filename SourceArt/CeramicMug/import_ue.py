import unreal,os,json,traceback
OUT=r'D:\UE\Project\HorrorGame\SourceArt\CeramicMug';ROOT='/Game/Yastars/Mesh/CeramicMug';report={}
try:
 edit=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();ml=unreal.MaterialEditingLibrary
 edit.make_directory(ROOT+'/Materials');mats={}
 specs={'M_Mug_IvoryGlaze':((.63,.55,.41),.23),'M_Mug_UnglazedFoot':((.34,.24,.15),.85),'M_Mug_OliveBand':((.11,.14,.105),.3),'M_Mug_Water':((.25,.55,.65),.06)}
 for name,(col,rough) in specs.items():
  m=edit.load_asset(ROOT+'/Materials/'+name) or tools.create_asset(name,ROOT+'/Materials',unreal.Material,unreal.MaterialFactoryNew());ml.delete_all_material_expressions(m)
  c=ml.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-300,0);c.constant=unreal.LinearColor(*col,1);ml.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
  r=ml.create_material_expression(m,unreal.MaterialExpressionConstant,-300,180);r.r=rough;ml.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
  if name=='M_Mug_Water':
   m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT);m.set_editor_property('two_sided',True)
   a=ml.create_material_expression(m,unreal.MaterialExpressionConstant,-300,300);a.r=.32;ml.connect_material_property(a,'',unreal.MaterialProperty.MP_OPACITY)
  ml.recompile_material(m);edit.save_loaded_asset(m,False);mats[name]=m
 def imp(file,name,opts):
  t=unreal.AssetImportTask();t.filename=OUT+'/'+file;t.destination_path=ROOT;t.destination_name=name;t.automated=True;t.replace_existing=True;t.save=True;t.options=opts;tools.import_asset_tasks([t]);a=edit.load_asset(ROOT+'/'+name);assert a,name;return a
 opt=unreal.FbxImportUI()
 for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():opt.set_editor_property(k,v)
 for k,v in {'import_uniform_scale':100.0,'combine_meshes':True,'auto_generate_collision':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():opt.static_mesh_import_data.set_editor_property(k,v)
 mesh=imp('SM_CeramicMug.fbx','SM_CeramicMug',opt)
 for i,slot in enumerate(mesh.static_materials):mesh.set_material(i,mats[str(slot.material_slot_name)])
 edit.save_loaded_asset(mesh,False);report['height_cm']=mesh.get_bounds().box_extent.z*2;assert 9<report['height_cm']<11,report
 abc=unreal.AbcImportSettings();abc.import_type=unreal.AlembicImportType.GEOMETRY_CACHE
 sample=abc.sampling_settings;sample.frame_start=1;sample.frame_end=220;abc.sampling_settings=sample
 conv=abc.conversion_settings;conv.scale=unreal.Vector(100,-100,100);conv.rotation=unreal.Vector(90,0,0);abc.conversion_settings=conv
 ma=abc.material_settings;ma.find_materials=True;ma.create_materials=False;abc.material_settings=ma
 cache=imp('GC_CeramicMug_Pouring.abc','GC_CeramicMug_Pouring',abc)
 report['materials']=[m.get_path_name() if m else None for m in cache.get_editor_property('materials')];assert all(report['materials'])
 actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.GeometryCacheActor,unreal.Vector())
 comp=actor.get_component_by_class(unreal.GeometryCacheComponent);comp.set_geometry_cache(cache);report['duration_seconds']=comp.get_duration();assert 9<report['duration_seconds']<10
 report['mesh']=mesh.get_path_name();report['animation']=cache.get_path_name();report['success']=True
except Exception:report['success']=False;report['error']=traceback.format_exc()
with open(OUT+'/ue_import_report.json','w') as f:json.dump(report,f,indent=2)
unreal.log('MUG_IMPORT_RESULT '+json.dumps(report))
