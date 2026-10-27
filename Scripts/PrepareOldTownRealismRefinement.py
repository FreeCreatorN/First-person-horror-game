"""Freeze the accepted saved-map input and prescribe this material-only stage."""
import json
from pathlib import Path
import re
import shutil
from collections import Counter
from VerifyOldTownRealismRefinement import create_baseline, verify_baseline, sha

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
WORK=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
ASSET='/Game/CodexGenerated/OldTown/RealismRefinement_20261013'

def write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    before=WORK/'Before';before.mkdir(parents=True,exist_ok=True)
    assert not (WORK/'Baseline.json').exists(), 'Do not recreate an existing stage baseline.'
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    pointer=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'
    shutil.copy2(mapfile,before/'L_OldTownSchoolStreet.umap')
    shutil.copy2(pointer,before/'CurrentEvidence.json')
    baseline=create_baseline(before/'L_OldTownSchoolStreet.umap',before/'CurrentEvidence.json')
    data=verify_baseline(baseline)
    write(WORK/'Baseline.json',baseline)
    native=data['native'];actors=native['actors']
    wallroles={'Plaster_World','ConcreteWall_World','BluePlaster_World','GreenPlaster_World'}
    woodroles={'Wood_UV','Wood_World','PaintedWood_UV'}
    clothroles={'Linen_UV','Linen_World','LinenSeam_UV','LinenSeam_World','Upholstery_UV'}
    def group(a):
        folder=actors[a]['folder']
        if a.startswith('OTS_HotelV4_'):return 'HotelV4'
        if '/EnterableBuildings/' in folder:return folder.split('/EnterableBuildings/')[1].split('/')[0]
        if a.startswith('OTS_Enterable_'):
            return re.split(r'_(?:Wall|Roof|Floor|Interior|Door|Window)',a)[0]
        return folder
    minima={}
    for a,records in native['component_records'].items():
        for c in records:
            if c.get('mesh') and any(m['base_material'].split('/')[-1].split('.')[0].removeprefix('M_R_') in wallroles for m in c.get('materials',[])):
                key=group(a);z=c['world_render_bounds_before_wpo_cm'][0][2]
                minima[key]=min(z,minima.get(key,z))
    rows=[];counts=Counter()
    floorz=[11.,378.25,745.5,1112.75]
    for a,records in native['component_records'].items():
        for c in records:
            pp=c.get('primitive_properties',{})
            if not c.get('mesh') or not pp.get('visible') or pp.get('hidden_in_game'):continue
            ident=a+'::'+c['name'];slots=[]
            for mat in c['materials']:
                base=mat['base_material'];role=base.split('/')[-1].split('.')[0].removeprefix('M_R_')
                if not base.startswith('/Game/CodexGenerated/OldTown/Realism_20261012/Materials/M_R_'):continue
                if role not in wallroles|woodroles|clothroles:continue
                key=group(a);zbase=minima.get(key,11.)
                if key=='HotelV4':
                    if any(t in a for t in ('StreetWall','RearWall','EndWall')):zbase=11.
                    else:zbase=max((z for z in floorz if z<=c['world_render_bounds_before_wpo_cm'][0][2]+.2),default=11.)
                seed=int(sha_bytes(key.encode())[:8],16)
                phase=[float((seed>>(i*8))%127)*17.1 for i in range(3)]
                damp=.42 if 'Back' in key or 'Alley' in key else .22
                slots.append(dict(slot=mat['slot'],source_base=base,role=role,
                    category='wall' if role in wallroles else 'wood' if role in woodroles else 'cloth',
                    surface_translation_cm=mat['effective_surface_translation_cm'],
                    building_group=key,building_phase_cm=phase if role.endswith('_World') else [0.,0.,0.],
                    floor_base_z_cm=zbase,damp_amount=damp))
                counts[role]+=1
            lamp=None
            if a.startswith('OTS_P2Prop_StreetLamp_'):
                index=int(a.rsplit('_',1)[-1])
                if index!=3:lamp=dict(slot=2,kind='StreetLens',light_actor=f'OTS_Light_StreetLamp{index:02d}',strength=4.)
            elif re.fullmatch(r'OTS_HotelV4_F[0-3]_GalleryTube(?:01|04)',a):
                floor=int(re.search(r'_F(\d)',a)[1]);tube=0 if a.endswith('01') else 1
                lamp=dict(slot=2,kind='HotelTube',light_actor=f'OTS_HotelV4_F{floor}_SurvivingTube{tube}',strength=3.)
            if slots or lamp:rows.append(dict(id=ident,actor=a,component=c['name'],slots=slots,lamp=lamp))
    assert sum(bool(r['lamp']) for r in rows)==16
    write(WORK/'MaterialPrescription.json',dict(schema='OldTownRealismMaterialPrescriptionV1',
        source_map_sha256=baseline['source_map_sha256'],new_asset_root=ASSET,components=rows,
        category_slot_counts=dict(counts),geometry_changes=False,
        lamp_policy='Only fixtures with an existing visible, positive-intensity source glow; bodies/posts/sockets stay nonemissive.',
        tube_mask_local_cm=dict(full_at_abs_y=42.5,zero_at_abs_y=43.1),
        current_scope='Material refinements and luminous lamp surfaces; soft-goods geometry remains the accepted source in this stage.'))
    print(json.dumps(dict(passed=True,components=len(rows),slots=sum(counts.values()),emissive_fixtures=16,counts=dict(counts))))

def sha_bytes(x):
    import hashlib
    return hashlib.sha256(x).hexdigest()

if __name__=='__main__':main()
