"""Separate newly cut rear-wall horizontal faces without moving collision."""
import sys,json,traceback,shutil
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import sha,actor_state
from OldTownSurfaceMaterials import make_offset_material,asset_hashes,get_report
WORK=ROOT/'Saved/CodexOutputs/HotelDetails_20261009'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,r):(WORK/n).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'SurfaceRefinementNegativeZ.json').exists()
    assert (WORK/'SurfaceRefinement.json').exists()
    shutil.copy2(WORK/'SurfaceRefinement.json',WORK/'SurfaceRefinementPositiveZ.json')
    build=read(WORK/'BuildReport.json');mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';old=build['map_sha256']
    assert sha(mapfile)==old;levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);by={a.get_actor_label():a for a in sub.get_all_level_actors()}
    before={n:actor_state(a) for n,a in by.items()};plan=build['hotel_v4'];offset=[.045,0,-.045]
    original=unreal.load_asset(plan['material_paths']['plaster'])
    material=make_offset_material(original,offset,'/Game/CodexGenerated/OldTown/Materials/HotelDetails_20261009')
    rear={r['actor'] for r in plan['placed_boxes'] if r.get('detail_kind')=='recut_rear_envelope'};assert len(rear)==153
    for name in rear:
        c=by[name].get_component_by_class(unreal.StaticMeshComponent);c.set_material(0,material)
        plan['expected_actor_states'][name]=actor_state(by[name])
    for rows in (plan['placed_boxes'],plan['boxes']):
        for r in rows:
            if r.get('actor') in rear:r['material_asset']=material.get_path_name();r['render_offset_hint_cm']=offset
    for r in build['surface_repair']['material_overrides']:
        if r['id'].split('::')[0] in rear:
            r['offset_cm']=offset
            for mat in r['materials']:mat['asset']=material.get_path_name()
    current={n:actor_state(a) for n,a in by.items()};changed={n for n in before if current[n]!=before[n]};assert changed==rear
    for name in rear:
        a,b=before[name],current[name]
        for oldc,newc in zip(a['components'],b['components']):oldc['materials']=newc['materials']
        assert a==b,'Non-material change: '+name
    report=get_report();assert report['passed'];build['new_asset_sha256'].update(asset_hashes())
    assert sha(mapfile)==old;assert levels.save_current_level();digest=sha(mapfile)
    details=read(WORK/'DetailRepairReport.json');details.update(map_sha256=digest,rear_wall_render_offset_cm=offset)
    build.update(map_sha256=digest,hotel_v4=plan,hotel_architecture=plan,detail_repair=details)
    applied=read(WORK/'Applied.json');applied['map_sha256']=digest
    write('BuildReport.json',build);write('ArchitecturePlan.json',plan);write('Applied.json',applied);write('DetailRepairReport.json',details)
    refinement=dict(passed=True,map_sha256=digest,previous_map_sha256=old,offset_cm=offset,
        changed_actor_labels=sorted(rear),only_render_materials_changed=True,original_assets_preserved=report)
    write('SurfaceRefinement.json',refinement);write('SurfaceRefinementNegativeZ.json',refinement)
    unreal.log('HOTEL_DETAIL_SURFACES_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('SurfaceRefineFailure.json',dict(traceback=traceback.format_exc()));raise
