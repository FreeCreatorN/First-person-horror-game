"""Only create private assets; original map and all existing assets stay read only."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelRevisionCommon import *
from HotelRevisionHandles import create_revised_blueprints
from HotelRevisionFurniture import build_assets

def main():
    assert not (W/'Assets.json').exists()
    source=read('Inspection.json');assert source['passed'] and native.sha(MAP)==source['source_map_sha256']
    before=files();doors=read('Doors.json')
    mapping=create_revised_blueprints(doors['blueprints'],ASSET+'/Blueprints')
    write('BlueprintMapping.json',mapping)
    graph_exports={}
    for old,new in mapping.items():
        p=W/'NewBlueprintNative'/(Path(new).name+'.t3d')
        _,proof=native.native_text_export(unreal.load_asset(new),p);assert proof['passed']
        graph_exports[old]=dict(source_native=doors['blueprints'][old]['native_file'],new_native=str(p))
    write('BlueprintGraphExports.json',graph_exports)
    materials=dict(wood='/Game/CodexGenerated/Hotel/Materials/MI_Hotel_Bedding_Wood_World_4040e9db',
        metal='/Game/CodexGenerated/Hotel/Materials/M_Hotel_DarkMetal_World',
        ceramic='/Game/CodexGenerated/Hotel/Materials/M_Hotel_Ceramic_UV',
        cloth='/Game/CodexGenerated/Hotel/Materials/MI_Hotel_LoadedLaundryRack_Linen_World_bf7dcc6f')
    furniture=build_assets(ASSET+'/Meshes',materials)
    now=files();changed=[p for p,h in before.items() if now.get(p)!=h]
    # New stage only; original map must not have been saved concurrently.
    assert not changed,changed
    new={p:h for p,h in now.items() if p not in before}
    assert new and all(Path(p).is_relative_to(NEW) for p in new),list(new)
    assert native.sha(MAP)==source['source_map_sha256']
    write('Assets.json',dict(passed=True,source_map_sha256=source['source_map_sha256'],blueprints=mapping,furniture=furniture,new_asset_sha256=new,existing_files_unchanged=True))
    unreal.log('HOTEL_REVISION_ASSETS_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('AssetFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
