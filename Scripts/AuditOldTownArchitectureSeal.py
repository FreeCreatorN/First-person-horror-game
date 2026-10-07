"""Independent real-mesh and physics checks for the architectural refinement."""
from collections import defaultdict
import itertools
import hashlib
import json
from pathlib import Path
import sys
import unreal

def audit_architecture(world,actors,build,plan):
    from ConvertOldTownBuildings import plan_buildings
    from AuditOldTownRevision import _mesh_box
    from ValidateEnterableStreet import capsule_blocking_components
    report={'passed':False,'checks':[],'errors':[]}
    def check(name,passed,**details):
        report['checks'].append({'name':name,'passed':bool(passed),**details})
        if not passed:
            report['errors'].append(name)
    def near(a,b):
        return max(abs(a[i]-b[i]) for i in range(3)) < .02
    def intersects(a,b):
        return all(min(a[1][i],b[1][i])-max(a[0][i],b[0][i]) > .02 for i in range(3))
    by=defaultdict(list)
    meshes={}
    for actor in actors:
        name=actor.get_actor_label()
        by[name].append(actor)
        cs=[c for c in actor.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]
        if len(cs)==1:
            meshes[name]=(cs[0],_mesh_box(cs[0]))
    structure=build['buildings']
    spec=build['architecture_seal']
    component_revision=bool(build.get('opening_components'))
    if component_revision:
        from AuditOldTownOpeningComponents import FORBIDDEN_WINDOW_ASSETS
        legacy=[]
        for actor in actors:
            for component in actor.get_components_by_class(unreal.StaticMeshComponent):
                asset=component.static_mesh
                if asset and asset.get_path_name().split('.',1)[0] in FORBIDDEN_WINDOW_ASSETS:
                    legacy.append(actor.get_actor_label()+':'+component.get_name())
        check('old_barred_window_modules_removed',not legacy,barred_components=legacy)
    else:
        window_mesh_actors=[name for name,(c,data) in meshes.items()
                            if '/Windows/' in data['asset'] or 'Window_' in c.static_mesh.get_name()]
        check('old_window_modules_replaced',set(window_mesh_actors)=={w['actor'] for w in spec['windows']},
              actual_window_mesh_count=len(window_mesh_actors))
    geometry=plan_buildings([],plan)
    rows={r['actor']:r for r in structure['structural_boxes']}
    for name,row in rows.items():
        item=meshes.get(name)
        bounds=item[1]['bounds_cm'] if item else None
        check('structural_bounds:'+name,len(by[name])==1 and bounds is not None
              and near(bounds[0],row['min']) and near(bounds[1],row['max']),actual_cm=bounds)
    for b in geometry:
        panels=[p for p in structure['stair_side_panels'] if p['building']==b.label]
        if b.count==1:
            check('single_storey_no_stair_panels:'+b.label,len(panels)==0)
            continue
        check('four_full_height_rectangles:'+b.label,len(panels)==4)
        local={p['coverage']['side']:p for p in panels}
        for p in panels:
            name=p['actor']
            item=meshes.get(name)
            if item is None:
                check('stair_mesh:'+name,False)
                continue
            c,data=item
            box=data['bounds_cm']
            r=data['world_rotation_degrees']
            green=any('OldGreenMetal' in (m or '') for m in data['materials'])
            check('stair_full_regular_box:'+name,green and abs(box[0][2]-b.ground)<.02
                  and abs(box[1][2]-(b.high[2]-20.))<.02
                  and all(abs(v)<.001 for v in r)
                  and 'StairSidePanel' in data['asset'],bounds_cm=box)
        center=local.get('center_gap')
        check('entire_center_gap_closed:'+b.label,center is not None
              and abs(center['local_min'][0]-(b.core_u-10.))<.02
              and abs(center['local_max'][0]-(b.core_u+10.))<.02
              and abs(center['local_max'][1]-(b.core_v+b.run))<.02)
        rear=local.get('rear')
        side=local.get('wall')
        check('side_and_back_join_building:'+b.label,rear is not None and side is not None
              and abs(rear['local_max'][1]-(b.depth-20.))<.02
              and (abs(side['local_min'][0]-(-b.width*.5+20.))<.02 if b.core_u<0.
                   else abs(side['local_max'][0]-(b.width*.5-20.))<.02))
        overlaps=[]
        for a,c in itertools.combinations(panels,2):
            if intersects([a['world_min'],a['world_max']],[c['world_min'],c['world_max']]):
                overlaps.append([a['actor'],c['actor']])
        check('stair_panels_no_overlap:'+b.label,not overlaps,overlaps=overlaps)
    walls=[r for r in rows.values() if r['role']=='WallPanel']
    for w in spec['windows']:
        name=w['actor']
        item=meshes.get(name)
        if component_revision:
            fixtures=[r for r in build['opening_components']['windows'] if r['window_id']==w['name']]
            check('base_window_fixture_matches_wall_opening:'+name,len(by[name])==1
                  and len(fixtures)==1 and fixtures[0]['actor']==name and fixtures[0]['building']==w['building'])
        else:
            check('window_frame_attached:'+name,item is not None and len(by[name])==1
                  and near(item[1]['component_location_cm'],w['location_cm'])
                  and near(item[1]['world_scale'],w['scale']),location_cm=w['location_cm'])
        intrusions=[r['actor'] for r in walls if r['building']==w['building']
                    and intersects([r['min'],r['max']],[w['world_min'],w['world_max']])]
        check('real_wall_window_opening:'+name,not intrusions,wall_intrusions=intrusions)
        if not component_revision:
            glass=meshes.get(w['glass_actor'])
            blocked=False
            if glass:
                c=glass[0]
                blocked=c.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION and (
                    c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)==unreal.CollisionResponseType.ECR_BLOCK)
                box=glass[1]['bounds_cm']
                point=[(box[0][i]+box[1][i])*.5 for i in range(3)]
                foot=point[:2]+[point[2]-92.]
                hits=capsule_blocking_components(world,foot)
                blocked=blocked and c in hits
            check('closed_window_real_collision:'+name,blocked)
        check('four_full_depth_reveals:'+name,len(w['reveal_actors'])==4
              and all(r in meshes for r in w['reveal_actors']))
    if component_revision:
        check('base_windows_in_all_planned_buildings',{w['building'] for w in spec['windows']}=={b.label for b in geometry})
    else:
        check('windows_in_all_29_buildings',len({w['building'] for w in spec['windows']})==29)
    if component_revision:
        expected_labels={b.label for b in geometry}
        check('one_component_door_per_building_entry',len(spec['doors'])==len(expected_labels)
              and {d['building'] for d in spec['doors']}==expected_labels)
    else:
        check('one_physical_leaf_per_entry',len(spec['doors'])==29
              and len({d['building'] for d in spec['doors']})==29
              and sum(r['role']=='DoorLeaf' for r in rows.values())==29)
    for d in spec['doors']:
        item=meshes.get(d['actor'])
        if component_revision:
            entries=[r for r in build['opening_components']['doors']
                     if r.get('kind')=='building_entry' and r['building']==d['building']]
            check('door_component_fixture_and_route:'+d['building'],len(entries)==1 and len(by[d['actor']])==1
                  and entries[0]['actor']==d['actor'] and d['route_center_clearance_cm']>=39.)
        else:
            check('door_leaf_and_frame:'+d['building'],item is not None
                  and len(d['frame_actors'])==3 and all(n in meshes for n in d['frame_actors'])
                  and d['route_center_clearance_cm']>=39.)
    check('sealed_floor_and_roof_joints_exist',bool(spec['seam_joint_boxes']) and spec['joint_lap_cm']==.5)
    for row in spec['seam_joint_boxes']:
        item=meshes.get(row['actor'])
        check('sealed_joint_actual_bounds:'+row['actor'],item is not None
              and near(item[1]['bounds_cm'][0],row['min']) and near(item[1]['bounds_cm'][1],row['max']))
    if component_revision:
        from AuditOldTownOpeningComponents import run
        opening_audit=run(world,actors,geometry,build)
        report['opening_components_audit']=opening_audit
        check('independent_opening_component_and_physics_audit',opening_audit['passed'],
              failed_checks=opening_audit['failures'],statistics=opening_audit['statistics'])
    report['statistics']={'checks':len(report['checks']),'failed_checks':len(report['errors']),
        'stair_cores':sum(b.count>1 for b in geometry),'stair_panels':len(structure['stair_side_panels']),
        'window_modules':len(spec['windows']),'physical_door_leaves':len(spec['doors']),
        'sealed_floor_roof_modules':len(spec['seam_joint_boxes'])}
    report['passed']=not report['errors']
    report['limitations']=['Collision sampling is not a real-time player traversal.',
        'New door leaves are fixed open geometry; they have no newly implemented interaction.']
    if component_revision:
        report['statistics']['window_modules']=len(build['opening_components']['windows'])
        report['statistics']['physical_door_leaves']=len(build['opening_components']['doors'])
        report['statistics']['building_entry_doors']=len(spec['doors'])
        report['limitations']=['Collision sampling is not a real-time player traversal.',
            'Opening fixtures have independent movable hinges and collision, but interaction input and animation are not implemented.']
    return report

def main():
    project=Path(unreal.Paths.project_dir()).resolve()
    sys.path.insert(0,str(project/'Scripts'))
    out=project/'Saved/CodexOutputs/EnterableStreet_20261002'
    work=project/'Saved/CodexOutputs/ArchitectureSeal_20261004'
    build=json.loads((out/'BuildReport.json').read_text(encoding='utf-8'))
    plan=json.loads((out/'RevisionPlan.json').read_text(encoding='utf-8'))
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    from ValidateEnterableStreet import refresh_world_collision
    refresh_world_collision(actors)
    report=audit_architecture(world,actors,build,plan)
    report['map_sha256']=hashlib.sha256((project/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap').read_bytes()).hexdigest()
    assert report['map_sha256']==build['map_sha256']==build['architecture_seal']['map_sha256']
    from AuditOldTownLightingCleanup import audit_cleanup
    lighting=audit_cleanup(world,actors,build)
    assert lighting['passed'],lighting['errors']
    for folder in (out,work):
        (folder/'ArchitectureSealAudit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'LightingCleanupAudit.json').write_text(json.dumps(lighting,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report['passed'],report['errors']
    unreal.log('OTS_ARCHITECTURE_AUDIT_SUCCESS '+json.dumps(report['statistics']))

if __name__=='__main__':
    main()
