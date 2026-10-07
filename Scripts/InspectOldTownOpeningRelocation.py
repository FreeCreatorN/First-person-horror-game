"""Inventory and back up only the generated opening assets and their referencers."""
import json
import shutil
import sys
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from BuildOldTownOpeningBlueprints import _templates
OLD='/Game/Yastar/Blueprints/OldTownOpenings_20261004'
NEW='/Game/CodexGenerated/OldTown/Blueprints/Openings'
WORK=ROOT/'Saved/CodexOutputs/OpeningRelocation_20261007'


def write(name,data):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def package_file(package):
    q=ROOT/('Content/'+package.removeprefix('/Game/'))
    for ext in ('.uasset','.umap'):
        f=q.with_suffix(ext)
        if f.exists():return f
    raise AssertionError(package)


def template_state(bp):
    sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    result={}
    for name,(_,c) in _templates(sub,bp).items():
        rot=c.get_editor_property('relative_rotation')
        row=dict(class_path=c.get_class().get_path_name(),location=xyz(c.get_editor_property('relative_location')),
                 rotation=[round(float(getattr(rot,k)),4) for k in ('pitch','yaw','roll')],
                 scale=xyz(c.get_editor_property('relative_scale3d')),mobility=str(c.get_editor_property('mobility')))
        if isinstance(c,unreal.StaticMeshComponent):
            row.update(mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
                       materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())])
        if isinstance(c,unreal.PrimitiveComponent):
            row.update(collision=str(c.get_collision_enabled()),profile=str(c.get_collision_profile_name()),
                       visible=bool(c.get_editor_property('visible')),hidden=bool(c.get_editor_property('hidden_in_game')))
        result[name]=row
    return result


def main():
    assert not (WORK/'Inventory.json').exists(),'Inventory exists; preserve original pre-move snapshots.'
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
        include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
    packages=sorted({p.split('.')[0] for p in unreal.EditorAssetLibrary.list_assets(OLD,True,False)})
    assert len(packages)==11,packages
    assert not unreal.EditorAssetLibrary.list_assets(NEW,True,False),'Destination must be new and empty.'
    before=WORK/'BeforeContent';before.mkdir(parents=True,exist_ok=True)
    assets=[];refs=set()
    for p in packages:
        bp=unreal.load_asset(p);assert isinstance(bp,unreal.Blueprint),p
        referencers=sorted(str(r) for r in registry.get_referencers(unreal.Name(p),options))
        refs.update(referencers)
        assets.append(dict(old=p,new=NEW+'/'+p.rsplit('/',1)[1],referencers=referencers,templates=template_state(bp)))
    refs-=set(packages)
    assert all(p.startswith('/Game/') for p in refs),refs
    files={p:package_file(p) for p in packages+sorted(refs)}
    for p,f in files.items():
        target=before/f.relative_to(ROOT/'Content');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    maps=[p for p in sorted(refs) if files[p].suffix=='.umap']
    other=[p for p in sorted(refs) if p not in maps]
    snapshots={}
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for p in maps:
        assert level.load_level(p),p
        actors=list(sub.get_all_level_actors())
        snapshots[p]={a.get_actor_label():actor_state(a) for a in actors}
        assert len(snapshots[p])==len(actors)
    write('ActorSnapshots.json',snapshots)
    all_hashes={str(f.relative_to(ROOT/'Content')).replace('\\','/'):sha(f) for f in (ROOT/'Content').rglob('*') if f.is_file()}
    report=dict(old_folder=OLD,new_folder=NEW,assets=assets,referencer_maps=maps,other_referencers=other,
                content_sha256=all_hashes,map_counts={p:len(s) for p,s in snapshots.items()},
                source_map_sha256={p:sha(files[p]) for p in maps})
    write('Inventory.json',report)
    unreal.log('OPENING_RELOCATION_INVENTORY_PASS '+str(dict(assets=len(assets),maps=report['map_counts'],other=other)))


if __name__=='__main__':main()
