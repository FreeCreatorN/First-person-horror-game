"""Targeted curb-side lamps, connected utilities and readable guesthouse signs."""
import json
import math
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,shared_asset_hashes,sha,xyz
from OldTownAssetRelocation import normalize_paths
WORK=ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'
BASE=ROOT/'Saved/CodexOutputs/OpeningRelocation_20261007'
SOURCE=ROOT/'SourceArt/OldTownStreetRefinement_20261007'
ASSETS='/Game/CodexGenerated/OldTown/StreetRefinement_20261007'
TAG='StreetRefinement_20261007'
LIT=(1,2,4,5,6,7,8,9)
LIGHT_FIELDS=('intensity','intensity_units','attenuation_radius','inner_cone_angle','outer_cone_angle',
    'use_temperature','temperature','light_color','indirect_lighting_intensity','volumetric_scattering_intensity',
    'use_inverse_squared_falloff','cast_shadows')

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def light_values(c):
    v={k:c.get_editor_property(k) for k in LIGHT_FIELDS}
    v['intensity_units']=str(v['intensity_units']);color=v['light_color']
    v['light_color']=[int(getattr(color,k)) for k in ('r','g','b','a')]
    return v
def wire_ends(a):
    c=a.get_component_by_class(unreal.StaticMeshComponent);b=c.static_mesh.get_bounds();t=c.get_world_transform()
    return sorted([xyz(t.transform_location(unreal.Vector(b.origin.x+s*b.box_extent.x,b.origin.y,b.origin.z))) for s in (-1,1)],key=lambda v:v[0])

def sign_material(row):
    texture_path=ASSETS+'/Textures/'+Path(row['filename']).stem
    source=SOURCE/row['filename'];assert sha(source)==row['png_sha256']
    library=unreal.EditorAssetLibrary
    if library.does_asset_exist(texture_path):
        texture=unreal.load_asset(texture_path)
        if not library.get_metadata_tag(texture,TAG+'_SourceSHA256'):
            # Resume our first import, which was saved before the unattended
            # Interchange browser notification failed. Match its source first.
            imported=[Path(p).resolve() for p in texture.get_editor_property('asset_import_data').extract_filenames()]
            assert imported==[source.resolve()],imported
            library.set_metadata_tag(texture,TAG+'_SourceSHA256',row['png_sha256'])
            library.set_metadata_tag(texture,TAG+'_Text',row['text'])
            assert library.save_loaded_asset(texture,False)
        assert library.get_metadata_tag(texture,TAG+'_SourceSHA256')==row['png_sha256']
    else:
        task=unreal.AssetImportTask()
        for k,v in dict(filename=str(source),destination_path=ASSETS+'/Textures',destination_name=Path(row['filename']).stem,
                        automated=True,replace_existing=False,save=False).items():task.set_editor_property(k,v)
        task.set_editor_property('factory',unreal.TextureFactory())
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture=unreal.load_asset(texture_path);assert isinstance(texture,unreal.Texture2D)
        texture.set_editor_property('srgb',True)
        texture.set_editor_property('address_x',unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
        library.set_metadata_tag(texture,TAG+'_SourceSHA256',row['png_sha256'])
        library.set_metadata_tag(texture,TAG+'_Text',row['text'])
        assert library.save_loaded_asset(texture,False)
    material_path=ASSETS+'/Materials/M_OTS_Refinement_'+row['key']
    if library.does_asset_exist(material_path):
        material=unreal.load_asset(material_path)
        assert library.get_metadata_tag(material,TAG+'_Owned')=='true'
    else:
        material=unreal.AssetToolsHelpers.get_asset_tools().create_asset(material_path.rsplit('/',1)[1],ASSETS+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        material.set_editor_property('two_sided',True)
        editing=unreal.MaterialEditingLibrary
        node=editing.create_material_expression(material,unreal.MaterialExpressionTextureSample,-300,0)
        node.set_editor_property('texture',texture)
        uv=editing.create_material_expression(material,unreal.MaterialExpressionTextureCoordinate,-750,0)
        uv.set_editor_property('v_tiling',-1.)
        offset=editing.create_material_expression(material,unreal.MaterialExpressionConstant2Vector,-750,150)
        offset.set_editor_property('r',0.);offset.set_editor_property('g',1.)
        add=editing.create_material_expression(material,unreal.MaterialExpressionAdd,-500,0)
        assert editing.connect_material_expressions(uv,'',add,'A')
        assert editing.connect_material_expressions(offset,'',add,'B')
        assert editing.connect_material_expressions(add,'',node,'')
        assert editing.connect_material_property(node,'RGB',unreal.MaterialProperty.MP_BASE_COLOR)
        rough=editing.create_material_expression(material,unreal.MaterialExpressionConstant,-300,150);rough.set_editor_property('r',.96)
        assert editing.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
        editing.recompile_material(material)
        library.set_metadata_tag(material,TAG+'_Owned','true')
        library.set_metadata_tag(material,TAG+'_UVVFlipped','true')
        assert library.save_loaded_asset(material,False)
    return material,texture

def main():
    WORK.mkdir(exist_ok=True)
    assert not (WORK/'Applied.json').exists(),'Already applied; run the fresh-load audit.'
    probe=os.environ.get('OTS_STREET_REFINEMENT_PROBE_ONLY')=='1'
    build=read(BASE/'BuildReport.json');target=build['target_level']
    mapfile=ROOT/('Content/'+target.removeprefix('/Game/')+'.umap');source_hash=sha(mapfile)
    inspection=read(WORK/'Inspection.json');assert inspection['map_sha256']==source_hash,'Reinspect newly saved user changes.'
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert level.load_level(target)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors())
    by={a.get_actor_label():a for a in actors};assert len(by)==len(actors)==inspection['actor_count']
    before={n:actor_state(a) for n,a in by.items()};hashes=shared_asset_hashes(actors)
    backup=WORK/'Before';backup.mkdir(exist_ok=True)
    for f in (mapfile,BASE/'BuildReport.json',ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'):
        if not (backup/f.name).exists():shutil.copy2(f,backup/f.name)
    old=normalize_paths(read(BASE/'ActorSnapshots.json')[target],build['asset_relocations'])
    external=[n for n in set(before)|set(old) if before.get(n)!=old.get(n)]
    write('InputRebaseReport.json',dict(passed=True,previous_map_sha256=build['map_sha256'],source_map_sha256=source_hash,
        external_actor_changes=sorted(external),all_current_user_changes_preserved=True))
    protected={p:sha(Path(p)) for p in build['protected_map_sha256']}
    spec=dict(lamp_moves=[],directional_lights=[],pole_moves=[],wire_adjustments=[],new_signs=[],route_specs=[],
        allowed_changed_labels=[],new_actor_labels=[],source_map_sha256=source_hash,
        policy='Lamp bases in curb-side service band; retain roads, sidewalks, open alleys and current user edits.')
    changed=set();added=set()
    for i in range(1,10):
        n='OTS_P2Prop_StreetLamp_%02d'%i;a=by[n];oldpos=xyz(a.get_actor_location());pos=list(oldpos)
        if i<8:pos[1]=385. if oldpos[1]>0 else -385.
        else:pos[0]=8285.
        delta=[pos[j]-oldpos[j] for j in range(3)]
        a.set_actor_location(unreal.Vector(*pos),False,False);changed.add(n)
        axis=1 if i<8 else 0;facade=(530. if pos[1]>0 else -530.) if i<8 else 9000.
        edge=(350. if pos[1]>0 else -350.) if i<8 else 8250.
        spec['lamp_moves'].append(dict(actor=n,before_position_cm=oldpos,position_cm=pos,base_radius_cm=14.56,
            facade_plane_axis=axis,facade_plane_cm=facade,road_edge_axis=axis,road_edge_cm=edge,
            walk_route=[[pos[0]-100,450. if pos[1]>0 else -450.,11],[pos[0]+100,450. if pos[1]>0 else -450.,11]] if i<8 else [[8350,pos[1]-100,11],[8350,pos[1]+100,11]]))
        if i not in LIT:continue
        label='OTS_Light_StreetLamp%02d'%i;light=by[label];c=light.get_component_by_class(unreal.SpotLightComponent)
        assert c and c.get_class().get_name()=='SpotLightComponent'
        values=light_values(c);lp=[xyz(light.get_actor_location())[j]+delta[j] for j in range(3)]
        light.set_actor_location(unreal.Vector(*lp),False,False);changed.add(label)
        assert light_values(c)==values
        spec['directional_lights'].append(dict(actor=label,position_cm=lp,intensity_lm=values['intensity'],
            attenuation_radius_cm=values['attenuation_radius'],inner_cone_angle=values['inner_cone_angle'],outer_cone_angle=values['outer_cone_angle'],before_physical_values=values))
    # Keep the complete pole, insulators and wire terminals connected as its
    # base joins the same service band. Opposite wire endpoints remain fixed.
    for n,a in sorted(by.items()):
        if not n.startswith('OTS_UtilityPole_02_'):continue
        oldpos=xyz(a.get_actor_location());pos=[oldpos[0],oldpos[1]+115,oldpos[2]]
        a.set_actor_location(unreal.Vector(*pos),False,False);changed.add(n)
        spec['pole_moves'].append(dict(actor=n,before_position_cm=oldpos,position_cm=pos))
    for suffix in (3,6,9):
        n='OTS_OverheadWire_%02d'%suffix;a=by[n];ends=wire_ends(a);expected=deepcopy(ends)
        assert abs(expected[1][1]+500)<.01
        expected[1][1]+=115
        c=a.get_component_by_class(unreal.StaticMeshComponent);extent=c.static_mesh.get_bounds().box_extent.x
        a.set_actor_location(unreal.Vector(*[(expected[0][j]+expected[1][j])/2 for j in range(3)]),False,False)
        a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*expected[0]),unreal.Vector(*expected[1])),False)
        scale=a.get_actor_scale3d();a.set_actor_scale3d(unreal.Vector(math.dist(*expected)/(2*extent),scale.y,scale.z));changed.add(n)
        assert all(math.dist(x,y)<.03 for x,y in zip(wire_ends(a),expected))
        spec['wire_adjustments'].append(dict(actor=n,endpoints_cm=expected,fixed_first_endpoint_before=ends[0],before_endpoints_cm=ends))
    plane=unreal.load_asset('/Engine/BasicShapes/Plane');assert plane
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.PNG 0')
    for row in read(SOURCE/'SignManifest.json')['signs']:
        material,texture=sign_material(row)
        # The stock plane uses U along local X and top edge along local Y.
        # Two-sided matte paper is readable from its corridor-facing side.
        right=unreal.Vector(*row['text_right_world']);up=unreal.Vector(*row['text_up_world'])
        normal=unreal.MathLibrary.cross_vector_vector(right,up)
        rotation=unreal.MathLibrary.make_rotation_from_axes(right,up,normal)
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*row['world_position_cm']),rotation,False)
        n='OTS_Refinement_Sign_'+row['key'];a.set_actor_label(n);a.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/RefinementSigns'))
        a.set_editor_property('tags',[unreal.Name(TAG)])
        a.set_actor_scale3d(unreal.Vector(row['size_cm'][0]/100,row['size_cm'][1]/100,1))
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(plane);c.set_material(0,material)
        c.set_collision_profile_name('NoCollision');c.set_editor_property('cast_shadow',False)
        added.add(n);by[n]=a
        spec['new_signs'].append(dict(actor=n,text=row['text'],position_cm=row['world_position_cm'],size_cm=row['size_cm'],
            normal_world=xyz(normal),read_from_direction=row['normal_world'],rotation=[rotation.pitch,rotation.yaw,rotation.roll],asset=plane.get_path_name(),
            material_asset=material.get_path_name(),texture_asset=texture.get_path_name(),source_file=row['filename'],source_sha256=row['png_sha256']))
        spec['new_signs'][-1]['text_metadata_key']=TAG+'_Text'
    legacy=read(ROOT/'Saved/CodexOutputs/StreetAccessLighting_20261005/BuildReport.json')['street_access_lighting']
    for side,y in [('South',-450.),('North',450.)]:spec['route_specs'].append(dict(id='ContinuousMainWalk'+side,points=[[150,y,11],[7500,y,11]]))
    spec['route_specs'].append(dict(id='ContinuousEastWalk',points=[[8350,-2030,11],[8350,2030,11]]))
    for r in legacy['reopened_gaps']:spec['route_specs'].append(dict(id=r['name'],points=r['route_points_cm']))
    for r in legacy['door_approaches']:spec['route_specs'].append(dict(id=r['name'],points=r['route_points_cm']))
    for r in spec['lamp_moves']:spec['route_specs'].append(dict(id='WalkPast_'+r['actor'],points=r['walk_route']))
    cameras=[('CAM_Refinement_CurbWalk',[3100,20,190],[3500,440,185],78,'temporary'),
        ('CAM_Refinement_StreetNight',[1350,0,175],[3580,0,190],80,'street_only'),
        ('CAM_Refinement_Gallery',[9110,320,560],[9196,325,585],78,'temporary'),
        ('CAM_Refinement_Lift',[9380,240,535],[9591,235,530],65,'temporary'),
        ('CAM_Refinement_Linen',[9110,2440,170],[9196,2490,180],80,'temporary')]
    spec['review_cameras']=[]
    for n,pos,look,fov,mode in cameras:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*look))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*pos),rot,False);a.set_actor_label(n)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/Refinement/ReviewCameras'));a.set_editor_property('tags',[unreal.Name(TAG)])
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
        added.add(n);spec['review_cameras'].append(dict(camera=n,lighting_mode=mode))
    current=list(sub.get_all_level_actors());expected={a.get_actor_label():actor_state(a) for a in current}
    assert set(expected)-set(before)==added and not set(before)-set(expected)
    assert all(expected[n]==s for n,s in before.items() if n not in changed)
    assert all(sha(Path(p))==h for p,h in hashes.items()) and sha(mapfile)==source_hash
    spec['allowed_changed_labels']=sorted(changed);spec['new_actor_labels']=sorted(added)
    build.update(source_map_sha256=source_hash,map_sha256=source_hash,actor_count=len(current),protected_map_sha256=protected,
        street_refinement=spec,previous_evidence=str(BASE/'FinalReview.json'))
    build['new_asset_sha256']={str(p):sha(p) for p in (ROOT/('Content/'+ASSETS.removeprefix('/Game/'))).rglob('*.uasset')}
    for p in (build['hotel_architecture'],build['hotel_operations']):p['new_actor_labels']=sorted(set(p['new_actor_labels'])|added)
    build['hotel_openings_review_cameras']+= [r['camera'] for r in spec['review_cameras']]
    write('PreservationBaseline.json',dict(actors=before,expected_actors=expected,shared_asset_sha256=hashes,
        source_map_sha256=source_hash,allowed_changed_labels=sorted(changed),new_actor_labels=sorted(added)))
    write('PendingBuildReport.json',build)
    if probe:
        from AuditOldTownStreetRefinement import audit,operations
        operations.refresh(current)
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        result=audit(world,current,build,read(WORK/'PreservationBaseline.json'));write('ProbeAudit.json',result);assert result['passed'],result['errors'][:15]
        assert sha(mapfile)==source_hash
        write('ProbeSummary.json',dict(passed=True,source_map_sha256=source_hash,proposed_changes=spec,statistics=result['statistics']))
        unreal.log('STREET_REFINEMENT_PROBE_PASS '+str(result['statistics']));return
    approved=read(WORK/'ProbeSummary.json');assert approved['passed'] and approved['source_map_sha256']==source_hash
    assert approved['proposed_changes']==spec,'Proposal differs from successful physical probe.'
    assert unreal.EditorLoadingAndSavingUtils.save_current_level()
    build['map_sha256']=sha(mapfile);write('BuildReport.json',build)
    write('Applied.json',dict(passed=True,map_sha256=build['map_sha256'],changed=len(changed),added=len(added)))
    unreal.log('STREET_REFINEMENT_SAVED changed='+str(len(changed))+' added='+str(len(added)))

if __name__=='__main__':main()
