"""Record the eight actual frames directly inspected by the root reviewer."""
from OldTownMainLightingCommon import R,read,write,sha,ref
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016'
NOTES={
 'CAM_StreetAccess_NightStreet':'Saved user night environment retained. Warm single-direction street lenses emit, poles/housings stay dark; pools illuminate sidewalk and street. Dark middle-distance facade detail is not visually assessed.',
 'CAM_V4_Exterior':'Saved hotel exterior is very dark, with cyan room windows. Copy preservation is verified by fresh native state; this actual-light image cannot validate facade detail.',
 'CAM_StreetAccess_Lamp':'Only underside diffuser emits warm light. Hood, arm and pole remain nonemissive; bolts and lens are physically seated.',
 'CAM_V4_TopGallery':'Two cool tube bodies emit; green fixture body and tube end seats remain dark. Ceiling/wall shows original damp texture.',
 'CAM_V4_LobbyWide':'Actual saved lobby view is nearly black apart from a remote light. No detail or walkability claim is made from this frame; user lighting is preserved.',
 'CAM_V4_GuestTwin':'Actual saved guestroom is nearly black with a visible night window. Furniture is assessed in the separate temporary inspection closeup.',
 'CAM_V4_UpperCore':'Temporary inspection fill: pillow contacts mattress, folds and piping are visible, wood/headboard and ground support remain aligned. Linen remains rather shiny under inspection fill.',
 'CAM_V4_CentralStair':'Temporary inspection fill: checked fabric, cushion depressions, casing seams and supporting frame remain aligned. Dark crease shadows are recorded; closed-surface/source proof is separate.'}
def main():
    setup=read(W/'CaptureSetup.json');digest=setup['map_sha256'];rows=[];images={}
    for folder,names in [('Captures',setup['actual_cameras']),('ModelCaptures',setup['model_cameras'])]:
        runs=read(W/folder/'CaptureRuns.json');assert len(runs)==len(names)
        for name in names:
            run=next(r for r in runs if r['camera']==name)
            assert run['captured'] and run['normal_exit'] and run['exit_code']==0 and not run['forced_cleanup']
            path=W/folder/'Renders'/(name+'.png');meta=read(path.with_suffix('.json'))
            assert meta['map_sha256']==digest and meta['png_sha256']==sha(path)
            images[str(path)]=sha(path)
            rows.append(dict(file=str(path),png_sha256=sha(path),directly_viewed=True,observations=NOTES[name]))
    assert len(rows)==8
    write(W/'VisualReview.json',dict(passed=True,map_sha256=digest,image_sha256=images,root_reviewed_frames=rows,
        scope='Current V2 copy, saved user lighting and temporary geometry inspection; no runtime-performance or full photorealism claim.',
        limitations=['Actual saved lobby, guestroom and hotel facade are very dark; their detail is checked through preserved native state and inspection lighting, not claimed visible in those actual-light frames.',
            'Inspection lights and camera overrides are transient, removed after capture and never saved.',
            'Linen specular response and broad facade material variation remain future artistic improvements for V2.',
            'No runtime playthrough, frame-time benchmark, texture residency or closed-inventory capture frequency was measured.',
            'V2 is a map copy with frozen shared dependencies; future asset edits require private V2 replacements.']))
    print('V2_EIGHT_DIRECTLY_VIEWED_FRAMES_RECORDED')
if __name__=='__main__':main()
