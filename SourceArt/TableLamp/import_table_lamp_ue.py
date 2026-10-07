import unreal,json,traceback,os
OUT=r'D:\UE\Project\HorrorGame\SourceArt\TableLamp'
ROOT='/Game/Yastars/Mesh'
def main():
 tools=unreal.AssetToolsHelpers.get_asset_tools();edit=unreal.EditorAssetLibrary;ml=unreal.MaterialEditingLibrary
 for path in [ROOT,ROOT+'/Materials',ROOT+'/Textures']:edit.make_directory(path)
 opts=unreal.FbxImportUI()
 for key,value in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():opts.set_editor_property(key,value)
 for key,value in {'import_uniform_scale':100.0,'remove_degenerates':False,'combine_meshes':True,'auto_generate_collision':False,'one_convex_hull_per_ucx':True,'generate_lightmap_u_vs':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():opts.static_mesh_import_data.set_editor_property(key,value)
 def imp(filename,path,name,options=None):
  t=unreal.AssetImportTask();t.filename=os.path.join(OUT,filename);t.destination_path=path;t.destination_name=name;t.automated=True;t.replace_existing=True;t.replace_existing_settings=True;t.save=True
  if options:t.options=options
  tools.import_asset_tasks([t]);return edit.load_asset(path+'/'+name)
 if edit.does_asset_exist(ROOT+'/SM_TableLamp'):edit.delete_asset(ROOT+'/SM_TableLamp')
 mesh=imp('SM_TableLamp.fbx',ROOT,'SM_TableLamp',opts);assert isinstance(mesh,unreal.StaticMesh),'Mesh import failed'
 tex=imp('T_TableLamp_Weave.png',ROOT+'/Textures','T_TableLamp_Weave');assert tex
 tex.set_editor_property('srgb',False);tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_GRAYSCALE);edit.save_loaded_asset(tex,False)
 specs={'M_TableLamp_Brass':((.31,.185,.065,1),.31,.82),'M_TableLamp_Cord':((.022,.017,.012,1),.82,0),'M_TableLamp_Socket':((.12,.10,.076,1),.42,0),'M_TableLamp_Linen':((.66,.51,.31,1),.88,0),'M_TableLamp_Bulb':((.85,.64,.30,1),.24,0)}
 materials={}
 def expr(m,cls,x,y):return ml.create_material_expression(m,cls,x,y)
 for name,(col,rough,metal) in specs.items():
  mat=edit.load_asset(ROOT+'/Materials/'+name)
  if not mat:mat=tools.create_asset(name,ROOT+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
  ml.delete_all_material_expressions(mat)
  c=expr(mat,unreal.MaterialExpressionConstant3Vector,-500,0);c.constant=unreal.LinearColor(*col);ml.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
  for val,prop,y in [(rough,unreal.MaterialProperty.MP_ROUGHNESS,180),(metal,unreal.MaterialProperty.MP_METALLIC,260)]:
   n=expr(mat,unreal.MaterialExpressionConstant,-250,y);n.r=val;ml.connect_material_property(n,'',prop)
  if name=='M_TableLamp_Linen':
   mat.set_editor_property('two_sided',True)
   uv=expr(mat,unreal.MaterialExpressionTextureCoordinate,-900,-200);uv.set_editor_property('u_tiling',8.0);uv.set_editor_property('v_tiling',8.0)
   t=expr(mat,unreal.MaterialExpressionTextureSample,-650,-180);t.texture=tex;t.sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE;ml.connect_material_expressions(uv,'',t,'UVs')
   mul=expr(mat,unreal.MaterialExpressionMultiply,-200,0);ml.connect_material_expressions(c,'',mul,'A');ml.connect_material_expressions(t,'RGB',mul,'B');ml.connect_material_property(mul,'',unreal.MaterialProperty.MP_BASE_COLOR)
  if name=='M_TableLamp_Bulb':
   em=expr(mat,unreal.MaterialExpressionConstant3Vector,-200,350);em.constant=unreal.LinearColor(3,1.56,.48,1);ml.connect_material_property(em,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
  ml.recompile_material(mat);edit.save_loaded_asset(mat,False);materials[name]=mat
 slots=[]
 for i,slot in enumerate(mesh.static_materials):
  name=str(slot.material_slot_name);key=next((k for k in materials if name.startswith(k)),None);assert key,name
  mesh.set_material(i,materials[key]);slots.append(key)
 mesh.set_editor_property('light_map_resolution',128);mesh.set_editor_property('light_map_coordinate_index',1);edit.save_loaded_asset(mesh,False)
 bounds=mesh.get_bounds();height=bounds.box_extent.z*2;unreal.log('LAMP_DIAGNOSTIC '+str(bounds)+' SCALE '+str(mesh.get_editor_property('asset_import_data').get_editor_property('import_uniform_scale')));assert 53<height<57,height;assert len(slots)==5,slots
 sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem);collision=sub.get_convex_collision_count(mesh);assert collision>=3,collision
 report={'asset':mesh.get_path_name(),'height_cm':height,'material_slots':slots,'convex_collision_hulls':collision,'saved':True}
 with open(os.path.join(OUT,'ue_import_report.json'),'w') as f:json.dump(report,f,indent=2)
 unreal.log('TABLE_LAMP_IMPORT_SUCCESS '+json.dumps(report))
try:main()
except Exception:
 with open(os.path.join(OUT,'ue_import_report.json'),'w') as f:json.dump({'saved':False,'error':traceback.format_exc()},f,indent=2)
 raise




