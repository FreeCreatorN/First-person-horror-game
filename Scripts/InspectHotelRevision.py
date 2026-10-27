"""Fresh read-only baseline, including any user edits since the last repair."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelRevisionCommon import *
from InspectOldTownHotelDoorClosure_20261019 import component
from BuildOldTownOpeningBlueprints import _templates

def main():
    assert not (W/'Inspection.json').exists()
    before=files();write('ProtectedBefore.json',dict(file_sha256=before))
    le,ae,world,actors,by=load()
    doors=[a for a in actors if a.get_actor_label().startswith('OTS_HotelV4_Door_') and a.get_class().get_path_name().startswith('/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door')]
    for a in doors:own(a)
    rows=[];blueprints={};sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for a in doors:
        cs=components(a);kind='swing' if cs.get('DoorLeaf') and cs['DoorLeaf'].static_mesh else 'slider'
        rows.append(dict(label=a.get_actor_label(),name=a.get_name(),path=a.get_path_name(),class_path=a.get_class().get_path_name(),kind=kind,
            transform=native.value(a.get_actor_transform()),tags=[str(t) for t in a.tags],folder=str(a.get_folder_path()),components=[component(c) for c in cs.values()]))
        path=a.get_class().get_path_name().split('.')[0]
        assert path.startswith('/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door'),path
        if path not in blueprints:
            bp=unreal.load_asset(path);export=W/'BlueprintNative'/(Path(path).name+'.t3d');_,proof=native.native_text_export(bp,export);assert proof['passed']
            blueprints[path]=dict(native_file=str(export),templates={n:component(c) for n,(_,c) in _templates(sub,bp).items()})
    chosen=[a for a in actors if a.get_actor_label().startswith(('OTS_HotelV4_South_','OTS_HotelV4_North_','OTS_HotelV4_F0_StreetWall','OTS_HotelV4_GroundRearWindow')) or a.get_actor_label() in ['OTS_HotelV4_'+n for n in ('CleanLinenShelf','DirtyLinenShelf','ChangingShelf','EquipmentShelf','CleanLinenShelf_DoorTrim','DirtyLinenShelf_DoorTrim','ChangingShelf_DoorTrim','EquipmentShelf_DoorTrim','ExitThreshold_0','ExitThreshold_64','ServiceEntryThreshold')]]
    write('Candidates.json',dict(actors=[dict(label=a.get_actor_label(),name=a.get_name(),class_path=a.get_class().get_path_name(),tags=[str(t) for t in a.tags],components=[component(c) for c in a.get_components_by_class(unreal.SceneComponent)]) for a in chosen]))
    write('Doors.json',dict(doors=rows,blueprints=blueprints))
    # Import above inspector initializes base.W to its legacy workdir. Restore it.
    base.W=W;base.TAG='HotelRevision_NoExistingActorExclusion'
    write('BeforeScene.json',snapshot(actors,'BeforeRevision',world))
    assert native.sha(MAP)==before[str(MAP)],'Original map was saved during inspection; repeat fresh baseline'
    write('Inspection.json',dict(passed=True,source_map_sha256=before[str(MAP)],actor_count=len(actors),doors=len(doors),blueprints=len(blueprints),protection=protect(before),no_save=True))
    unreal.log('HOTEL_REVISION_INSPECT_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('InspectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
