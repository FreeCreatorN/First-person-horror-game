import unreal,os,json,traceback
OUT=r'D:\UE\Project\HorrorGame\SourceArt\KraftBook';ROOT='/Game/Yastars/Mesh';BOOK=ROOT+'/KraftBook';LAMP=ROOT+'/TableLamp'
report={}
try:
 edit=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();ml=unreal.MaterialEditingLibrary
 for path in [BOOK,BOOK+'/Materials',LAMP,LAMP+'/Materials',LAMP+'/Textures']:edit.make_directory(path)
 moved=[]
 for src in edit.list_assets(ROOT,True,False):
  package=src.split('.')[0];name=package.rsplit('/',1)[-1]
  if package.startswith(LAMP+'/') or package.startswith(BOOK+'/'):continue
  if name=='SM_TableLamp':dst=LAMP+'/'+name
  elif name.startswith('M_TableLamp_'):dst=LAMP+'/Materials/'+name
  elif name.startswith('T_TableLamp_'):dst=LAMP+'/Textures/'+name
  else:continue
  obj=edit.load_asset(package)
  if obj and obj.get_class().get_name()=='ObjectRedirector':continue
  if not edit.does_asset_exist(dst):assert edit.rename_asset(package,dst),package;moved.append([package,dst])
 edit.save_directory(LAMP,False,True);report['lamp_moved']=moved
 mats={}
 specs={'M_Book_Kraft':(.34,.205,.092),'M_Book_Crease':(.15,.071,.024),'M_Book_Ribbon':(.16,.062,.027)}
 for i in range(6):
  v=.65+i*.028;specs['M_Book_Paper_%02d'%i]=(v,v*.91,v*.73)
 for name,col in specs.items():
  m=edit.load_asset(BOOK+'/Materials/'+name) or tools.create_asset(name,BOOK+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
  ml.delete_all_material_expressions(m);m.set_editor_property('two_sided',True)
  c=ml.create_material_expression(m,unreal.MaterialExpressionConstant3Vector,-250,0);c.constant=unreal.LinearColor(*col,1);ml.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
  r=ml.create_material_expression(m,unreal.MaterialExpressionConstant,-250,150);r.r=.85;ml.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
  ml.recompile_material(m);edit.save_loaded_asset(m,False);mats[name]=m
 def imp(filename,name,options):
  task=unreal.AssetImportTask();task.filename=os.path.join(OUT,filename);task.destination_path=BOOK;task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=True;task.options=options
  tools.import_asset_tasks([task]);a=edit.load_asset(BOOK+'/'+name);assert a,(name,task.imported_object_paths);return a
 opts=unreal.FbxImportUI()
 for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():opts.set_editor_property(k,v)
 for k,v in {'import_uniform_scale':100.0,'combine_meshes':True,'auto_generate_collision':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():opts.static_mesh_import_data.set_editor_property(k,v)
 mesh=imp('SM_KraftBook.fbx','SM_KraftBook',opts)
 for i,slot in enumerate(mesh.static_materials):
  key=next((k for k in mats if str(slot.material_slot_name).startswith(k)),None)
  assert key,str(slot.material_slot_name);mesh.set_material(i,mats[key])
 edit.save_loaded_asset(mesh,False)
 report['static_mesh']=mesh.get_path_name();report['closed_height_cm']=mesh.get_bounds().box_extent.z*2
 abc=unreal.AbcImportSettings();abc.import_type=unreal.AlembicImportType.GEOMETRY_CACHE
 sampling=abc.sampling_settings;sampling.frame_start=1;sampling.frame_end=1632;abc.sampling_settings=sampling
 conv=abc.conversion_settings;conv.scale=unreal.Vector(100,-100,100);conv.rotation=unreal.Vector(90,0,0);abc.conversion_settings=conv
 mat=abc.material_settings;mat.find_materials=True;mat.create_materials=False;abc.material_settings=mat
 settings=abc.geometry_cache_settings;settings.flatten_tracks=True;settings.compressed_position_precision=.0005;abc.geometry_cache_settings=settings
 cache=imp('GC_KraftBook_FullCycle.abc','GC_KraftBook_FullCycle',abc)
 report['animation']=cache.get_path_name();report['animation_class']=cache.get_class().get_name()
 report['animation_materials']=[str(m.get_path_name()) if m else None for m in cache.get_editor_property('materials')]
 assert all(report['animation_materials']),report
 edit.save_loaded_asset(cache,False)
 assert 2<report['closed_height_cm']<3,report
 assert edit.does_asset_exist(LAMP+'/SM_TableLamp')
 report['success']=True
except Exception:report['error']=traceback.format_exc();report['success']=False
with open(os.path.join(OUT,'ue_import_report.json'),'w') as f:json.dump(report,f,indent=2)
unreal.log('BOOK_IMPORT_RESULT '+json.dumps(report))
