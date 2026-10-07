"""Refine the saved F5 street with new Blender geometry and fitted paving."""
from collections import Counter
import hashlib, json, math, sys
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(PROJECT/'Scripts'))
from ConvertOldTownBuildings import MeshFactory,plan_buildings
from OldTownArchitectureSealPlan import door_world_box,door_coordinates
from OldTownDetailGroundPlan import normalize_ground_surfaces
from PlanOldTownDetailMeshes import key
from ImportOldTownBlenderFurniture import _infer_axes
from AuditOldTownRevision import _mesh_box,audit_revision
from AuditOldTownLightingCleanup import audit_cleanup
from AuditOldTownArchitectureSeal import audit_architecture
from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home

TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
OUT=PROJECT/'Saved/CodexOutputs/EnterableStreet_20261002'
WORK=PROJECT/'Saved/CodexOutputs/DetailPolish_20261004'
SOURCE=PROJECT/'SourceArt/OldTownDetailPolish_20261004'
MAP=PROJECT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TAG='OTS_DetailPolish_20261004'
DEST='/Game/Yastar/Meshes/hOUSE/DetailPolish_20261004'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name,data):
    for folder in (OUT,WORK):
        (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def xyz(v):return [float(v.x),float(v.y),float(v.z)]
def union(boxes):return [[min(b[0][i] for b in boxes) for i in range(3)],[max(b[1][i] for b in boxes) for i in range(3)]]
def actor_bounds(a):
    return union([_mesh_box(c)['bounds_cm'] for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh])
def hide(a):
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        c.set_visibility(False,True);c.set_editor_property('cast_shadow',False)
        c.set_hidden_in_game(True,True)

def import_meshes(world,force=False):
    unreal.EditorAssetLibrary.make_directory(DEST)
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    manifest=read(SOURCE/'ImportManifest.json');assets={};reports=[]
    mats={'Concrete':unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete'),
          'Trim':unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Props/Detailed/Materials/M_P2_Wood'),
          'Green':unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldGreenMetal'),
          'Metal':unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_RustMetal')}
    assert all(mats.values())
    for e in manifest['assets']:
        assert e['name'].startswith('SM_OTS_Polish_') and e['nonmanifold_edges']==0
        path=DEST+'/'+e['name'];mesh=unreal.load_asset(path)
        if mesh is None or force:
            if mesh:
                data=mesh.get_editor_property('asset_import_data')
                for prop,value in {'convert_scene':True,'convert_scene_unit':True,'import_uniform_scale':1.}.items():data.set_editor_property(prop,value)
            options=unreal.FbxImportUI()
            for prop,value in {'import_mesh':True,'import_as_skeletal':False,'import_animations':False,
                               'import_materials':False,'import_textures':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
                options.set_editor_property(prop,value)
            data=options.get_editor_property('static_mesh_import_data')
            for prop,value in {'combine_meshes':True,'auto_generate_collision':False,'generate_lightmap_u_vs':True,
                               'convert_scene':True,'convert_scene_unit':True,'import_uniform_scale':1.}.items():data.set_editor_property(prop,value)
            task=unreal.AssetImportTask()
            for prop,value in {'filename':str(SOURCE/e['file']),'destination_path':DEST,'destination_name':e['name'],
                               'automated':True,'replace_existing':bool(force),'save':False,'options':options,'factory':unreal.FbxFactory()}.items():task.set_editor_property(prop,value)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);mesh=unreal.load_asset(path)
        assert isinstance(mesh,unreal.StaticMesh),path
        for i,slot in enumerate(mesh.get_editor_property('static_materials')):
            slot_name=str(slot.get_editor_property('material_slot_name'))
            material=next((mat for name,mat in mats.items() if name.lower() in slot_name.lower()),None)
            assert material,slot_name
            mesh.set_material(i,material)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,'OldTownDetailSourceSHA256',hashlib.sha256((SOURCE/e['file']).read_bytes()).hexdigest())
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,False)
        assets[e['name']]=mesh
        reports.append({'asset':mesh.get_path_name(),'source':e['file'],'source_sha256':hashlib.sha256((SOURCE/e['file']).read_bytes()).hexdigest()})
    axes=_infer_axes(manifest['assets'],assets)
    assert tuple(axes['order'])==(0,1,2),axes
    (SOURCE/'UnrealAxisVerification.json').write_text(json.dumps(axes,indent=2),encoding='utf-8')
    return assets,reports,axes

def main():
    build=read(OUT/'BuildReport.json');plan=read(OUT/'RevisionPlan.json')
    baseline=read(WORK/'Before/BuildReport.json')
    assert 'detail_polish' not in build,'Use the repair script for an already saved detail phase'
    assert hashlib.sha256(MAP.read_bytes()).hexdigest()==baseline['map_sha256']==build['map_sha256']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in build['protected_map_sha256'].items())
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by={a.get_actor_label():a for a in sub.get_all_level_actors()}
    geometry=plan_buildings([],plan);by_b={b.label:b for b in geometry}
    assets,imports,axes=import_meshes(world)
    detail={'manifest_path':str((SOURCE/'ImportManifest.json').relative_to(PROJECT)),
            'imports':imports,'axes':axes,'visuals':[],'fills':[],'stairs':[],'attachments':[],
            'door_behavior':'Original single doors remain fixed open at 90 degrees'}

    def spawn(name,asset,pos,yaw,kind,hidden=()):
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/DetailPolish/'+kind))
        a.set_editor_property('tags',[unreal.Name(TAG)])
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(asset);c.set_collision_profile_name('NoCollision')
        a.set_actor_enable_collision(False)
        bounds=actor_bounds(a)
        row={'actor':name,'asset':asset.get_path_name(),'kind':kind,'world_min':bounds[0],'world_max':bounds[1],
             'hidden_collision_actor_labels':list(hidden),'location_cm':pos,'yaw_degrees':yaw}
        detail['visuals'].append(row)
        for old in hidden:hide(by[old])
        return a,row

    def yaw_for_source_y(direction):
        angle=math.degrees(math.atan2(direction[1],direction[0]))
        return angle-(90. if axes['signs'][1]>0 else -90.)

    # Ground rectangles are physically trimmed, maintaining their complete material-specific footprint.
    updated,partition=normalize_ground_surfaces(plan)
    detail['paving_partition']=partition
    assert partition['original_overlap_pair_count']==48 and partition['final_overlap_pair_count']==0
    original_labels={'OTS_RoadRevision_'+s['name'] for s in plan['ground_surfaces'] if s['kind']=='slab'}
    for label in original_labels:assert sub.destroy_actor(by[label]),label
    base=unreal.load_asset('/Game/Yastar/Meshes/hOUSE/SM_OTS_Enterable_FloorSlab')
    concrete=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete')
    asphalt=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_WetAsphalt')
    roads=[r for r in build['roads'] if r['actor'] not in original_labels]
    for s in updated:
        if s['kind']!='slab':continue
        lo,hi=s['world_min'],s['world_max'];center=[(lo[i]+hi[i])/2 for i in range(3)];size=[hi[i]-lo[i] for i in range(3)]
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),unreal.Rotator(),False)
        a.set_actor_label('OTS_RoadRevision_'+s['name']);a.set_folder_path(unreal.Name('OldTownSchoolStreet/RevisedRoads'))
        a.set_editor_property('tags',[unreal.Name('OTS_RoadRevision_20261003')])
        a.set_actor_scale3d(unreal.Vector(*[v/100 for v in size]))
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(base)
        c.set_material(0,asphalt if s['material_group']=='asphalt' else concrete);c.set_collision_profile_name('BlockAll')
        s['actor']=a.get_actor_label()
        roads.append({'actor':a.get_actor_label(),'asset':base.get_path_name(),'center_cm':center,'size_cm':size})
    plan['ground_surfaces']=updated;build['roads']=roads
    build['street_end_cleanup']['road_surface_expectations']=[{'actor':s.get('actor','OTS_RoadRevision_'+s['name']),
             'world_min':s['world_min'],'world_max':s['world_max']} for s in updated if s['kind']=='slab']

    # Close only the wall-thickness floor strip; it never protrudes in front of a door.
    factory=MeshFactory(sub);factory.count=max(9000,build['buildings']['generated_actor_count'])
    factory.lighting_policy='street_lamps_only'
    for b in geometry:
        p=b.portals[0]
        lo,hi=door_world_box(b,p,[-b.door_width/2,0,b.ground-20],[b.door_width/2,19.5,b.ground])
        a=factory.world_box(b.label,'EntryFloorFill',lo,hi,concrete,True)
        detail['fills'].append({'building':b.label,'actor':a.get_actor_label(),'world_min':lo,'world_max':hi,
            'surface_z_cm':b.ground,'door_wall':p['wall'],'door_coordinate_cm':p['coordinate'],'door_width_cm':b.door_width})
    structure=build['buildings'];structure['structural_boxes']+=factory.placed_boxes
    structure['generated_actor_count']=len(structure['structural_boxes'])
    structure['module_actor_distribution']=dict(Counter(r['role'] for r in structure['structural_boxes']))
    structure['generated_assets']=sorted(set(structure['generated_assets']+[m.get_path_name() for m in factory.modules.values()]))

    # All old collision geometry remains registered, but the render is a closed flight with a sloping soffit.
    rows=structure['structural_boxes']
    for b in geometry:
        if b.count<2:continue
        inward=[0.,0.];inward[b.normal_axis]=b.inward
        yaw=yaw_for_source_y(inward)
        for level in range(b.count-1):
            z=b.floors[level];mid=z+b.n1*b.rise;end=b.core_v+b.n1*28
            tread_rows=[r for r in rows if r['building']==b.label and r['role']=='StairTread'
                        and z+.01<r['max'][2]<=b.floors[level+1]+.01]
            old1=[];old2=[]
            for r in tread_rows:
                lo,hi=b.local(r['min']),b.local(r['max'])
                (old1 if (lo[0]+hi[0])/2<b.core_u else old2).append(r['actor'])
            assert len(old1)==b.n1 and len(old2)==b.n2,(b.label,level,len(old1),len(old2))
            a1,r1=spawn('OTS_Polish_Flight_'+b.label+'_'+str(level)+'_A',assets[key('Flight',b.n1,b.rise)],
                b.world(b.core_u-80,b.core_v,z),yaw,'flight',old1)
            a2,r2=spawn('OTS_Polish_Flight_'+b.label+'_'+str(level)+'_B',assets[key('Flight',b.n2,b.rise)],
                b.world(b.core_u+80,end,mid),yaw+180,'flight',old2)
            land_rows=[r for r in rows if r['building']==b.label and r['role']=='StairLanding' and abs(r['max'][2]-mid)<.01]
            assert len(land_rows)==1,(b.label,level,land_rows)
            la,lr=spawn('OTS_Polish_Landing_'+b.label+'_'+str(level),assets[key('Landing',300,140,20+b.rise)],
                b.world(b.core_u,end+70,mid),yaw,'landing',[land_rows[0]['actor']])
            detail['stairs'].append({'building':b.label,'from_floor':level,'rise_cm':b.rise,'story_cm':b.story,
                'flight_visual_actors':[a1.get_actor_label(),a2.get_actor_label()],'landing_visual_actor':la.get_actor_label(),
                'minimum_vertical_clearance_cm':b.story-20-2*b.rise,'landing_depth_cm':140.,'flight_width_cm':140.})

    for w in build['architecture_seal']['windows']:
        b=by_b[w['building']];sgn=1 if w['wall']=='Front' else -1
        inward=[0.,0.];inward[b.normal_axis]=b.inward*sgn
        a,row=spawn('OTS_Polish_InnerTrim_'+w['name'],assets[key('InnerTrim',w['width'],w['height'])],
            b.world(w['u'],w['v']+sgn*21.25,w['z']),yaw_for_source_y(inward),'inner_trim')
        row['window_actor']=w['actor'];row['opening_cm']=[w['width'],w['height']]
        row['intrusion_into_opening_cm']=4.;row['wall_overlap_cm']=3.

    for d in build['architecture_seal']['doors']:
        b=by_b[d['building']];p=b.portals[0]
        center=[(d['world_min'][i]+d['world_max'][i])/2 for i in range(3)]
        v0=door_coordinates(b,p,0,0,0);v1=door_coordinates(b,p,0,1,0)
        yaw=yaw_for_source_y([v1[i]-v0[i] for i in (0,1)])
        a,row=spawn('OTS_Polish_Door_'+b.label,assets[key('Door',b.door_width-8,b.door_height-6)],center,yaw,'door',
                    [d['actor'],d['handle_actor']])
        row['building']=b.label;row['hinge_side']=d['hinge_side'];row['leaf_collision_actor']=d['actor']

    # Re-seat complete attachment assemblies against the street-end facade.
    attachment_labels=build['street_end_cleanup']['attachment_expected_positions']
    groups=[('FloorCourse',['OTS_StreetEndFocalFloorCourse_01']),
            ('Cornice',['OTS_StreetEndFocalCornice_01']),('CorniceCap',['OTS_StreetEndFocalCorniceCap_01']),
            ('Sign',['OTS_P3Prop_SignAssemblyStreetEnd_01','OTS_P3Prop_SignTextStreetEnd_01']),
            ('Awning',['OTS_P3Prop_AwningAssemblyStreetEnd_01']),
            ('Utility',[k for k in attachment_labels if 'WallUtilityCluster_05_' in k])]
    for group,names in groups:
        mesh_actors=[by[n] for n in names if by[n].get_components_by_class(unreal.StaticMeshComponent)]
        bounds=union([actor_bounds(a) for a in mesh_actors])
        delta=[9000.5-bounds[1][0],-460. if group=='Utility' else 0.,0.]
        for label in names:
            a=by[label];old=xyz(a.get_actor_location());pos=[old[i]+delta[i] for i in range(3)]
            a.set_actor_location(unreal.Vector(*pos),False,False);attachment_labels[label]=pos
            if a in mesh_actors:
                box=actor_bounds(a)
                detail['attachments'].append({'actor':label,'delta_cm':delta,'world_min':box[0],
                    'world_max':box[1],'group':group,'wall_x_cm':9000.})
                if group=='Utility' and box[1][0]<9000.1:
                    # Separate electrical parts need their own small wall mounts;
                    # the downpipe is not a support for the adjacent meter boxes.
                    lo=[box[1][0]-.25,(box[0][1]+box[1][1])/2-4,(box[0][2]+box[1][2])/2-5]
                    hi=[9000.5,lo[1]+8,lo[2]+10]
                    mount=factory.world_box('OTS_PerimeterBoundaryEast_01','UtilityWallMount',lo,hi,
                        unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkTrim'),False)
                    detail['attachments'].append({'actor':mount.get_actor_label(),'delta_cm':[0,0,0],
                        'world_min':lo,'world_max':hi,'group':group,'wall_x_cm':9000.})
    structure['structural_boxes'] += [r for r in factory.placed_boxes if r['role']=='UtilityWallMount']
    structure['generated_actor_count']=len(structure['structural_boxes'])
    structure['module_actor_distribution']=dict(Counter(r['role'] for r in structure['structural_boxes']))
    structure['generated_assets']=sorted(set(structure['generated_assets']+[m.get_path_name() for m in factory.modules.values()]))
    build['detail_polish']=detail

    b=by_b['BLK_L_Enter_C_Mass'];w=next(w for w in build['architecture_seal']['windows'] if w['building']==b.label and w['floor']==0)
    p=b.portals[0]
    cams=[('CAM_Polish_Stair',b.world(b.core_u,b.core_v-200,b.ground+155),b.world(b.core_u,b.core_v+130,b.ground+175),70.),
          ('CAM_Polish_DoorWindow',b.world(0,-460,b.ground+155),b.world(0,25,b.ground+150),70.),
          ('CAM_Polish_InnerTrim',b.world(w['u'],180,b.ground+160),b.world(w['u'],15,w['z']),60.),
          ('CAM_Polish_EntryFloor',door_coordinates(b,p,0,-160,b.ground+65),door_coordinates(b,p,0,35,b.ground+10),65.)]
    for name,pos,target,fov in cams:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*target))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*pos),rot,False)
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/DetailPolish/Review'))
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
    build['detail_review_cameras']=[r[0] for r in cams]+['CAM_Cleanup_Junction','CAM_Cleanup_TurnNorth']
    actors=list(sub.get_all_level_actors());refresh_world_collision(actors)
    assert validate_main_home(actors)==build['main_home']
    build['collision']=validate_buildings(world,actors,structure);write('CollisionValidation.json',build['collision'])
    assert build['collision']['passed'],'Original building route collision failed'
    for name,callback in [('RevisionAudit.json',lambda:audit_revision(world,actors,build,plan)),
                          ('LightingCleanupAudit.json',lambda:audit_cleanup(world,actors,build)),
                          ('ArchitectureSealAudit.json',lambda:audit_architecture(world,actors,build,plan))]:
        report=callback();write(name,report);assert report['passed'],report['errors']
        if name=='RevisionAudit.json':build['revision_audit']=report
    from AuditOldTownDetailPolish import audit_details
    report=audit_details(world,actors,build,plan);write('DetailPolishAudit.json',report);assert report['passed'],report['errors']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in build['protected_map_sha256'].items())
    assert levels.save_current_level()
    build['actor_count']=len(actors);build['map_sha256']=hashlib.sha256(MAP.read_bytes()).hexdigest()
    build['architecture_seal']['map_sha256']=build['map_sha256'];detail['map_sha256']=build['map_sha256']
    write('BuildReport.json',build);write('BuildingReport.json',structure);write('RevisionPlan.json',plan)
    unreal.log('OTS_DETAIL_POLISH_SUCCESS '+build['map_sha256'])

if __name__=='__main__':main()
