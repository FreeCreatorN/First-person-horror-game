import unreal,json,traceback,os
OUT=r'D:\UE\Project\HorrorGame\SourceArt\KraftBook';ROOT='/Game/Yastars/Mesh/KraftBook';report={}
try:
 edit=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();ml=unreal.MaterialEditingLibrary
 edit.make_directory(ROOT+'/Textures')
 task=unreal.AssetImportTask();task.filename=OUT+'/T_Book_Kraft.png';task.destination_path=ROOT+'/Textures';task.destination_name='T_Book_Kraft';task.automated=True;task.replace_existing=True;task.save=True;tools.import_asset_tasks([task])
 tex=edit.load_asset(ROOT+'/Textures/T_Book_Kraft');assert tex
 mat=edit.load_asset(ROOT+'/Materials/M_Book_Kraft')
 sample=ml.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-500,-200);sample.texture=tex;ml.connect_material_property(sample,'RGB',unreal.MaterialProperty.MP_BASE_COLOR);ml.recompile_material(mat);edit.save_loaded_asset(mat,False)
 cache=edit.load_asset(ROOT+'/GC_KraftBook_FullCycle');assert cache
 actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.GeometryCacheActor,unreal.Vector())
 comp=actor.get_component_by_class(unreal.GeometryCacheComponent);assert comp.set_geometry_cache(cache)
 report['duration_seconds']=comp.get_duration();assert 67<report['duration_seconds']<69,report
 report['samples']=[]
 for t in [0,30,67]:
  comp.tick_at_this_time(t,True,False,False)
  origin,extent=actor.get_actor_bounds(False)
  report['samples'].append({'time':t,'extent_cm':[extent.x,extent.y,extent.z]})
 report['cache_materials']=[m.get_path_name() if m else None for m in cache.get_editor_property('materials')]
 assert all('/KraftBook/Materials/' in str(m) for m in report['cache_materials']),report
 lamp=edit.load_asset('/Game/Yastars/Mesh/TableLamp/SM_TableLamp');assert lamp
 report['lamp_materials']=[slot.material_interface.get_path_name() for slot in lamp.static_materials]
 assert all('/TableLamp/Materials/' in m for m in report['lamp_materials'])
 report['success']=True
except Exception:report['success']=False;report['error']=traceback.format_exc()
with open(OUT+'/ue_validation.json','w') as f:json.dump(report,f,indent=2)
unreal.log('BOOK_VALIDATION '+json.dumps(report))
