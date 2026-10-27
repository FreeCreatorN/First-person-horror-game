"""Resave only the authorized original map to regenerate stale ActorsMetaData."""
import sys,json,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';C=R/'Content'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def files():return {str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
def main():
    assert not (W/'MetadataRefreshApplied.json').exists()
    commit=read('Committed.json');assert read('FinalAudit.json')['passed'] and read('FinalAudit1.Completion.json')['normal_zero_exit']
    graph=read('FinalReferences.json');assert graph['passed'] and read('FinalReferences1.Completion.json')['normal_zero_exit']
    before=files();assert before==graph['file_sha256'] and before[commit['original_map_file']]==commit['map_sha256']
    backup=R/'Saved/CodexBackups'/('HotelWorldMetadata_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    mapfile=Path(commit['original_map_file']);saved=backup/mapfile.name;shutil.copy2(mapfile,saved);assert native.sha(saved)==commit['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(read('CopiedPackages.json')['original_level'])
    actors=list(ae.get_all_level_actors());assert len(actors)==7986
    counts={}
    for a in actors:counts[a.get_class().get_path_name()]=counts.get(a.get_class().get_path_name(),0)+1
    assert sum(v for k,v in counts.items() if k.startswith('/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door'))==124
    assert le.save_current_level()
    after=files();assert set(before)==set(after) and all(after[p]==h for p,h in before.items() if p!=str(mapfile))
    retained=read('CurrentCleanupGate.json')['retained'];data=mapfile.read_bytes()
    residual=[r['package'] for r in retained if r['package'].encode() in data or r['package'].encode('utf-16-le') in data]
    assert not residual,residual
    native.write(W/'MetadataRefreshApplied.json',dict(passed=True,original_map_file=str(mapfile),map_sha256=native.sha(mapfile),
        previous_map_sha256=commit['map_sha256'],source_map_sha256=commit['source_map_sha256'],backup=str(saved),backup_sha256=native.sha(saved),
        all_other_content_config_unchanged=True,no_actor_edit_called=True,no_asset_save_called=True,old_door_path_literals_removed=10,
        reason='UWorld.GetExtendedAssetRegistryTagsForSave regenerates plural ActorsMetaData; AssetHeaderPatcher handles singular ActorMetaData only.',
        engine_sources={p:native.sha(Path(p)) for p in ['D:/UE_5.7/Engine/Source/Runtime/Engine/Private/World.cpp','D:/UE_5.7/Engine/Source/Developer/AssetTools/Private/AssetHeaderPatcher.cpp']}))
    unreal.log('HOTEL_WORLD_ACTORS_METADATA_REFRESH_PASS')
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'MetadataRefreshFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
