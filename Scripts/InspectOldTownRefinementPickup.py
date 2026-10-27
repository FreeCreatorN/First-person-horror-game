import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import InspectOldTownRealismInput as n
from ApplyOldTownRealismRefinement import stable_actor,sha
W=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
n.WORK=W/'PickupPreflight'
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet')
actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
a=next(x for x in actors if x.get_actor_label()=='BP_ItemPickup')
bp=unreal.load_asset('/Game/Yastar/Items/BP_ItemPickup')
cdo=unreal.get_default_object(a.get_class())
at,ar=n.native_text_export(a,W/'PickupPreflight/Actor.t3d')
bt,br=n.native_text_export(bp,W/'PickupPreflight/Blueprint.t3d')
ct,cr=n.native_text_export(cdo,W/'PickupPreflight/Defaults.t3d')
c=a.get_component_by_class(unreal.StaticMeshComponent)
out=dict(actor_state=stable_actor(a),component=n.component_record(c),actor_properties=n.reflect_editor_properties(a),
 cdo_properties=n.reflect_editor_properties(cdo),asset=n.record_source(bp),native_export=[ar,br,cr])
(W/'PickupPreflight.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('PICKUP_PREFLIGHT_PASS')
