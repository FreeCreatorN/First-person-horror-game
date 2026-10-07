"""Apply the authorized single-entry, flush-road and adult-scale revision."""
from pathlib import Path
import fnmatch
import hashlib
import json
import math
import sys
import traceback
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / 'Saved/CodexOutputs/EnterableStreet_20261002'
REVISION = PROJECT / 'Saved/CodexOutputs/StreetRevision_20261003'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP_FILE = PROJECT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
MANIFEST = PROJECT / 'SourceArt/OldTownScaleRevision_20261003/ImportManifest.json'
ROAD_TAG = 'OTS_RoadRevision_20261003'
REFERENCE_TAG = 'OTS_HumanReference_20261003'
sys.path.insert(0, str(PROJECT / 'Scripts'))


def write(name, data):
    for folder in (OUTPUT, REVISION):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def apply_source_adjustments(subsystem, plan):
    rows = []
    remove = plan['remove_source_actor_labels']
    relocate = {
        'OTS_P2Prop_CardboardBox_02':[1500.,1660.,11.],
        'OTS_P2Prop_CardboardBox_03':[1600.,1660.,11.],
        'OTS_P2Prop_CardboardBox_04':[1700.,1660.,11.],
        'OTS_P2Prop_CardboardBox_05':[1800.,1660.,11.],
        'OTS_P2Prop_TrashBin_02':[1950.,1660.,11.],
        'OTS_P2Prop_TrashBin_03':[2100.,1660.,11.],
        'OTS_P2Prop_CardboardBox_06':[1500.,-1660.,11.],
        'OTS_P2Prop_TrashBin_04':[1650.,-1660.,11.],
        'OTS_P2Prop_WashBasin_01':[1800.,-1660.,11.],
        'OTS_P2Prop_Bicycle_01':[2260.,1660.,11.],
        'OTS_P2Prop_Bicycle_02':[3115.,-1540.,11.],
        'OTS_P2Prop_Bicycle_03':[5200.,1660.,11.],
        'OTS_P2Prop_StreetLamp_01':[1325.,-700.,11.],
        'OTS_P2Prop_StreetLamp_02':[3515.,-700.,11.],
        'OTS_P2Prop_StreetLamp_03':[4665.,-700.,11.],
        'OTS_P2Prop_StreetLamp_04':[5865.,-700.,11.],
        'OTS_P2Prop_StreetLamp_05':[1200.,700.,11.],
        'OTS_P2Prop_StreetLamp_06':[3765.,700.,11.],
        'OTS_P2Prop_StreetLamp_07':[4915.,700.,11.],
        'OTS_P2Prop_ChestFreezer_01':[5400.,1660.,11.],
        'OTS_P2Prop_PlantPot_02':[3540.,-760.,11.],
        'OTS_P2Prop_PlantPot_03':[4665.,-760.,11.],
        'OTS_P2Prop_OutdoorSink_01':[1500.,1580.,11.],
        'OTS_P2Prop_VendorTable_01':[1050.,-1540.,11.],
        'OTS_P2Prop_Thermos_01':[1028.,-1540.,91.],
        'OTS_P2Prop_ChineseStool_01':[1050.,-1430.,11.],
    }
    source_rows={r['label']:r for r in plan['translated_inventory']['actors']}
    for actor in list(subsystem.get_all_level_actors()):
        label = actor.get_actor_label()
        tags = {str(t) for t in actor.tags}
        if ROAD_TAG in tags or REFERENCE_TAG in tags or any(label == name or label.startswith(name+'_') for name in remove):
            assert subsystem.destroy_actor(actor), label
            rows.append({'actor':label, 'action':'remove_replaced_surface_or_wall'})
            continue
        if 'OTS_Enterable_20261002' in tags or 'OldTownBlenderFurniture_20261002' in tags:
            continue  # Rebuilt once from the translated immutable inventory.
        if label in relocate:
            actor.set_actor_location(unreal.Vector(*relocate[label]),False,False)
            rows.append({'actor':label,'action':'clear_public_corridor','location_cm':relocate[label]})
            if label in ('OTS_P2Prop_VendorTable_01','OTS_P2Prop_ChineseStool_01'):
                dims = [150.,80.,80.] if 'VendorTable' in label else [44.,44.,48.]
                c=actor.get_component_by_class(unreal.StaticMeshComponent)
                e=c.static_mesh.get_bounds().box_extent
                actor.set_actor_scale3d(unreal.Vector(dims[0]/(e.x*2),dims[1]/(e.y*2),dims[2]/(e.z*2)))
        if label.startswith('OTS_UtilityPole_'):
            p=actor.get_actor_location()
            side=1. if label.startswith('OTS_UtilityPole_01') else -1.
            actor.set_actor_location(unreal.Vector(p.x,p.y+side*150.,p.z),False,False)
        if label.startswith('OTS_P1WallPoster_01') or label.startswith('OTS_P1WallPosterTear_01'):
            p=actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(p.x-80.,p.y,p.z),False,False)
        if label.startswith('OTS_P2Prop_WallUtilityCluster_01_'):
            original=source_rows['OTS_P2Prop_WallUtilityCluster_01']['meshes'][0]
            delta=2430.-original['world_origin'][0]-original['world_extent'][0]
            p=actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(p.x+delta,p.y,p.z),False,False)
        if label.startswith('OTS_P2Prop_WallUtilityCluster_05_'):
            original=source_rows['OTS_P2Prop_WallUtilityCluster_05']['meshes'][0]
            delta=7730.-original['world_origin'][0]+original['world_extent'][0]
            p=actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(p.x+delta,p.y+3120.,p.z),False,False)
        if label.startswith('OTS_Light_StreetLamp'):
            index=label.rsplit('StreetLamp',1)[1]
            source_label='OTS_P2Prop_StreetLamp_'+index
            if source_label in relocate:
                old=source_rows[source_label]['location']
                dest=relocate[source_label]
                p=actor.get_actor_location()
                actor.set_actor_location(unreal.Vector(p.x+dest[0]-old[0],p.y+dest[1]-old[1],p.z+11.),False,False)
        if label.startswith('OTS_P2Prop_StormDrain_'):
            c=actor.get_component_by_class(unreal.StaticMeshComponent)
            origin,extent,_=unreal.SystemLibrary.get_component_bounds(c)
            p=actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(p.x,p.y,p.z+1.-origin.z-extent.z),False,False)
        if any(token in label for token in ('WallLampGooseneck','Light_StreetEndNorth','Light_StreetEndSouth','Light_StreetEndFocalShop')):
            if 'OTS_EastFacadeMoved_20261003' not in tags:
                p=actor.get_actor_location()
                actor.set_actor_location(unreal.Vector(p.x+1120.,p.y,p.z),False,False)
                actor.set_editor_property('tags',list(actor.tags)+[unreal.Name('OTS_EastFacadeMoved_20261003')])
        matches = [name for name in plan['actor_translations'] if label == name or label.startswith(name+'_')]
        if matches and 'OTS_LayoutTranslated_20261003' not in tags:
            delta = plan['actor_translations'][max(matches,key=len)]
            p = actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(p.x+delta[0],p.y+delta[1],p.z+delta[2]),False,False)
            actor.set_editor_property('tags',list(actor.tags)+[unreal.Name('OTS_LayoutTranslated_20261003')])
            rows.append({'actor':label,'action':'translate_with_building','delta_cm':delta})
        for action in plan['alley_attachment_actions']:
            patterns = action.get('label_patterns', [action.get('actor_label','')])
            if not any(fnmatch.fnmatchcase(label,p) or fnmatch.fnmatchcase(label.rsplit('_',1)[0],p) for p in patterns):
                continue
            if 'OTS_AlleyAdjusted_20261003' in tags:
                continue
            p = actor.get_actor_location()
            delta = action.get('translation_cm',[0.,0.,0.])
            dest = action.get('target_location_cm',[p.x+delta[0],p.y+delta[1],p.z+delta[2]])
            if 'target_x_cm' in action:
                dest[0] = action['target_x_cm']
            actor.set_actor_location(unreal.Vector(*dest),False,False)
            if 'target_yaw_degrees' in action:
                actor.set_actor_rotation(unreal.Rotator(pitch=0.,yaw=action['target_yaw_degrees'],roll=0.),False)
            if 'target_span_cm' in action:
                c=actor.get_component_by_class(unreal.StaticMeshComponent)
                if c and c.static_mesh:
                    actor.set_actor_rotation(unreal.Rotator(0.,0.,0.),False)
                    extent=c.static_mesh.get_bounds().box_extent
                    scale=actor.get_actor_scale3d()
                    actor.set_actor_scale3d(unreal.Vector(action['target_span_cm']/(2.*extent.x),scale.y,scale.z))
                    actor.set_actor_location(unreal.Vector(action['preserve_center_x_cm'],dest[1],dest[2]+25.),False,False)
            if 'target_seat_footprint_cm' in action:
                c=actor.get_component_by_class(unreal.StaticMeshComponent)
                if c and c.static_mesh:
                    extent=c.static_mesh.get_bounds().box_extent
                    scale=actor.get_actor_scale3d()
                    dims=action['target_seat_footprint_cm']
                    actor.set_actor_scale3d(unreal.Vector(dims[0]/(2.*extent.x),dims[1]/(2.*extent.y),scale.z))
            actor.set_editor_property('tags',list(actor.tags)+[unreal.Name('OTS_AlleyAdjusted_20261003')])
            rows.append({'actor':label,'action':'move_alley_attachment','location_cm':dest})
            break
    return rows


def emit_roads(subsystem, plan):
    mesh = unreal.load_asset('/Game/Yastar/Meshes/hOUSE/SM_OTS_Enterable_FloorSlab')
    concrete = unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete')
    asphalt = unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_WetAsphalt')
    wall = unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldPlaster') or concrete
    assert mesh and concrete
    records = []
    def spawn(name, center, size, rotation, material):
        actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),rotation,False)
        actor.set_actor_label('OTS_RoadRevision_'+name)
        actor.set_folder_path(unreal.Name('OldTownSchoolStreet/RevisedRoads'))
        actor.set_editor_property('tags',[unreal.Name(ROAD_TAG)])
        actor.set_actor_scale3d(unreal.Vector(*[s/100. for s in size]))
        c = actor.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh)
        c.set_material(0,material)
        c.set_collision_profile_name('BlockAll')
        records.append({'actor':actor.get_actor_label(),'asset':mesh.get_path_name(),'center_cm':center,'size_cm':size})
        return actor
    for surface in plan['ground_surfaces']:
        name = surface['name']
        if surface['kind'] == 'slab':
            lo,hi = surface['world_min'],surface['world_max']
            spawn(name,[(lo[i]+hi[i])*.5 for i in range(3)],[hi[i]-lo[i] for i in range(3)],unreal.Rotator(),
                  (asphalt or concrete) if name in ('MainRoad','WestCrossRoad','EastCrossRoad') else concrete)
        else:
            rect = surface['rect_xy']
            angle = math.atan2(surface['rise_cm'],surface['run_cm'])
            center = [(rect[0]+rect[2])*.5,(rect[1]+rect[3])*.5,
                      (surface['low_surface_z_cm']+surface['high_surface_z_cm'])*.5-10.*math.cos(angle)]
            spawn(name,center,[math.hypot(surface['run_cm'],surface['rise_cm']),rect[3]-rect[1],20.],
                  unreal.Rotator(pitch=math.degrees(angle),yaw=180.,roll=0.),concrete)
    for item in plan['replacement_party_walls']:
        lo,hi=item['world_min'],item['world_max']
        spawn(item['name'],[(lo[i]+hi[i])*.5 for i in range(3)],[hi[i]-lo[i] for i in range(3)],unreal.Rotator(),wall)
    return records


def adjust_overhead_wires(subsystem):
    records=[]
    for actor in subsystem.get_all_level_actors():
        if not actor.get_actor_label().startswith('OTS_OverheadWire_'):
            continue
        if 'OTS_WiresAdjusted_20261003' in {str(t) for t in actor.tags}:
            continue
        component=actor.get_component_by_class(unreal.StaticMeshComponent)
        transform=component.get_world_transform()
        bounds=component.static_mesh.get_bounds()
        points=[]
        for sign in (-1.,1.):
            p=transform.transform_location(unreal.Vector(bounds.origin.x+sign*bounds.box_extent.x,bounds.origin.y,bounds.origin.z))
            points.append([p.x,p.y+150.-300.*(p.x-2200.)/2500.,p.z])
        first,last=points
        actor.set_actor_location(unreal.Vector(*[(first[i]+last[i])*.5 for i in range(3)]),False,False)
        actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*first),unreal.Vector(*last)),False)
        scale=actor.get_actor_scale3d()
        actor.set_actor_scale3d(unreal.Vector(math.dist(first,last)/(2.*bounds.box_extent.x),scale.y,scale.z))
        component.set_collision_profile_name('NoCollision')
        actor.set_editor_property('tags',list(actor.tags)+[unreal.Name('OTS_WiresAdjusted_20261003')])
        records.append({'actor':actor.get_actor_label(),'world_endpoints_cm':points,'collision':'NoCollision'})
    return records


def spawn_references_and_cameras(subsystem, assets, buildings, placements):
    label = 'BLK_L_Enter_C_Mass'
    b = next(x for x in buildings['buildings'] if x['label']==label)
    table = next(p for p in placements if p['building']==label and p['group']=='Table')['location_cm']
    bed = next(p for p in placements if p['building']==label and p['group']=='Bed')['assembly_origin_cm']
    ref_plans = [('OTS_Reference_TableHuman',[table[0]+150.,table[1]+20.,b['floor_z'][0]],0.),
                 ('OTS_Reference_AlleyHuman',[2570.,-1100.,11.],0.),
                 ('OTS_Reference_BedHuman',[bed[0]+150.,bed[1]+10.,b['floor_z'][1]],0.),
                 ('OTS_Reference_SchoolHuman',[-1550.,-700.,35.],0.)]
    for name,position,yaw in ref_plans:
        a=subsystem.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*position),unreal.Rotator(pitch=0.,yaw=yaw,roll=0.),False)
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HumanScaleReferences'))
        a.set_editor_property('tags',[unreal.Name(REFERENCE_TAG)])
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(assets['SM_OTS_HumanReference_180x50'])
        c.set_collision_profile_name('NoCollision')
    stair=b['stairs'][0]['foot_waypoints']
    cameras=[('CAM_Revision_TableHuman',[table[0]+420.,table[1]+420.,176.],[table[0]+30.,table[1]+40.,90.],60.),
             ('CAM_Revision_AlleyHuman',[2570.,-420.,176.],[2570.,-1550.,120.],60.),
             ('CAM_Revision_BedHuman',[bed[0]+420.,bed[1]+420.,b['floor_z'][1]+165.],[bed[0]+35.,bed[1]+25.,b['floor_z'][1]+95.],60.),
             ('CAM_Revision_StairClosed',b['ground_route'][1][:2]+[176.],stair[len(stair)//2][:2]+[stair[len(stair)//2][2]+85.],65.),
             ('CAM_Revision_EntranceFlush',[1900.,-245.,176.],[1900.,-700.,105.],60.),
             ('CAM_Revision_RoadPlan',[1250.,0.,16000.],[1250.,0.,0.],60.)]
    from BuildEnterableOldTown import add_review_cameras
    existing=add_review_cameras(subsystem,buildings,placements)
    by_label={a.get_actor_label():a for a in subsystem.get_all_level_actors()}
    for name,position,target,fov in cameras:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position),unreal.Vector(*target))
        a=by_label.get(name) or subsystem.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*position),rot,False)
        a.set_actor_label(name)
        a.set_actor_location(unreal.Vector(*position),False,False)
        a.set_actor_rotation(rot,False)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/RevisionReview'))
        c=a.get_component_by_class(unreal.CameraComponent)
        c.set_editor_property('field_of_view',fov)
    for a in subsystem.get_all_level_actors():
        c=a.get_component_by_class(unreal.CameraComponent)
        if c:
            pp=c.get_editor_property('post_process_settings')
            pp.set_editor_property('override_auto_exposure_bias',True)
            pp.set_editor_property('auto_exposure_bias',-1.0)
            c.set_editor_property('post_process_settings',pp)
            c.set_editor_property('post_process_blend_weight',1.0)
            if a.get_actor_label() in existing:
                c.set_editor_property('field_of_view',65.)
    return [x[0] for x in ref_plans],existing+[x[0] for x in cameras]


def main():
    from OldTownRoadLayoutRevision import plan_road_layout
    from ConvertOldTownBuildings import convert_buildings
    from ImportOldTownBlenderFurniture import import_furniture,place_furniture,LAST_PLACEMENT_DIAGNOSTICS
    from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home
    from AuditOldTownRevision import audit_revision
    from OldTownHumanScalePlan import target_parts
    before = json.loads((REVISION/'Before/BuildReport.json').read_text(encoding='utf-8'))
    inventory=json.loads((OUTPUT/'SourceInventory.json').read_text(encoding='utf-8'))
    plan=plan_road_layout(inventory,before['buildings'])
    protected=[PROJECT/'Content/Yastar/Maps/Blockout/L_Chapter01_Blockout.umap',PROJECT/'Content/Yastar/Maps/L_Main.umap']
    protected_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()}
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith(TARGET+'.')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    home=validate_main_home(list(actors.get_all_level_actors()))
    adjustments=apply_source_adjustments(actors,plan)
    buildings=convert_buildings(actors,plan)
    buildings['world_ground_rect']=plan['layout']['world_ground_rect']
    roads=emit_roads(actors,plan)
    wires=adjust_overhead_wires(actors)
    furniture,imports=import_furniture(MANIFEST)
    placements=place_furniture(actors,furniture,buildings,MANIFEST)
    references,cameras=spawn_references_and_cameras(actors,furniture,buildings,placements)
    current=list(actors.get_all_level_actors())
    refreshed=refresh_world_collision(current)
    assert home==validate_main_home(current)
    validation=validate_buildings(world,current,buildings)
    write('CollisionValidation.json',validation)
    plan['audit_expectations']={'human_actor_labels':references,'furniture_parts':target_parts(),
                                'stair_side_panels':buildings['stair_side_panels']}
    report={'status':'PENDING','target_level':TARGET,'actor_count':len(current),'buildings':buildings,
            'assets':before['assets'],'blender_imports':imports,'furniture_placements':placements,
            'furniture_manifest':str(MANIFEST),'furniture_placement_diagnostics':LAST_PLACEMENT_DIAGNOSTICS,
            'collision':validation,'main_home':home,'review_cameras':cameras,'human_actor_labels':references,
            'roads':roads,'source_adjustments':adjustments,'refreshed_collision_components':refreshed,
            'overhead_wire_adjustments':wires,
            'protected_map_sha256':protected_hashes}
    write('RevisionPlan.json',plan)
    write('RevisionPending.json',report)
    audit=audit_revision(world,current,report,plan)
    write('RevisionAudit.json',audit)
    assert validation['passed'], 'Revision collision checks failed; level was not saved'
    assert audit['passed'], 'Revision independent audit failed; level was not saved'
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected_hashes.items())
    assert levels.save_current_level()
    report.update(status='PASS',map_sha256=hashlib.sha256(MAP_FILE.read_bytes()).hexdigest(),revision_audit=audit)
    write('BuildingReport.json',buildings)
    write('BlenderImportReport.json',imports)
    write('BuildReport.json',report)
    unreal.SystemLibrary.execute_console_command(world,'MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG')
    unreal.log('OTS_STREET_REVISION_SUCCESS '+report['map_sha256'])
    return report


if __name__=='__main__':
    try:
        main()
    except Exception:
        unreal.log_error('OTS_STREET_REVISION_FAILED\n'+traceback.format_exc())
        raise
