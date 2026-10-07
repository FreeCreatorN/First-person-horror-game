"""Read-only saved-world checks for the detailed street refinement."""
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import traceback

import unreal

TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
CANONICAL = 'Saved/CodexOutputs/EnterableStreet_20261002'
WORK = 'Saved/CodexOutputs/DetailPolish_20261004'
TOLERANCE = .1


def _near(a, b):
    return len(a) == len(b) and all(abs(float(x)-float(y)) <= TOLERANCE for x, y in zip(a, b))


def _bounds(component):
    center, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    return [[float(getattr(center, axis)-getattr(extent, axis)) for axis in ('x','y','z')],
            [float(getattr(center, axis)+getattr(extent, axis)) for axis in ('x','y','z')]]


def _union(boxes):
    return [[min(b[0][i] for b in boxes) for i in range(3)],
            [max(b[1][i] for b in boxes) for i in range(3)]]


def _visible(component):
    return bool(component.get_editor_property('visible'))


def _no_collision(component):
    return component.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value


def _block_all(component):
    channels = (unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
                unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_VISIBILITY,
                unreal.CollisionChannel.ECC_CAMERA)
    return not _no_collision(component) and all(
        component.get_collision_response_to_channel(c).value == unreal.CollisionResponseType.ECR_BLOCK.value
        for c in channels)


def audit_details(world, actors, build, plan):
    from AuditOldTownRevision import _mesh_box, _step_probe, _support
    from ConvertOldTownBuildings import plan_buildings
    from OldTownArchitectureSealPlan import door_coordinates
    from ValidateEnterableStreet import floor_support
    from OldTownDetailGroundPlan import _overlaps
    project = Path(unreal.Paths.project_dir()).resolve()
    actors = list(actors)
    report = {'passed':False, 'target_level':TARGET, 'checks':[], 'errors':[], 'statistics':{},
              'limitations':[
                  'Manifest nonmanifold counts prove source topology, not imported triangle identity or absence of self intersections.',
                  'Visual meshes have no collision. Source stair clearance is analytic; imported visible soffit clearance still requires independent triangle-level verification.',
                  'Wall attachment contacts use conservative component AABBs; bevelled triangle contact is not certified.',
                  'Editor collision sampling is not a runtime player walkthrough.']}
    def check(name, passed, **details):
        report['checks'].append(dict(details, name=name, passed=bool(passed)))
        if not passed: report['errors'].append(name)
    def section(name, callback):
        try: callback()
        except Exception: check(name+':exception',False,traceback=traceback.format_exc())
    if world is None or not world.get_path_name().startswith(TARGET+'.'):
        check('loaded_target_world',False)
        return report
    check('loaded_target_world',True)
    spec = build.get('detail_polish', {})
    check('detail_expectations_present',bool(spec))
    by = defaultdict(list)
    meshes = defaultdict(list)
    for actor in actors:
        label = actor.get_actor_label()
        by[label].append(actor)
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            if c.static_mesh:
                meshes[label].append((c,_mesh_box(c)))
    check('unique_actor_labels',all(len(v)==1 for v in by.values()))
    visuals = spec.get('visuals', [])
    visual_by = {v['actor']:v for v in visuals}
    geometry = {b.label:b for b in plan_buildings([],plan)}
    manifest = {}

    def visual_meshes():
        check('visual_expectations_unique',bool(visuals) and len(visual_by)==len(visuals))
        for row in visuals:
            label = row['actor']
            items = meshes.get(label, [])
            good = len(by.get(label,[]))==1 and len(items)==1
            data = items[0][1] if len(items)==1 else None
            check('visual_mesh:'+label,good and data['asset']==row['asset'].split('.',1)[0]
                  and _near(data['bounds_cm'][0],row['world_min'])
                  and _near(data['bounds_cm'][1],row['world_max'])
                  and _no_collision(items[0][0]) and _visible(items[0][0]),
                  actual_bounds_cm=data['bounds_cm'] if data else None,
                  expected_bounds_cm=[row['world_min'],row['world_max']])
            for hidden in row.get('hidden_collision_actor_labels',[]):
                old = meshes.get(hidden,[])
                handle = 'DoorHandle' in hidden
                check('retained_hidden_collider:'+hidden,len(by.get(hidden,[]))==1 and len(old)==1
                      and not _visible(old[0][0])
                      and (_no_collision(old[0][0]) if handle else _block_all(old[0][0])),
                      no_collision_handle_exception=handle)
        trim_count = sum('trim' in str(row.get('kind','')).lower() for row in visuals)
        if build.get('opening_components'):
            migrated = spec.get('migrated_opening_visuals', [])
            check('old_opening_visuals_migrated',trim_count==0
                  and len([r for r in migrated if r.get('kind')=='inner_trim'])==291
                  and len([r for r in migrated if r.get('kind')=='door'])==29
                  and all(not by.get(r['actor']) for r in migrated),
                  remaining_old_trims=trim_count,migrated_visual_count=len(migrated))
        else:
            check('291_inner_window_trims',trim_count==291,actual_count=trim_count)

    def source_manifest():
        path = Path(spec.get('manifest_path','SourceArt/OldTownDetailPolish_20261004/ImportManifest.json'))
        if not path.is_absolute(): path = project/path
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        manifest.update({row['name']:row for row in data['assets']})
        check('source_manifest_centimeter_units',data.get('units')=='centimeters')
        for row in visuals:
            name = row['asset'].split('.',1)[0].rsplit('/',1)[-1]
            entry = manifest.get(name)
            source = path.parent/entry['file'] if entry else None
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source and source.is_file() else None
            items = meshes.get(row['actor'],[])
            imported_hash = (unreal.EditorAssetLibrary.get_metadata_tag(items[0][0].static_mesh,'OldTownDetailSourceSHA256')
                             if len(items)==1 else None)
            check('watertight_source:'+row['actor'],entry is not None
                  and entry.get('nonmanifold_edges')==0 and entry.get('vertices',0)>0
                  and entry.get('polygons',0)>0 and source.is_file()
                  and source_hash==imported_hash,
                  manifest_asset=name,nonmanifold_edges=entry.get('nonmanifold_edges') if entry else None,
                  source_sha256=source_hash,imported_source_sha256=imported_hash)

    def entry_floors():
        fills = spec.get('fills',[])
        check('29_unique_flush_entry_fills',len(fills)==29 and len({r['building'] for r in fills})==29)
        for row in fills:
            label = row['actor']
            items = meshes.get(label,[])
            box = items[0][1]['bounds_cm'] if len(items)==1 else None
            b = geometry[row['building']]
            portal = b.portals[0]
            check('entry_fill_mesh:'+label,len(by.get(label,[]))==1 and box is not None
                  and _near(box[0],row['world_min']) and _near(box[1],row['world_max'])
                  and abs(box[1][2]-b.ground)<=.15 and abs(float(row['surface_z_cm'])-b.ground)<=.15
                  and _block_all(items[0][0]) and _visible(items[0][0])
                  and row['door_wall']==portal['wall']
                  and abs(float(row['door_coordinate_cm'])-portal['coordinate'])<=.1
                  and abs(float(row['door_width_cm'])-b.door_width)<=.1,
                  actual_bounds_cm=box)
            samples = []
            for a in (-b.door_width*.5+15.,0.,b.door_width*.5-15.):
                for n in range(-5,26,5):
                    foot = door_coordinates(b,portal,a,float(n),b.ground)
                    samples.append(floor_support(world,foot,tolerance=.15))
            check('three_flush_entry_tracks:'+row['building'],all(r['passed'] for r in samples),samples=samples)

    def paving():
        partition = spec.get('paving_partition',{})
        check('zero_partition_coverage_difference',partition.get('status')=='PASS'
              and partition.get('symmetric_difference_area_cm2')==0
              and partition.get('final_overlap_pair_count')==0
              and partition.get('final_overlap_pairs')==[]
              and partition.get('ramps_unchanged') is True
              and bool(partition.get('groups'))
              and all(g.get('coverage_difference_cells')==[]
                      and g.get('symmetric_difference_area_cm2')==0
                      and g.get('lost_coverage_area_cm2')==0 and g.get('added_coverage_area_cm2')==0
                      for g in partition.get('groups',[])))
        slabs = [s for s in plan.get('ground_surfaces',[]) if s.get('kind')=='slab']
        check('actual_plan_has_no_coplanar_overlap',not _overlaps(slabs),overlaps=_overlaps(slabs))
        for s in slabs:
            label = s.get('actor','OTS_RoadRevision_'+s['name'])
            items = meshes.get(label,[])
            box = items[0][1]['bounds_cm'] if len(items)==1 else None
            check('partition_slab:'+s['name'],len(by.get(label,[]))==1 and box is not None
                  and _near(box[0],s['world_min']) and _near(box[1],s['world_max'])
                  and _visible(items[0][0]) and _block_all(items[0][0]),actual_bounds_cm=box)
        corridors = partition.get('original_virtual_corridors',[])
        check('original_virtual_corridors_retained',bool(corridors))
        for row in corridors:
            rect = row['clear_rect_xy']; across = int(row['width_axis']); along = 1-across
            spans = [rect[i+2]-rect[i] for i in (0,1)]; failures = []; sample_count = 0
            count = max(1,math.ceil(spans[along]/100.))
            for index in range(count+1):
                for fraction in (0.,.25,.5,.75,1.):
                    foot = [(rect[i]+rect[i+2])*.5 for i in (0,1)]+[float(row['surface_z_cm'])]
                    foot[along] = rect[along]+min(spans[along]*.5,37.)+index/count*max(0.,spans[along]-74.)
                    foot[across] = rect[across]+37.+fraction*max(0.,spans[across]-74.)
                    z = _support(world,foot,above=45.,below=45.); sample_count += 1
                    if z is None or abs(z-foot[2])>45.01:
                        failures.append({'foot_cm':foot,'support_z_cm':z})
                    else:
                        probe = _step_probe(world,foot[:2]+[z],34.,180.)
                        if not probe['passed']: failures.append(dict(probe,foot_cm=foot[:2]+[z]))
            check('original_corridor_tracks:'+row['name'],spans[across]>=row['target_clear_width_cm']-.1
                  and not failures,samples=sample_count,failures=failures,
                  capsule_radius_cm=34.,capsule_height_cm=180.)

    def attached_groups():
        groups = defaultdict(list)
        for row in spec.get('attachments',[]):
            label = row['actor']; found = by.get(label,[]); mesh_items = meshes.get(label,[])
            boxes = [data['bounds_cm'] for _c,data in mesh_items]
            if not boxes and len(found)==1:
                boxes = [_bounds(c) for c in found[0].get_components_by_class(unreal.PrimitiveComponent)]
            box = _union(boxes) if boxes else None
            delta = row.get('delta_cm',[])
            check('attachment_bounds:'+label,len(found)==1 and box is not None
                  and _near(box[0],row['world_min']) and _near(box[1],row['world_max'])
                  and len(delta)==3 and all(math.isfinite(float(v)) for v in delta),actual_bounds_cm=box)
            if box: groups[row['group']].append({'actor':label,'bounds':box,'mesh':bool(mesh_items),
                                               'wall_x':float(row.get('wall_x_cm',9000.))})
        check('attachment_groups_present',bool(groups))
        for name, rows in groups.items():
            box = _union([r['bounds'] for r in rows]); wall = rows[0]['wall_x']
            check('attachment_group_embeds_wall:'+name,all(abs(r['wall_x']-wall)<.1 for r in rows)
                  and box[1][0]>=wall+.1-.001,group_bounds_cm=box,wall_x_cm=wall)
            solids = [r for r in rows if r['mesh']]
            reached = {i for i,r in enumerate(solids) if r['bounds'][0][0]<=wall+.1 and r['bounds'][1][0]>=wall+.1-.001}
            changed = True
            while changed:
                changed = False
                for i,r in enumerate(solids):
                    if i in reached: continue
                    if any(all(min(r['bounds'][1][k],solids[j]['bounds'][1][k])
                               -max(r['bounds'][0][k],solids[j]['bounds'][0][k])>=-.1 for k in range(3)) for j in reached):
                        reached.add(i); changed = True
            check('mesh_attachment_group_contact:'+name,bool(solids) and len(reached)==len(solids),
                  unconnected_meshes=[r['actor'] for i,r in enumerate(solids) if i not in reached])

    def stairs():
        rows = spec.get('stairs',[])
        expected = {(b.label,i) for b in geometry.values() for i in range(b.count-1)}
        actual = {(r['building'],r['from_floor']) for r in rows}
        check('all_81_stair_connections_have_visuals',len(rows)==len(expected)==81 and actual==expected)
        for row in rows:
            b = geometry[row['building']]; rise = float(row['rise_cm']); story = float(row['story_cm'])
            clearance = story-20.-2.*rise
            labels = row['flight_visual_actors']+[row['landing_visual_actor']]
            source_rows = [manifest.get(visual_by[label]['asset'].split('.',1)[0].rsplit('/',1)[-1],{})
                           for label in labels if label in visual_by]
            check('continuous_stair_sources:'+row['building']+':'+str(row['from_floor']),
                  len(row['flight_visual_actors'])==2 and len(set(labels))==3
                  and all(label in visual_by for label in labels) and len(source_rows)==3
                  and [r.get('kind') for r in source_rows]==['flight','flight','landing']
                  and all(r.get('nonmanifold_edges')==0 for r in source_rows))
            axes = spec.get('axes',{})
            order,signs = axes.get('order'),axes.get('signs')
            plane_rows = []
            if order is not None and signs is not None and len(source_rows)==3:
                for index,label in enumerate(row['flight_visual_actors']):
                    items = meshes.get(label,[]); entry = source_rows[index]
                    if len(items)!=1 or entry.get('kind')!='flight': continue
                    steps,source_rise = entry['steps'],entry['rise']
                    run = steps*28.; transform = items[0][0].get_world_transform()
                    corners = []
                    for x in (-70.,70.):
                        for y,z in ((0.,-20.-source_rise),(run,steps*source_rise-20.-source_rise)):
                            p = [x,y,z]
                            v = transform.transform_location(unreal.Vector(*[p[order[i]]*signs[i] for i in range(3)]))
                            corners.append([float(v.x),float(v.y),float(v.z)])
                    lower = b.floors[row['from_floor']]
                    middle = lower+b.n1*b.rise
                    if index==0:
                        u,ends = b.core_u-80.,((b.core_v,lower-20.-b.rise),
                                              (b.core_v+b.n1*28.,middle-20.-b.rise))
                    else:
                        u,ends = b.core_u+80.,((b.core_v+b.n1*28.,middle-20.-b.rise),
                                              (b.core_v+(b.n1-b.n2)*28.,b.floors[row['from_floor']+1]-20.-b.rise))
                    expected_corners = [b.world(u+side,v,z) for side in (-70.,70.) for v,z in ends]
                    matched = all(any(_near(p,e) for e in expected_corners) for p in corners)
                    plane_rows.append({'actor':label,'transformed_source_soffit_corners_cm':corners,
                                       'expected_soffit_corners_cm':expected_corners,'passed':matched})
            check('source_soffit_placement:'+row['building']+':'+str(row['from_floor']),
                  len(plane_rows)==2 and all(r['passed'] for r in plane_rows),planes=plane_rows,
                  scope='Source lower-plane vertices transformed by actual imported component transforms; imported triangles still require independent verification')
            check('analytic_soffit_clearance:'+row['building']+':'+str(row['from_floor']),
                  abs(rise-b.rise)<.1 and abs(story-b.story)<.1 and 0.<rise<=18.01
                  and clearance>225. and abs(float(row['minimum_vertical_clearance_cm'])-clearance)<.1,
                  analytic_clearance_cm=clearance,required_cm=225.,
                  imported_triangle_clearance_verified=False)

    for name,callback in (('visuals',visual_meshes),('manifest',source_manifest),('entry_floors',entry_floors),
                          ('paving',paving),('attachments',attached_groups),('stairs',stairs)):
        section(name,callback)
    report['statistics'] = {'actors':len(actors),'visual_meshes':len(visuals),'entry_fills':len(spec.get('fills',[])),
                            'stair_connections':len(spec.get('stairs',[])),
                            'attachment_components':len(spec.get('attachments',[])),
                            'checks':len(report['checks']),'failed_checks':len(report['errors'])}
    report['passed'] = not report['errors']
    return report


def main():
    project = Path(unreal.Paths.project_dir()).resolve()
    sys.path.insert(0,str(project/'Scripts'))
    out,work = project/CANONICAL,project/WORK
    result = {'passed':False,'checks':[],'errors':['commandlet_exception'],'statistics':{}}
    try:
        build = json.loads((out/'BuildReport.json').read_text(encoding='utf-8-sig'))
        plan = json.loads((out/'RevisionPlan.json').read_text(encoding='utf-8-sig'))
        path = project/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
        map_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert map_hash==build['map_sha256']==build['architecture_seal']['map_sha256']==build['detail_polish']['map_sha256']
        for protected,expected in build['protected_map_sha256'].items():
            assert hashlib.sha256(Path(protected).read_bytes()).hexdigest()==expected,protected
        assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        from ValidateEnterableStreet import refresh_world_collision
        refresh_world_collision(actors)
        result = audit_details(world,actors,build,plan)
        result['map_sha256'] = map_hash
        assert hashlib.sha256(path.read_bytes()).hexdigest()==map_hash,'Map changed during read-only audit'
        for protected,expected in build['protected_map_sha256'].items():
            assert hashlib.sha256(Path(protected).read_bytes()).hexdigest()==expected,protected
    except Exception:
        result['passed'] = False
        result['errors'].append('commandlet_exception')
        result['traceback'] = traceback.format_exc()
    finally:
        for folder in (out,work):
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'DetailPolishAudit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if not result['passed']:
        unreal.log_error('OTS_DETAIL_POLISH_AUDIT_FAILED '+', '.join(result['errors']))
        raise RuntimeError('Detail polish audit failed; see DetailPolishAudit.json')
    unreal.log('OTS_DETAIL_POLISH_AUDIT_SUCCESS '+json.dumps(result['statistics']))
    return result


if __name__=='__main__':
    main()
