"""Create only three private wall/gate meshes; no existing package writes."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelFrontBoundaryCommon import *
from HotelFrontBoundaryGeometry import build_assets
def main():
    assert not (W/'Assets.json').exists()
    inspection=read('Inspection.json');assert inspection['passed'] and native.sha(MAP)==inspection['source_map_sha256']
    baseline=read('ProtectedBefore.json')['file_sha256'];protect(baseline)
    materials=dict(plaster='/Game/CodexGenerated/Hotel/Materials/M_Hotel_Plaster_World_SurfaceDetail',
        brick='/Game/CodexGenerated/Hotel/Materials/MI_Hotel_Enterable_RedBrick_World_75ee78bd',
        concrete='/Game/CodexGenerated/Hotel/Materials/M_Hotel_Concrete_World',
        metal='/Game/CodexGenerated/Hotel/Materials/M_Hotel_PaintedMetal_World',
        rust='/Game/CodexGenerated/Hotel/Materials/M_Hotel_Rust_World')
    meshes=build_assets(ASSET+'/Meshes',materials)
    plan=[dict(label='OTS_Hotel_FrontBoundary_NorthMain',mesh_key='MainWall',position=[8460.,3900.,-3.],yaw=0.,scale=[1.,1.,1.]),
        dict(label='OTS_Hotel_FrontBoundary_NorthWestReturn',mesh_key='SideWall700',position=[6612.,3549.,-3.],yaw=90.,scale=[702./700.,1.,1.]),
        dict(label='OTS_Hotel_FrontBoundary_NorthEastReturn',mesh_key='SideWall600',position=[10320.,3600.,-3.],yaw=90.,scale=[1.,1.,1.])]
    now=files();new={p:h for p,h in now.items() if p not in baseline};assert len(new)==3 and all(Path(p).is_relative_to(NEW) for p in new)
    write('Assets.json',dict(passed=True,source_map_sha256=inspection['source_map_sha256'],meshes=meshes,plan=plan,
        joint=dict(label='OTS_Hotel_FrontBoundary_NorthWestJoint',lo=[6599.,3195.,-3.],hi=[6625.,3205.,279.],material=materials['plaster']),
        new_asset_sha256=new,protection=protect(baseline)))
    unreal.log('HOTEL_FRONT_BOUNDARY_ASSETS_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('AssetsFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
