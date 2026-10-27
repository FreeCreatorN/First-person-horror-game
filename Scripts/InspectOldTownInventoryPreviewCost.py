"""Read render-target and preview Blueprint settings; never change performance."""
import sys,json,re
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from OldTownMainLightingCommon import sha,read,write,ref
from CreateOldTownVersion2 import W,V2,MAP,V2FILE,MAIN
def main():
    maps={str(p):sha(p) for p in (MAP,V2FILE,MAIN)};i=read(W/'Input.json')
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert le.load_level(V2)
    ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a=next(a for a in ae.get_all_level_actors() if a.get_actor_label()=='BP_InventoryCharacterPreview')
    c=a.get_component_by_class(unreal.SceneCaptureComponent2D);assert c
    rt=c.get_editor_property('texture_target');assert rt
    rtfile=native.asset_file(rt);bpfile=native.asset_file(a.get_class().class_generated_by()) if hasattr(a.get_class(),'class_generated_by') else None
    capture=native.props(c,['capture_every_frame','capture_on_movement','primitive_render_mode','capture_source',
        'show_only_actors','hidden_actors','max_view_distance_override','lod_distance_factor','always_persist_rendering_state','texture_target'])
    target=native.props(rt,['size_x','size_y','render_target_format','force_linear_gamma','auto_generate_mips','target_gamma','override_format'])
    bp_path=i['actors']['BP_InventoryCharacterPreview']['class'].split('.')[0]
    bp=unreal.load_asset(bp_path);assert bp
    text,export=native.native_text_export(bp,W/'PreviewBlueprintReadOnly.t3d')
    function_mentions={name:len(re.findall(r'\b'+name+r'\b',text)) for name in
        ('CaptureScene','SetCaptureEveryFrame','SetCaptureOnMovement','SetVisibility','ReceiveTick','ReceiveBeginPlay')}
    report=dict(passed=True,source='read only saved V2 editor state and native Blueprint text; no gameplay capture',
        map_sha256=maps[str(V2FILE)],capture_component=capture,render_target=target,
        render_target_file=dict(file=str(rtfile),sha256=sha(rtfile)),blueprint=export,blueprint_function_name_mentions=function_mentions,
        runtime_inventory_closed_capture_status='Not measured; saved capture_every_frame alone does not prove runtime behavior.',
        no_performance_changes_applied=True,map_save_requested=False)
    assert all(sha(p)==h for p,h in maps.items())
    assert all(sha(p)==h for p,h in {**i['all_original_generated_file_sha256'],
        **{p:h for p,h in i['referenced_game_package_sha256'].items() if Path(p).suffix!='.umap'}}.items())
    write(W/'InventoryPreviewReadOnly.json',report)
    unreal.log('INVENTORY_PREVIEW_COST_READONLY_PASS '+json.dumps(dict(render_target=target,function_mentions=function_mentions),ensure_ascii=False))
if __name__=='__main__':main()
