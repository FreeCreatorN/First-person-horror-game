"""Fresh complete baseline and localized scene inventory, never saves packages."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelFrontBoundaryCommon import *
def main():
    assert not (W/'Inspection.json').exists()
    baseline=files();write('ProtectedBefore.json',dict(file_sha256=baseline))
    le,ae,world,actors,by=load()
    selected=[]
    for a in actors:
        p=a.get_actor_location()
        if (5500<p.x<10900 and (2700<abs(p.y)<4600)) or 'Ground' in a.get_actor_label():
            comps=[]
            for c in a.get_components_by_class(unreal.PrimitiveComponent):
                o,e,_=unreal.SystemLibrary.get_component_bounds(c)
                d=dict(name=c.get_name(),location=native.value(c.get_world_location()),bounds=[[getattr(o,k)-getattr(e,k) for k in ('x','y','z')],[getattr(o,k)+getattr(e,k) for k in ('x','y','z')]],
                    visible=bool(c.get_editor_property('visible')),collision=str(c.get_collision_enabled()))
                if isinstance(c,unreal.StaticMeshComponent):d.update(mesh=native.path_of(c.static_mesh),materials=[native.path_of(c.get_material(i)) for i in range(c.get_num_materials())])
                comps.append(d)
            selected.append(dict(label=a.get_actor_label(),name=a.get_name(),class_path=a.get_class().get_path_name(),tags=[str(t) for t in a.tags],location=native.value(p),components=comps))
    write('LocalScene.json',dict(source_map_sha256=baseline[str(MAP)],actors=selected))
    write('BeforeScene.json',snap(actors,'BeforeScreen',world))
    assert native.sha(MAP)==baseline[str(MAP)]
    write('Inspection.json',dict(passed=True,source_map_sha256=baseline[str(MAP)],actor_count=len(actors),protection=protect(baseline),no_save=True))
    unreal.log('HOTEL_FRONT_BOUNDARY_INSPECT_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('InspectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
