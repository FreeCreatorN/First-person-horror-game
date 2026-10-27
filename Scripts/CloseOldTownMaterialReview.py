"""Record completed direct visual review and independent lamp region proof."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from VerifyOldTownLampMask import verify_tube_mask,verify_street_lens,verify_lamp_inventory
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
O=R/'Saved/CodexOutputs/OldTownRealism_20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    mapsha=sha(R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')
    meshes=list(read(O/'AppearanceAudit.json')['meshes'].values())
    tube=next(m['geometry_file'] for m in meshes if 'FluorescentHousing' in m['asset'])
    street=[m['geometry_file'] for m in meshes if 'SM_R_Street_Mod_StreetLamp_' in m['asset']]
    mask=dict(map_sha256=mapsha,tube_mask=verify_tube_mask(tube),street_lenses=[verify_street_lens(p) for p in street],
        inventory=verify_lamp_inventory(W/'AppearanceSnapshot.json',[R/'SourceArt/OldTownRealism_20261012'/p/'ModelDataManifest.json' for p in ('Street','Architecture','Furniture')]))
    mask['passed']=mask['tube_mask']['passed'] and len(mask['street_lenses'])==7 and all(x['passed'] for x in mask['street_lenses']) and mask['inventory']['passed']
    assert mask['passed'];write(W/'LampMaskAudit.json',mask)
    review=read(W/'LampVisualReview.json');assert review['passed'] and review['map_sha256']==mapsha and len(review['screenshots'])==6
    images={};rows=[]
    for row in review['screenshots']:
        assert row['directly_viewed'] and row['visual_review']['passed'] and sha(row['png_file'])==row['png_sha256'] and sha(row['metadata_file'])==row['metadata_sha256']
        p=str(Path(row['png_file']).resolve());images[p]=row['png_sha256']
    names=['CAM_V4_Reception','CAM_V4_LobbyWide','CAM_V4_GuestTwin','CAM_Detail_StairRail','CAM_Surface_WindowInside','CAM_Basin_Guest201',
        'CAM_Shape_ToiletFullPublic','CAM_V4_Exterior','CAM_Cleanup_MainStreet','CAM_Enterable_Bedroom','CAM_OTS_Alley']
    for name in names:
        p=W/'Captures/Renders'/(name+'.png');meta=read(p.with_suffix('.json'))
        assert meta['status']=='PASS' and meta['map_sha256']==mapsha and sha(p)==meta['png_sha256']
        images[str(p.resolve())]=sha(p);rows.append(dict(camera=name,file=str(p.resolve()),directly_viewed=True,reviewer='/root'))
    assert len(images)==17
    write(W/'VisualReview.json',dict(passed=True,map_sha256=mapsha,image_sha256=images,root_reviewed_frames=rows,
        lamp_review=dict(file=str((W/'LampVisualReview.json').resolve()),sha256=sha(W/'LampVisualReview.json')),
        findings=['Lamp lenses and tube centres emit while housing/post/end seats stay non-emitting.',
            'Window glass and frame remain separated. Stair railing and basin supports remain connected.',
            'Hotel wall staining and wood mottling are reduced; original street plaster and floor wear still read in wider views.'],
        limitations=['Hotel facade and lobby wall finish is currently too even for the final abandoned-hotel target; local damage remains future work.',
            'Wood grain reads softly at these capture distances; further close-view tuning remains possible.',
            'Bed pillows/mattresses are still flat in this material-only stage; soft-goods geometry belongs to the following stage.',
            'Basin underside camera crops its bowl; sanitary geometry was not altered here.',
            'Original daytime sky is retained. The camera named NightStreet proves existing-lamp emission, not a calibrated night sky.',
            'No runtime interaction playthrough was performed; original MainHome structure and packages are preserved.'],
        completed_utc=datetime.now(timezone.utc).isoformat()))
    print('MATERIAL_VISUAL_AND_LAMP_MASK_PASS 17 frames')
if __name__=='__main__':main()
