"""Read the 20 source mesh slots and BodySetup before the next mesh stage."""
import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
W=ROOT/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
S=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    digest=native.sha(MAP);expected=read(S/'AppearanceSnapshot.json')
    assert digest==expected['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(native.TARGET)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    states={a.get_actor_label():stable_actor(a) for a in actors}
    assert states==expected['actors']
    assert light_inventory(actors)==read(S/'LightInput.json')['lights']
    catalog=read(ROOT/'SourceArt/OldTownRealismRefinement_20261013/SoftGoods/ModelDataManifest.json')
    sources=sorted({v['source_asset'] for v in catalog['variants']});assert len(sources)==20
    native.WORK=W/'Before/Native';native.MESH_CACHE.clear();native.MATERIAL_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    rows={p:native.mesh_record(unreal.load_asset(p)) for p in sources}
    assert not native.LIMITATIONS,native.LIMITATIONS
    assert native.sha(MAP)==digest
    native.write(W/'Before/SourceMeshRecords.json',dict(passed=True,map_sha256=digest,mesh_records=rows,
        native_source_file_sha256=native.SOURCE_FILES,source='fresh_persisted_native_read_only',
        exact_scene_input_matches=True,all_light_properties_preserved=True,persisted_map_unchanged=True))
    unreal.log('SOFT_GOODS_INPUT_EXPORT_PASS '+str(len(rows)))
if __name__=='__main__':main()
