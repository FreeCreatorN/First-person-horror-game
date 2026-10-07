"""Use UE asset rename, resave direct referencers, and preserve all recorded actor fields."""
import json
import sys
import traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from InspectOldTownOpeningRelocation import OLD,NEW,WORK,write,template_state,package_file
from PolishOldTownHotel import actor_state,sha
from OldTownAssetRelocation import normalize_paths


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    assert not (WORK/'Moved.json').exists(),'Move was already saved; use fresh relocation validation.'
    inventory=read(WORK/'Inventory.json');snapshots=read(WORK/'ActorSnapshots.json')
    relocations=[dict(old=r['old'],new=r['new']) for r in inventory['assets']]
    assert all(sha(package_file(p))==h for p,h in inventory['source_map_sha256'].items())
    assert not unreal.EditorAssetLibrary.list_assets(NEW,True,False),'Destination changed since inventory.'
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assets=[];default_states={}
    for row in inventory['assets']:
        bp=unreal.load_asset(row['old']);assert isinstance(bp,unreal.Blueprint)
        assert template_state(bp)==row['templates']
        cls=unreal.EditorAssetLibrary.load_blueprint_class(row['old'])
        a=sub.spawn_actor_from_class(cls,unreal.Vector(0,0,50000),unreal.Rotator(pitch=0,yaw=0,roll=0),False)
        state=actor_state(a);state.pop('name');default_states[row['new']]=normalize_paths(state,relocations)
        assert sub.destroy_actor(a)
        assets.append(bp)
    renames=[unreal.AssetRenameData(asset=bp,new_package_path=NEW,new_name=row['new'].rsplit('/',1)[1])
             for bp,row in zip(assets,inventory['assets'])]
    unreal.EditorAssetLibrary.make_directory(NEW)
    write('DefaultActorStates.json',default_states)
    assert unreal.AssetToolsHelpers.get_asset_tools().rename_assets(renames),'UE asset rename failed.'
    write('RenameStage.json',dict(renamed=True,assets=relocations))
    for bp,row in zip(assets,inventory['assets']):
        assert bp.get_path_name().split('.')[0]==row['new']
        assert template_state(bp)==normalize_paths(row['templates'],relocations)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    map_checks=[]
    for p in inventory['referencer_maps']:
        assert level.load_level(p)
        actors=list(sub.get_all_level_actors());current={a.get_actor_label():actor_state(a) for a in actors}
        expected=normalize_paths(snapshots[p],relocations)
        changed=[n for n,s in expected.items() if current.get(n)!=s]
        assert not changed and set(current)==set(expected),(p,changed[:5])
        assert level.save_current_level()
        map_checks.append(dict(level=p,actor_count=len(current),recorded_actor_fields_preserved=True,
                              old_sha256=inventory['source_map_sha256'][p],new_sha256=sha(package_file(p))))
    assert not inventory['other_referencers'],'Unexpected non-map references require separate verification.'
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_modified_asset_files([str(package_file(p)) for p in inventory['referencer_maps']])
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
        include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
    refs={r['old']:sorted(str(p) for p in (registry.get_referencers(unreal.Name(r['old']),options) or [])) for r in inventory['assets']}
    write('PreCleanupReferences.json',refs)
    assert not any(refs.values()),refs
    write('DefaultActorStates.json',default_states)
    write('Moved.json',dict(passed=True,relocations=relocations,maps=map_checks,
                           old_folder_contains_temporary_redirectors=True,cleanup_pending=True))
    unreal.log('OPENING_RELOCATION_MOVE_PASS '+str(dict(assets=len(assets),maps=len(map_checks))))


if __name__=='__main__':
    try:main()
    except Exception:
        write('MoveFailure.json',dict(traceback=traceback.format_exc()))
        raise
