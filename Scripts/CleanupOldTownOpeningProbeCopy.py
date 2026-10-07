"""Remove an unreferenced original probe copy left by UE's asset rename."""
import json
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from InspectOldTownOpeningRelocation import WORK,OLD,NEW,write,template_state,package_file
from PolishOldTownHotel import sha
inventory=json.loads((WORK/'Inventory.json').read_text(encoding='utf-8-sig'))
assert (WORK/'Moved.json').exists()
row=next(r for r in inventory['assets'] if r['old'].endswith('/BP_OpeningProbe'))
old=row['old'];new=row['new']
registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True)
options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
 include_searchable_names=True,include_soft_management_references=True,include_hard_management_references=True)
refs=list(registry.get_referencers(unreal.Name(old),options) or []);assert not refs,refs
original=unreal.load_asset(old);destination=unreal.load_asset(new)
assert isinstance(original,unreal.Blueprint) and isinstance(destination,unreal.Blueprint)
assert original.get_path_name().split('.')[0]==old and destination.get_path_name().split('.')[0]==new
assert template_state(original)==template_state(destination)==row['templates']
old_class=unreal.EditorAssetLibrary.load_blueprint_class(old);new_class=unreal.EditorAssetLibrary.load_blueprint_class(new)
assert old_class.get_path_name().startswith(old+'.') and new_class.get_path_name().startswith(new+'.')
relative=str(package_file(old).relative_to(ROOT/'Content')).replace('\\','/')
assert sha(package_file(old))==inventory['content_sha256'][relative]
assert unreal.EditorAssetLibrary.delete_asset(old)
assert not (ROOT/('Content/'+old.removeprefix('/Game/')+'.uasset')).exists()
assert unreal.EditorAssetLibrary.does_asset_exist(new)
write('ProbeCopyCleanup.json',dict(passed=True,removed_unused_original=old,retained_destination=new,referencers=0))
unreal.log('OPENING_RELOCATION_UNUSED_PROBE_COPY_CLEANUP_PASS')
