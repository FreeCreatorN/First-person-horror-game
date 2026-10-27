"""Separate concrete wall finishes from floor aggregate without moving geometry."""
import sys,json,shutil,traceback
from pathlib import Path
from copy import deepcopy
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha
import OldTownRealismMaterials as pbr
from OldTownRealismSurfaceRoles import concrete_role
import AuditOldTownHotelV4 as architecture
import AuditOldTownHotelDetails as detail
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(n):return json.loads((WORK/n).read_text(encoding='utf-8-sig'))
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'MaterialRoleRepairs.json').exists(),'Do not reapply saved material routing.'
    build=read('BuildReport.json');apply=read('RealismApply.json');expected=read('ExpectedSnapshot.json');plan=read('ArchitecturePlan.json')
    digest=sha(MAP);assert digest==build['map_sha256']==apply['map_sha256']
    records=read('RealismInput.json')['component_records'];records.update(read('RealismStreetInput.json')['component_records'])
    native={a+'::'+c['name']:c for a,cs in records.items() for c in cs}
    world=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level']);assert world
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors());by={a.get_actor_label():a for a in actors}
    before={n:actor_state(a) for n,a in by.items()};assert before==expected['actors']
    backup=WORK/'BeforeMaterialRoles';backup.mkdir(exist_ok=True);shutil.copy2(MAP,backup/MAP.name)
    for name in ('BuildReport.json','RealismApply.json','ExpectedSnapshot.json','ArchitecturePlan.json','MaterialBuild.json','AdditionalSurfaceRepairs.json'):
        shutil.copy2(WORK/name,backup/name)
    pbr.initialize();repairs=[];retained=[]
    for row in apply['components']:
        if 'Concrete' not in row['role']:continue
        target=concrete_role(row['actor'],row['component'],native[row['id']])
        if target=='Concrete':retained.append(row['id']);continue
        comp=next(c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==row['component'])
        previous=list(row['after_materials']);old_roles=list(row['role'])
        assert previous==[comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())]
        for i,role in enumerate(row['role']):
            if role=='Concrete':
                row['role'][i]='ConcreteWall';comp.set_material(i,pbr.get('ConcreteWall',row['projection'],row['expected_offset_cm']))
        mats=[comp.get_material(i).get_path_name() for i in range(comp.get_num_materials())];row['after_materials']=mats
        next(c for c in expected['actors'][row['actor']]['components'] if c['name']==row['component'])['materials']=mats
        repairs.append(dict(id=row['id'],actor=row['actor'],component=row['component'],source_roles=old_roles,target_roles=list(row['role']),
                            before_materials=previous,after_materials=mats,offset_cm=row['expected_offset_cm'],appearance_only=True))
    assert repairs and retained
    after={n:actor_state(a) for n,a in by.items()};assert after==expected['actors']
    assert after['BP_OTS_MainHomeInteractive']==before['BP_OTS_MainHomeInteractive']
    hotel=set(plan['expected_actor_states']);plan['expected_actor_states']={n:after[n] for n in hotel}
    changed={r['id']:r for r in repairs}
    for item in plan['placed_boxes']:
        ident=item['actor']+'::StaticMeshComponent0'
        if ident in changed:item['material_asset']=changed[ident]['after_materials'][0]
    baseline=read('PreservationBaseline.json');baseline['allowed_surface_overrides']={n:after[n] for n in set(by)-hotel if n in baseline['allowed_surface_overrides']}
    architecture.refresh(actors);architecture.WORK=WORK;detail.WORK=WORK
    ar=architecture.audit(world,plan,baseline,actors);assert ar['passed'],ar['errors'][:10]
    de=detail.detail_audit(world,plan,actors);assert de['passed'],de['errors'][:10]
    assert sha(MAP)==digest and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    final_sha=sha(MAP);apply['map_sha256']=final_sha
    report=dict(schema='OldTownRealismMaterialRoleRepairsV1',passed=True,source_map_sha256=digest,map_sha256=final_sha,
        components=repairs,changed_component_count=len(repairs),retained_floor_component_ids=retained,
        concrete_component_count=len(repairs)+len(retained),actor_poses_and_collision_unchanged=True,
        source_input_sha256={str(WORK/n):sha(WORK/n) for n in ('RealismInput.json','RealismStreetInput.json')})
    build.update(map_sha256=final_sha,hotel_v4=plan,hotel_architecture=plan,realism_refinement=apply,material_role_repairs=report)
    surface={r['id']:r for r in build['surface_repair']['material_overrides']}
    for ident,r in changed.items():
        if ident in surface:
            surface[ident]['materials']=[dict(slot=i,original=m,asset=r['after_materials'][i]) for i,m in enumerate(r['before_materials'])]
    build['surface_repair']['material_overrides']=list(surface.values())
    material=read('MaterialBuild.json');mr={r['asset']:dict(r,sha256=sha(Path(r['file']))) for r in material['assets']};mr.update({r['asset']:r for r in pbr.report()['assets']})
    material['assets']=list(mr.values());material['final_compile_logs'].append(str(WORK/'MaterialRolesRepair.stdout.log'))
    build['new_asset_sha256'].update({str(p):sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
    inp=read('InputSnapshot.json');inp['actors']=after
    applied=read('Applied.json');applied['map_sha256']=final_sha;applied['material_role_repairs']=len(repairs)
    contact=read('AdditionalSurfaceRepairs.json');contact['applied_map_sha256']=contact['map_sha256'];contact['map_sha256']=final_sha
    for n,d in [('MaterialRoleRepairs.json',report),('BuildReport.json',build),('RealismApply.json',apply),('ExpectedSnapshot.json',expected),
                ('ArchitecturePlan.json',plan),('PreservationBaseline.json',baseline),('InputSnapshot.json',inp),('Applied.json',applied),
                ('AdditionalSurfaceRepairs.json',contact),('MaterialBuild.json',material)]:write(n,d)
    write('MaterialRolesPreSaveArchitectureAudit.json',ar);write('MaterialRolesPreSaveDetailAudit.json',de)
    unreal.log('REALISM_MATERIAL_ROLES_REPAIR_PASS '+final_sha+' '+str(len(repairs)))
if __name__=='__main__':
    try:main()
    except Exception:write('MaterialRolesRepairFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
