"""Finish verification after a successful rename/resave stage; never repeat the move."""
import json
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from InspectOldTownOpeningRelocation import WORK,OLD,NEW,write,template_state,package_file
from PolishOldTownHotel import actor_state,sha
from OldTownAssetRelocation import normalize_paths
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

assert (WORK/'RenameStage.json').exists() and not (WORK/'Moved.json').exists()
inventory=read(WORK/'Inventory.json');snapshots=read(WORK/'ActorSnapshots.json')
relocations=[dict(old=r['old'],new=r['new']) for r in inventory['assets']]
registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True)
options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
 include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
for row in inventory['assets']:
 bp=unreal.load_asset(row['new']);assert isinstance(bp,unreal.Blueprint)
 assert bp.get_path_name().split('.')[0]==row['new']
 assert template_state(bp)==normalize_paths(row['templates'],relocations)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
maps=[]
for p in inventory['referencer_maps']:
 assert level.load_level(p)
 current={a.get_actor_label():actor_state(a) for a in sub.get_all_level_actors()}
 expected=normalize_paths(snapshots[p],relocations)
 changed=[n for n,s in expected.items() if current.get(n)!=s]
 assert not changed and set(current)==set(expected),(p,changed[:5])
 maps.append(dict(level=p,actor_count=len(current),recorded_actor_fields_preserved=True,
 old_sha256=inventory['source_map_sha256'][p],new_sha256=sha(package_file(p))))
refs={r['old']:sorted(str(p) for p in (registry.get_referencers(unreal.Name(r['old']),options) or [])) for r in inventory['assets']}
write('PreCleanupReferences.json',refs);assert not any(refs.values()),refs
old_data=[]
for path in unreal.EditorAssetLibrary.list_assets(OLD,True,False):
 data=unreal.EditorAssetLibrary.find_asset_data(path)
 old_data.append(dict(path=path,asset_class=str(data.asset_class_path),loaded_path=data.get_asset().get_path_name()))
write('OldDirectoryBeforeCleanup.json',old_data)
write('Moved.json',dict(passed=True,relocations=relocations,maps=maps,old_folder_contains_temporary_redirectors=True,
 cleanup_pending=True,resumed_after_registry_empty_referencer_return=True))
unreal.log('OPENING_RELOCATION_RESUME_PASS '+str(dict(assets=len(relocations),maps=len(maps),old_assets=old_data)))
