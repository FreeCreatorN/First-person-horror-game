"""Read-only saved-world geometry and user-state baseline for surface repair."""
import json, sys, traceback,os
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from ValidateEnterableStreet import validate_main_home
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
STAGE=os.environ.get('OTS_SURFACE_INSPECT_STAGE','Input')

def geometry_xyz(value):
    """Keep native coordinates through both local and world render export.

    Actor-state snapshots retain their existing serialization. Rounding render
    vertices to four decimal places can collapse distinct float32 mesh vertices
    before the world transform and hide narrow, otherwise valid triangles.
    """
    return [float(getattr(value, axis)) for axis in ('x', 'y', 'z')]
def write(name,value):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/name).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
def main():
    digest=sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    previous=json.loads((ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json').read_text(encoding='utf-8-sig'))
    states={a.get_actor_label():actor_state(a) for a in actors}
    write(STAGE+'Snapshot.json',dict(passed=True,target_level=TARGET,source_map_sha256=digest,actors=states,actor_count=len(actors),
        shared_asset_sha256=shared_asset_hashes(actors),main_home=validate_main_home(actors),
        protected_map_sha256={p:sha(Path(p)) for p in previous['protected_map_sha256']}))
    # Export actual render LOD0 vertices, not bounding-box guesses.
    cache={};records=[];errors=[];hidden=0
    expected_offsets={}
    if STAGE!='Input':
        build=json.loads((WORK/'BuildReport.json').read_text(encoding='utf-8-sig'))
        expected_offsets={r['id']:r['offset_cm'] for r in build['surface_repair']['material_overrides']}
    for a in actors:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            mesh=c.static_mesh
            if not mesh:continue
            if not c.get_editor_property('visible') or c.get_editor_property('hidden_in_game'):
                hidden+=1;continue
            path=mesh.get_path_name()
            try:
                if path not in cache:
                    vertices=[];triangles=[];sign_sum=0
                    for section in range(mesh.get_num_sections(0)):
                        data=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh,0,section)
                        vs,ts,ns=data[0],data[1],data[2];offset=len(vertices)
                        for i in range(0,len(ts),3):
                            va,vb,vc=[vs[int(ts[i+j])] for j in range(3)]
                            dot=unreal.MathLibrary.dot_vector_vector(unreal.MathLibrary.cross_vector_vector(vb-va,vc-va),ns[int(ts[i])]+ns[int(ts[i+1])]+ns[int(ts[i+2])])
                            if abs(dot)>1e-6:sign_sum+=1 if dot>0 else -1
                        vertices.extend([geometry_xyz(v) for v in vs])
                        triangles.extend([[offset+int(ts[i+j]) for j in range(3)] for i in range(0,len(ts),3)])
                    assert vertices and triangles,path
                    cache[path]=(vertices,triangles,sign_sum<0)
                vs,ts,reverse=cache[path];transform=c.get_world_transform()
                identifier=a.get_actor_label()+'::'+c.get_name()
                render_offset=[0.,0.,0.]
                if identifier in expected_offsets:
                    from OldTownSurfaceMaterials import PARAMETER
                    assert c.get_editor_property('evaluate_world_position_offset')
                    assert c.get_editor_property('world_position_offset_disable_distance')==0
                    for i in range(c.get_num_materials()):
                        material=c.get_material(i);assert isinstance(material,unreal.MaterialInstanceConstant)
                        value=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material,unreal.Name(PARAMETER))
                        actual=[float(value.r),float(value.g),float(value.b)]
                        assert max(abs(v-t) for v,t in zip(actual,expected_offsets[identifier]))<1e-5
                        render_offset=actual
                scale=c.get_world_scale();negative=scale.x*scale.y*scale.z<0
                world_vertices=[geometry_xyz(unreal.MathLibrary.transform_location(transform,unreal.Vector(*v))) for v in vs]
                world_vertices=[[v[i]+render_offset[i] for i in range(3)] for v in world_vertices]
                records.append(dict(id=a.get_actor_label()+'::'+c.get_name(),actor=a.get_actor_label(),component=c.get_name(),mesh=path,
                    vertices=world_vertices,triangles=ts,render_offset_cm=render_offset,wpo_verified_from_persisted_material=identifier in expected_offsets,
                    reverse_winding=reverse ^ negative,world_transform_negative_determinant=negative,
                    collision=str(c.get_collision_enabled()),materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]))
            except Exception as exc:errors.append(dict(actor=a.get_actor_label(),component=c.get_name(),mesh=path,error=str(exc)))
    write('Geometry'+STAGE+'.json',dict(map_sha256=digest,components=records,hidden_components_excluded=hidden,errors=errors,unique_meshes=len(cache),
        coordinate_serialization='unrounded native local positions and unrounded native transformed world positions, plus verified material WPO',
        triangles=sum(len(r['triangles']) for r in records)))
    assert sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==digest
    write(STAGE+'Summary.json',dict(passed=not errors,map_sha256=digest,actors=len(actors),visible_components=len(records),unique_meshes=len(cache),
        hidden_components_excluded=hidden,errors=errors,triangles=sum(len(r['triangles']) for r in records)))
    unreal.log('SURFACE_INPUT_PASS '+str(dict(components=len(records),errors=len(errors),meshes=len(cache))))
if __name__=='__main__':
    try:main()
    except Exception:
        write('InputFailure.json',dict(traceback=traceback.format_exc()));raise
