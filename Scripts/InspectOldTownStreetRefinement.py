"""Read saved street/guesthouse geometry before a targeted refinement."""
import json
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from PolishOldTownDetails import actor_bounds
WORK=ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'

def main():
    WORK.mkdir(exist_ok=True)
    path=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';before=sha(path)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(sub.get_all_level_actors())
    rows={}
    for a in actors:
        n=a.get_actor_label()
        if n.startswith(('OTS_P2Prop_StreetLamp_','OTS_Light_StreetLamp','OTS_UtilityPole_02_','OTS_OverheadWire_')) or n in ('OTS_RoadRevision_MainRoad','OTS_RoadRevision_MainWalkNorth','OTS_RoadRevision_MainWalkSouth','OTS_RoadRevision_EastBoundaryWalk'):
            meshes=[c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]
            rows[n]=dict(state=actor_state(a),bounds=actor_bounds(a) if meshes else None)
            if n in ('OTS_OverheadWire_03','OTS_OverheadWire_06','OTS_OverheadWire_09'):
                c=meshes[0];t=c.get_world_transform();b=c.static_mesh.get_bounds()
                ends=[xyz(t.transform_location(unreal.Vector(b.origin.x+s*b.box_extent.x,b.origin.y,b.origin.z))) for s in (-1,1)]
                rows[n]['endpoints_cm']=sorted(ends,key=lambda p:p[0])
    assert sha(path)==before
    (WORK/'Inspection.json').write_text(json.dumps(dict(map_sha256=before,actor_count=len(actors),actors=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('STREET_REFINEMENT_INSPECT_PASS actors='+str(len(actors))+' selected='+str(len(rows)))

if __name__=='__main__':main()
