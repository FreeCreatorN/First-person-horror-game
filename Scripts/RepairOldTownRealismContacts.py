"""Separate a fixed set of diagnosed faces by 0.6 mm in render space."""
import json,sys,shutil,traceback
from pathlib import Path
from copy import deepcopy
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha
import OldTownRealismMaterials as pbr
import AuditOldTownHotelV4 as architecture
import AuditOldTownHotelDetails as detail
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'AdditionalSurfaceRepairs.json').exists(),'Do not apply an additive repair twice.'
    build=read(WORK/'BuildReport.json');change=read(WORK/'RealismApply.json')
    expected=read(WORK/'ExpectedSnapshot.json');plan=read(WORK/'ArchitecturePlan.json')
    before_sha=sha(MAP);assert before_sha==build['map_sha256']==change['map_sha256']
    diagnosed=read(WORK/'BeforePrecisionEvidence/ExposedGroups.json')
    external=[r for r in diagnosed if not r['intra_component']]
    assert len(external)==51 and not any(r['buried'] for r in external)
    deltas={f'OTS_HotelV4_Vestibule_Front_{i:02d}::StaticMeshComponent0':d for i,d in enumerate(([0,.06,0],[0,-.06,0],[0,0,-.06]))}
    heads={c for r in external for c in r['components'] if '_Bed' in c and 'Head::' in c}
    assert len(heads)==48 and all(r['normal']==[-1.,0.,0.] for r in external if any(c in heads for c in r['components']))
    deltas.update({c:[.06,0,0] for c in heads});assert len(deltas)==51
    world=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET);assert world
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by={a.get_actor_label():a for a in actors};before={n:actor_state(a) for n,a in by.items()}
    assert before==expected['actors'] and len(by)==8014
    backup=WORK/'BeforeContacts';backup.mkdir(exist_ok=True)
    shutil.copy2(MAP,backup/MAP.name)
    for name in ('BuildReport.json','RealismApply.json','ExpectedSnapshot.json','ArchitecturePlan.json','InputSnapshot.json','MaterialBuild.json'):
        shutil.copy2(WORK/name,backup/name)
    rows={r['id']:r for r in change['components']};offsets={r['id']:r for r in build['surface_repair']['material_overrides']}
    pbr.initialize();repairs=[]
    for ident,delta in sorted(deltas.items()):
        row=rows[ident];old=list(row['expected_offset_cm']);new=[round(v+d,6) for v,d in zip(old,delta)]
        comps={c.get_name():c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent)}
        comp=comps[row['component']]
        assert [comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())]==row['after_materials']
        prior=list(row['after_materials'])
        for slot,role in enumerate(row['role']):comp.set_material(slot,pbr.get(role,row['projection'],new))
        comp.set_editor_property('evaluate_world_position_offset',True)
        comp.set_editor_property('world_position_offset_disable_distance',0)
        mats=[comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())]
        row.update(expected_offset_cm=new,after_materials=mats)
        state=expected['actors'][row['actor']]
        next(c for c in state['components'] if c['name']==row['component'])['materials']=mats
        spec=dict(id=ident,actor=row['actor'],component=row['component'],source_offset_cm=old,delta_cm=delta,expected_offset_cm=new,before_materials=prior,after_materials=mats,
                  reason='Diagnosed exposed coplanar contact',appearance_only=True)
        repairs.append(spec)
        offsets[ident]=dict(id=ident,offset_cm=new,materials=[dict(slot=i,original=m,asset=mats[i]) for i,m in enumerate(prior)])
    after={n:actor_state(a) for n,a in by.items()};assert after==expected['actors']
    assert after['BP_OTS_MainHomeInteractive']==before['BP_OTS_MainHomeInteractive']
    hotel=set(plan['expected_actor_states']);plan['expected_actor_states']={n:after[n] for n in hotel}
    for item in plan['placed_boxes']:
        ident=item['actor']+'::StaticMeshComponent0'
        if ident in deltas:item['material_asset']=rows[ident]['after_materials'][0]
    baseline=read(WORK/'PreservationBaseline.json')
    architecture.refresh(actors);architecture.WORK=WORK;detail.WORK=WORK
    ar=architecture.audit(world,plan,baseline,actors);assert ar['passed'],ar['errors'][:10]
    de=detail.detail_audit(world,plan,actors);assert de['passed'],de['errors'][:10]
    assert sha(MAP)==before_sha and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    final_sha=sha(MAP)
    report=dict(schema='OldTownRealismAdditionalSurfaceRepairsV1',passed=True,source_map_sha256=before_sha,map_sha256=final_sha,
                diagnostic_sha256=sha(WORK/'BeforePrecisionEvidence/ExposedGroups.json'),components=repairs,count=51,
                maximum_added_offset_cm=.06,appearance_only=True,actor_poses_and_collision_unchanged=True)
    build.update(map_sha256=final_sha,hotel_v4=plan,hotel_architecture=plan)
    build['surface_repair']['material_overrides']=list(offsets.values())
    build['surface_repair']['shifted_components']=len(offsets)
    build['surface_repair']['maximum_world_translation_cm']=max(max(abs(v) for v in r['offset_cm']) for r in offsets.values())
    change['map_sha256']=final_sha;build['realism_refinement']=change
    build['additional_surface_repairs']=report
    material=read(WORK/'MaterialBuild.json');mr={r['asset']:r for r in material['assets']};mr.update({r['asset']:r for r in pbr.report()['assets']})
    material['assets']=list(mr.values());material['final_compile_logs'].append(str(WORK/'ContactsRepair.stdout.log'))
    build['new_asset_sha256'].update({str(p):sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
    inp=read(WORK/'InputSnapshot.json');inp['actors']=after
    applied=read(WORK/'Applied.json');applied['map_sha256']=final_sha;applied['additional_surface_repairs']=51
    for name,obj in [('AdditionalSurfaceRepairs.json',report),('BuildReport.json',build),('RealismApply.json',change),
                     ('ArchitecturePlan.json',plan),('ExpectedSnapshot.json',expected),('InputSnapshot.json',inp),
                     ('MaterialBuild.json',material),('Applied.json',applied)]:write(name,obj)
    write('ContactPreSaveArchitectureAudit.json',ar);write('ContactPreSaveDetailAudit.json',de)
    unreal.log('REALISM_CONTACT_REPAIR_PASS '+final_sha)
if __name__=='__main__':
    try:main()
    except Exception:write('ContactRepairFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
