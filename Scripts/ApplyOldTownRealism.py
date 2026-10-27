"""Apply approved detailed meshes/PBR through instance appearance overrides only."""
import json,sys,shutil,traceback
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from PolishOldTownDetails import actor_bounds
import OldTownRealismMaterials as pbr
import OldTownRealismImport as imp
from OldTownRealismRoles import role as street_role
from AuditOldTownHotelV4 import audit,refresh
import AuditOldTownHotelV4 as architecture
import AuditOldTownHotelDetails as detail
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
SOURCE=ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def old_role(path,label,component,box):
    name=path.rsplit('/',1)[-1].lower()
    if box and box.get('role')=='floor':return 'Stone'
    if box and box.get('detail_kind') in ('grounded_flight_post','platform_post','flight_baseplate','platform_baseplate'):return 'PaintedMetal'
    if 'schoolwall' in name:return 'Plaster'
    if 'concrete' in name:return 'Concrete'
    if 'glass' in name:return 'Glass'
    if 'linen' in name or 'cloth' in name:return 'Linen'
    if 'ceramic' in name:return 'Ceramic'
    if 'greenmetal' in name:return 'PaintedWood' if 'Door' in label and 'Frame' in component else 'PaintedMetal'
    if 'wood' in name:return 'Wood'
    if 'letters' in name:return 'Letters'
    if 'paper' in name:return 'Paper'
    if 'dark' in name or 'metal' in name:
        return 'Chrome' if any(s in label for s in ('Basin','Toilet','Shower')) or 'Handle' in component else 'DarkMetal'
    return None

def build_other_models(category,axes):
    base=ROOT/('SourceArt/OldTownRealism_20261012/'+category)
    manifest=read(base/'ModelDataManifest.json');rows=[];meshes={}
    assert manifest.get('status') in ('COMPLETE','PASS'),(category,manifest.get('status'))
    for entry in manifest['variants']:
        m,row=imp.build_variant(entry,base,axes,category);rows.append(row);meshes[entry['key']]=m
    write(category+'AssetBuild.json',dict(passed=True,assets=rows,manifest_sha256=sha(base/'ModelDataManifest.json')))
    return manifest,meshes,rows

def main():
    assert not (WORK/'Applied.json').exists(),'Use saved audits, not a second application.'
    inventory=read(WORK/'RealismInput.json');before=read(SOURCE/'AfterSnapshot.json');build=read(SOURCE/'BuildReport.json')
    street_input=read(WORK/'RealismStreetInput.json')
    assert street_input['passed'] and street_input['input_inventory_sha256']==sha(WORK/'RealismInput.json')
    inventory=deepcopy(inventory)
    inventory['component_records'].update(street_input['component_records'])
    inventory['source_asset_file_sha256'].update(street_input['source_asset_file_sha256'])
    inventory['protected_map_sha256']=street_input['protected_map_sha256']
    digest=sha(MAP);assert inventory['passed'] and digest==inventory['source_map_sha256']==build['map_sha256']==before['source_map_sha256']
    for path,h in inventory['source_asset_file_sha256'].items():assert sha(Path(path))==h,path
    for path,h in inventory['original_400_shared_asset_sha256'].items():assert sha(Path(path))==h,path
    for path,h in inventory['protected_map_sha256'].items():assert sha(Path(path))==h,path
    backup=WORK/'Before';backup.mkdir(parents=True,exist_ok=True)
    shutil.copy2(MAP,backup/MAP.name)
    for path in inventory['protected_map_sha256']:
        f=Path(path);shutil.copy2(f,backup/('Protected_'+f.name))
    for name in ('BuildReport.json','AfterSnapshot.json','PreservationBaseline.json'):shutil.copy2(SOURCE/name,backup/name)
    write('InputSnapshot.json',dict(before,protected_map_sha256=inventory['protected_map_sha256']))
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert {n:actor_state(a) for n,a in by.items()}==before['actors']
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    pbr.initialize();axes=read(WORK/'AxisVerification.json')
    furniture=read(WORK/'FurnitureAssetBuild.json');assert furniture['passed'] and len(furniture['assets'])==33
    f_manifest=read(ROOT/'SourceArt/OldTownRealism_20261012/Furniture/ModelDataManifest.json')
    f_assets={r['key']:assets.load_asset(r['asset']) for r in furniture['assets']}
    model_assignments={n:(f_assets[v['key']],v,'Furniture') for v in f_manifest['variants'] for n in v['source_actor_labels']}
    assert len(model_assignments)==680
    arch_manifest,arch_meshes,arch_rows=build_other_models('Architecture',axes)
    sanitary_manifest,sanitary_meshes,sanitary_rows=build_other_models('Sanitary',axes)
    street_manifest,street_meshes,street_rows=build_other_models('Street',axes)
    native_assignments={}
    for cat,manifest,meshes in [('Architecture',arch_manifest,arch_meshes),('Sanitary',sanitary_manifest,sanitary_meshes),('Street',street_manifest,street_meshes)]:
        for v in manifest['variants']:
            for n in ([] if v.get('components') else v.get('source_actor_labels',[])):
                component=v.get('component_name','StaticMeshComponent0')
                native_assignments[n+'::'+component]=(meshes[v['key']],v,cat)
            for row in v.get('components',v.get('component_assignments',[])):
                native_assignments[row['actor']+'::'+row['component']]=(meshes[v['key']],v,cat)
    plan=deepcopy(build['hotel_v4']);box_rows={r['actor']:r for r in plan['placed_boxes']}
    for key,mesh in sanitary_meshes.items():
        if key in plan['asset_catalog']:plan['asset_catalog'][key]=mesh.get_path_name().split('.')[0]
    hotel=set(inventory['hotel_actor_labels']);changes=[];unresolved=[];changed_actors=set()
    mainhome=before['main_home']['actor']
    for n in sorted(by):
        if n==mainhome:continue
        native={r['name']:r for r in inventory['component_records'][n]}
        for c in by[n].get_components_by_class(unreal.StaticMeshComponent):
            if not c.static_mesh or not c.get_editor_property('visible') or c.get_editor_property('hidden_in_game'):continue
            source_mesh=c.static_mesh.get_path_name();id=n+'::'+c.get_name();rec=native[c.get_name()]
            old_mats=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]
            uniform=rec['expected_surface_translation_cm_to_preserve'];assert uniform is not None,('Mixed WPO component needs explicit section mapping',id)
            assignment=model_assignments.get(n) or native_assignments.get(id)
            if assignment:
                mesh,v,cat=assignment;c.set_static_mesh(mesh)
                roles=[str(s.material_slot_name) for s in mesh.static_materials]
                # GeometryScript uses generated slot names; import report has the actual role order.
                reports=furniture['assets'] if cat=='Furniture' else arch_rows if cat=='Architecture' else sanitary_rows if cat=='Sanitary' else street_rows
                assetrow=next(r for r in reports if r['key']==v['key']);roles=assetrow['material_roles']
                if v.get('kind','').startswith('Seat') or 'Chair' in v.get('kind',''):roles=['Upholstery' if r=='Linen' else r for r in roles]
                for slot,role in enumerate(roles):c.set_material(slot,pbr.get(role,'UV',uniform))
                mode='UV'
            else:
                cat='Material';roles=[];mode='World'
                for slot,mat in enumerate(old_mats):
                    if not mat:unresolved.append(dict(id=id,slot=slot,material=mat));roles.append(None);continue
                    original_base=rec['materials'][slot]['base_material']
                    role=old_role(original_base,n,c.get_name(),box_rows.get(n)) if n in hotel else street_role(original_base,n,c.get_name())
                    if role:
                        c.set_material(slot,pbr.get(role,mode,rec['materials'][slot]['effective_surface_translation_cm']));roles.append(role)
                    else:roles.append(None);unresolved.append(dict(id=id,slot=slot,material=mat,base=original_base))
            after_mats=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]
            if after_mats!=old_mats or c.static_mesh.get_path_name()!=source_mesh:
                changed_actors.add(n);changes.append(dict(id=id,actor=n,component=c.get_name(),source_mesh=source_mesh,target_mesh=c.static_mesh.get_path_name(),before_materials=old_mats,after_materials=after_mats,expected_offset_cm=uniform,category=cat,role=roles,projection=mode))
    # Existing logo/number assets may deliberately retain their legible unlit letters.
    write('UnresolvedMaterials.json',dict(components=unresolved))
    current={n:actor_state(a) for n,a in by.items()}
    allowed={r['id']:r for r in changes}
    expected=deepcopy(before['actors'])
    for n,state in expected.items():
        for c in state['components']:
            row=allowed.get(n+'::'+c['name'])
            if row:c.update(mesh=row['target_mesh'],materials=row['after_materials'])
    assert current==expected,'Changes outside the declared appearance fields.'
    assert len(current)==8014 and current[mainhome]==before['actors'][mainhome]
    for path,h in inventory['source_asset_file_sha256'].items():assert sha(Path(path))==h,path
    for path,h in inventory['protected_map_sha256'].items():assert sha(Path(path))==h,path
    plan['expected_actor_states']={n:current[n] for n in hotel};plan['source_map_sha256']=digest
    for r in plan['placed_boxes']+plan['placed_props']:
        a=by[r['actor']];c=a.get_component_by_class(unreal.StaticMeshComponent)
        if c:
            r['asset']=c.static_mesh.get_path_name();lo,hi=actor_bounds(a)
            for k,v in dict(world_min=lo,world_max=hi,bounds=[lo,hi],world_bounds_cm=[lo,hi]).items():r[k]=v
            if r in plan['placed_boxes']:r['material_asset']=c.get_material(0).get_path_name()
    props_by={r['id']:r for r in plan['placed_props']}
    for r in plan.get('props',[]):
        if r['id'] in props_by:
            q=props_by[r['id']]
            for k in ('asset','world_min','world_max','bounds','world_bounds_cm'):
                if k in q:r[k]=deepcopy(q[k])
    for row in plan['placed_doors']+plan['placed_windows']:
        actual={c.get_name():c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent)}
        for spec in row['components']:
            c=actual.get(spec['name'])
            if c:spec['asset']=c.static_mesh.get_path_name()
    baseline=read(SOURCE/'PreservationBaseline.json');baseline['protected_map_sha256']=inventory['protected_map_sha256'];baseline['source_map_sha256']=digest
    baseline['allowed_surface_overrides']={n:current[n] for n in set(by)-hotel if current[n]!=before['actors'][n]}
    write('PreservationBaseline.json',baseline)
    write('ExpectedSnapshot.json',dict(actors=expected,source_map_sha256=digest))
    # Detail audit keeps exact collision/door states, with only approved appearance overrides.
    write('InputSnapshot.json',dict(before,actors=expected,protected_map_sha256=inventory['protected_map_sha256']))
    refresh(actors);architecture.WORK=WORK;detail.WORK=WORK
    ar=audit(world,plan,baseline,actors);write('PreSaveArchitectureAudit.json',ar);assert ar['passed'],ar['errors'][:20]
    de=detail.detail_audit(world,plan,actors);write('PreSaveDetailAudit.json',de);assert de['passed'],de['errors'][:20]
    changes_report=dict(passed=True,source_map_sha256=digest,components=changes,changed_actor_count=len(changed_actors),changed_component_count=len(changes),appearance_only=True,scope='whole_map',changed_street_actor_count=len(changed_actors-hotel),original_actor_count=8014,source_asset_sha256=inventory['source_asset_file_sha256'],protected_map_sha256=inventory['protected_map_sha256'])
    write('PendingRealismApply.json',changes_report)
    build.update(status='PENDING',source_map_sha256=digest,hotel_v4=plan,hotel_architecture=plan,protected_map_sha256=inventory['protected_map_sha256'],realism_refinement=changes_report,previous_evidence=str(SOURCE/'FinalReview.json'))
    build['new_asset_sha256'].update({str(p):sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
    build['hotel_openings_review_cameras']=['CAM_V4_Reception','CAM_V4_LobbyWide','CAM_V4_GuestTwin','CAM_Detail_StairRail','CAM_Surface_WindowInside','CAM_Basin_Guest201','CAM_Shape_ToiletFullPublic','CAM_V4_Exterior']
    write('PendingBuildReport.json',build)
    assert sha(MAP)==digest and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    newsha=sha(MAP);build.update(status='PASS',map_sha256=newsha);changes_report['map_sha256']=newsha
    write('BuildReport.json',build);write('RealismApply.json',changes_report);write('ArchitecturePlan.json',plan)
    write('MaterialBuild.json',dict(pbr.report(),final_compile_logs=[str(WORK/'PrepareAssets4.stdout.log'),str(WORK/'Apply.stdout.log')]))
    write('Applied.json',dict(passed=True,source_map_sha256=digest,map_sha256=newsha,changed_components=len(changes),changed_actors=len(changed_actors),actor_count=len(actors)))
    unreal.log('OLD_TOWN_REALISM_APPLY_PASS '+newsha)

assets=unreal.EditorAssetLibrary
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
