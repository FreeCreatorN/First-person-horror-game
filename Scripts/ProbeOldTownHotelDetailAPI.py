import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha
WORK=ROOT/'Saved/CodexOutputs/HotelDetails_20261009';WORK.mkdir(exist_ok=True,parents=True)
BASE=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
old=json.loads((BASE/'AfterSnapshot.json').read_text(encoding='utf-8'))
target='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
assert sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==old['source_map_sha256']
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target)
actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
current={a.get_actor_label():actor_state(a) for a in actors};assert current==old['actors']
(WORK/'InputSnapshot.json').write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8')
docs={n:getattr(unreal.Actor,n).__doc__ for n in ('attach_to_component','set_actor_relative_location','set_actor_relative_rotation','set_actor_relative_scale3d')}
cyl=unreal.load_asset('/Engine/BasicShapes/Cylinder.Cylinder');body=cyl.get_editor_property('body_setup')
agg=body.get_editor_property('agg_geom')
docs['cylinder_collision']=dict(trace=str(body.get_editor_property('collision_trace_flag')),
    shapes={n:len(agg.get_editor_property(n)) for n in ('box_elems','sphere_elems','sphyl_elems','convex_elems')})
(WORK/'APIDocs.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('HOTEL_DETAIL_API_PASS '+str(len(actors)))
