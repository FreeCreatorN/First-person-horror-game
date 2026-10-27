"""Separate one diagnosed vestibule header by 0.6 mm in render space."""
import json, sys, shutil, traceback
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, sha
import OldTownRealismMaterials as pbr
import AuditOldTownHotelV4 as architecture
import AuditOldTownHotelDetails as detail
WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
MAP = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
SOURCE_SHA = '6025a94eb391fb43d09cc4972ce3d7c8192b7e712578155d517a00b035caeb43'
IDENT = 'OTS_HotelV4_Vestibule_Front_02::StaticMeshComponent0'

def read(n):
    return json.loads((WORK / n).read_text(encoding='utf-8-sig'))

def write(n, data):
    (WORK / n).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    assert not (WORK / 'FollowupSurfaceRepairs.json').exists(), 'Do not apply a saved follow-up twice.'
    build, change = read('BuildReport.json'), read('RealismApply.json')
    expected, plan = read('ExpectedSnapshot.json'), read('ArchitecturePlan.json')
    digest = sha(MAP)
    assert digest == SOURCE_SHA == build['map_sha256'] == change['map_sha256']
    diagnosis = read('SavedScanSummary.json')
    exposed = diagnosis['exposed_candidates']
    assert diagnosis['provenance']['source_map_sha256'] == digest
    assert diagnosis['counts']['exposed_groups'] == len(exposed) == 4
    assert diagnosis['counts']['intra_exposed'] == diagnosis['counts']['exact_duplicate_box_groups'] == 0
    pairs = {frozenset(r['components']) for r in exposed}
    assert pairs == {frozenset((IDENT, f'OTS_HotelV4_Vestibule_Front_{i:02d}::StaticMeshComponent0')) for i in (0, 1)}
    assert all(r['normal'] in ([1., 0., 0.], [-1., 0., 0.]) and not r['intra_component'] for r in exposed)
    world = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    assert world
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by = {a.get_actor_label(): a for a in actors}
    before = {name: actor_state(a) for name, a in by.items()}
    assert len(by) == 8014 and before == expected['actors']
    backup = WORK / 'BeforeFollowupSurfaceRepairs'
    backup.mkdir(exist_ok=False)
    shutil.copy2(MAP, backup / MAP.name)
    for name in ('BuildReport.json', 'RealismApply.json', 'ExpectedSnapshot.json', 'ArchitecturePlan.json',
                 'MaterialBuild.json', 'Applied.json', 'AdditionalSurfaceRepairs.json', 'MaterialRoleRepairs.json',
                 'InputSnapshot.json', 'AfterSnapshot.json', 'GeometryAfter.json', 'AfterSummary.json',
                 'AppearanceAudit.json', 'ArchitectureAudit.json', 'DetailAudit.json', 'PreservationBaseline.json',
                 'SavedScan.json', 'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json', 'VisualReviewTeam.json'):
        shutil.copy2(WORK / name, backup / name)
    (backup / 'ExposedGroups.json').write_text(json.dumps(exposed, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = {r['id']: r for r in change['components']}
    row = rows[IDENT]
    assert row['projection'] == 'World' and row['role'] == ['Plaster']
    old = list(row['expected_offset_cm'])
    delta = [.06, 0., 0.]
    new = [round(v + d, 6) for v, d in zip(old, delta)]
    assert max(abs(v - t) for v, t in zip(old, [.09, 0., -.06])) < .000002
    comp = next(c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent) if c.get_name() == row['component'])
    prior = [comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())]
    assert prior == row['after_materials']
    material = read('MaterialBuild.json')
    parent_row = next(r for r in material['assets'] if r.get('kind') == 'master' and r.get('role') == 'Plaster' and r.get('projection') == 'World')
    parent = unreal.EditorAssetLibrary.load_asset(parent_row['asset'])
    assert parent and sha(Path(parent_row['file'])) == parent_row['sha256']
    # Reuse the already verified graph; create only the new offset instance.
    pbr._cache[('Plaster', 'World')] = parent
    comp.set_material(0, pbr.get('Plaster', 'World', new))
    comp.set_editor_property('evaluate_world_position_offset', True)
    comp.set_editor_property('world_position_offset_disable_distance', 0)
    mats = [comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())]
    row.update(expected_offset_cm=new, after_materials=mats)
    next(c for c in expected['actors'][row['actor']]['components'] if c['name'] == row['component'])['materials'] = mats
    after = {name: actor_state(a) for name, a in by.items()}
    assert after == expected['actors'] and after['BP_OTS_MainHomeInteractive'] == before['BP_OTS_MainHomeInteractive']
    hotel = set(plan['expected_actor_states'])
    plan['expected_actor_states'] = {name: after[name] for name in hotel}
    for box in plan['placed_boxes']:
        if box['actor'] + '::StaticMeshComponent0' == IDENT:
            box['material_asset'] = mats[0]
    baseline = read('PreservationBaseline.json')
    architecture.refresh(actors)
    architecture.WORK = detail.WORK = WORK
    ar = architecture.audit(world, plan, baseline, actors)
    de = detail.detail_audit(world, plan, actors)
    assert ar['passed'], ar['errors'][:10]
    assert de['passed'], de['errors'][:10]
    assert sha(MAP) == digest and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    final_sha = sha(MAP)
    spec = dict(id=IDENT, actor=row['actor'], component=row['component'], source_offset_cm=old, delta_cm=delta,
                expected_offset_cm=new, before_materials=prior, after_materials=mats, role=list(row['role']),
                projection=row['projection'], appearance_only=True,
                reason='Four diagnosed exposed vestibule header corner contacts in the complete saved scan')
    report = dict(schema='OldTownRealismFollowupSurfaceRepairsV1', passed=True, source_map_sha256=digest,
                  map_sha256=final_sha, components=[spec], count=1, maximum_added_offset_cm=.06,
                  appearance_only=True, actor_poses_and_collision_unchanged=True,
                  diagnostic_file=str(backup / 'ExposedGroups.json'), diagnostic_sha256=sha(backup / 'ExposedGroups.json'),
                  prior_saved_scan_summary_file=str(backup / 'SavedScanSummary.json'),
                  prior_saved_scan_summary_sha256=sha(backup / 'SavedScanSummary.json'))
    contact, roles = read('AdditionalSurfaceRepairs.json'), read('MaterialRoleRepairs.json')
    assert contact['map_sha256'] == roles['map_sha256'] == digest
    roles['applied_map_sha256'] = digest
    contact['map_sha256'] = roles['map_sha256'] = final_sha
    build.update(map_sha256=final_sha, hotel_v4=plan, hotel_architecture=plan, followup_surface_repairs=report,
                 additional_surface_repairs=contact, material_role_repairs=roles)
    offsets = {r['id']: r for r in build['surface_repair']['material_overrides']}
    offsets[IDENT] = dict(id=IDENT, offset_cm=new, materials=[dict(slot=i, original=m, asset=mats[i]) for i, m in enumerate(prior)])
    build['surface_repair']['material_overrides'] = list(offsets.values())
    build['surface_repair']['shifted_components'] = len(offsets)
    build['surface_repair']['maximum_world_translation_cm'] = max(max(abs(v) for v in r['offset_cm']) for r in offsets.values())
    change['map_sha256'] = final_sha
    build['realism_refinement'] = change
    mr = {r['asset']: r for r in material['assets']}
    mr.update({r['asset']: r for r in pbr.report()['assets']})
    material['assets'] = list(mr.values())
    material['final_compile_logs'].append(str(WORK / 'VestibuleFollowupRepair2.stdout.log'))
    for path, original_sha in build['new_asset_sha256'].items():
        assert sha(Path(path)) == original_sha, 'Existing generated asset changed: ' + path
    build['new_asset_sha256'].update({str(p): sha(p) for p in (ROOT / 'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
    inp = read('InputSnapshot.json')
    inp['actors'] = after
    applied = read('Applied.json')
    applied.update(map_sha256=final_sha, followup_surface_repairs=1)
    for name, data in (('FollowupSurfaceRepairs.json', report), ('AdditionalSurfaceRepairs.json', contact),
                       ('MaterialRoleRepairs.json', roles), ('BuildReport.json', build), ('RealismApply.json', change),
                       ('ArchitecturePlan.json', plan), ('ExpectedSnapshot.json', expected), ('InputSnapshot.json', inp),
                       ('MaterialBuild.json', material), ('Applied.json', applied)):
        write(name, data)
    write('FollowupPreSaveArchitectureAudit.json', ar)
    write('FollowupPreSaveDetailAudit.json', de)
    unreal.log('REALISM_VESTIBULE_FOLLOWUP_PASS ' + final_sha)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('VestibuleFollowupFailure.json', dict(passed=False, traceback=traceback.format_exc()))
        raise
