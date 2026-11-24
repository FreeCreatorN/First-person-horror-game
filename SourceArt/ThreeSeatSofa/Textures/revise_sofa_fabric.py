"""Darken only Fabric after review of the actual Cycles sofa render.

The original first-pass Fabric is retained as a deterministic revision input.
Plaid, underside and Fabric ORM remain byte-identical.
"""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
REV=ROOT/'Revisions'/'Fabric_v01'
REV.mkdir(parents=True,exist_ok=True)
for kind in ['BaseColor','Normal','ORM']:
 fn=f'T_Sofa_Fabric_{kind}.png'
 if not (REV/fn).exists():shutil.copy2(ROOT/fn,REV/fn)
if not (REV/'SofaMaterialManifest.json').exists():
 shutil.copy2(ROOT/'SofaMaterialManifest.json',REV/'SofaMaterialManifest.json')
manifest=json.loads((ROOT/'SofaMaterialManifest.json').read_text(encoding='utf-8'))
old=np.asarray(Image.open(REV/'T_Sofa_Fabric_BaseColor.png').convert('RGB'),dtype=np.float32)
N=old.shape[0]
axis=np.arange(N,dtype=np.float32)/N
X=axis[None,:];Y=axis[:,None];TAU=np.float32(2*np.pi)
# 360 repeat threads across a 45 cm tile = 1.25 mm coarse textile.
wx=TAU*360*X+.11*np.sin(TAU*17*Y)
wy=TAU*360*Y+.11*np.sin(TAU*19*X)
thread=(np.sin(wx)+np.sin(wy))*.45+np.sin(wx)*np.sin(wy)*.28
# First-pass broad marks reduced25%; warm dark-brown target from actual render review.
color=(old-old.mean(axis=(0,1)))*.75+np.array([78,59,44],dtype=np.float32)
color+=thread[...,None]*3.0
color=np.uint8(np.clip(color,0,255)+.5)
Image.fromarray(color,'RGB').save(ROOT/'T_Sofa_Fabric_BaseColor.png',optimize=True)

oldnormal=np.asarray(Image.open(REV/'T_Sofa_Fabric_Normal.png'),dtype=np.float32)/255*2-1
oldnormal/=np.maximum(np.sqrt(np.sum(oldnormal*oldnormal,axis=-1))[...,None],1e-6)
height=thread*.37
dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.5*.9
dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.5*.9
normal=np.stack([-dx+oldnormal[...,0]*.3,dy+oldnormal[...,1]*.3,np.ones_like(dx)],axis=-1)
normal/=np.sqrt(np.sum(normal*normal,axis=-1))[...,None]
normal=np.uint8(np.clip(normal*.5+.5,0,1)*255+.5)
Image.fromarray(normal,'RGB').save(ROOT/'T_Sofa_Fabric_Normal.png',optimize=True)

mat=manifest['material_sets']['Fabric']
for kind,fn in mat['files'].items():
 path=ROOT/fn;pixels=np.asarray(Image.open(path).convert('RGB'))
 mat['stats'][kind]={'minimum':pixels.min(axis=(0,1)).tolist(),
  'maximum':pixels.max(axis=(0,1)).tolist(),'mean':np.round(pixels.mean(axis=(0,1)),3).tolist(),
  'edge_mean_delta':float(np.abs(pixels[:,0].astype(float)-pixels[:,-1]).mean()+
    np.abs(pixels[0].astype(float)-pixels[-1]).mean())/2,
  'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
mat['revision']='v02 actual-Cycles review: dark warm brown, broad contrast reduced25%,1.25mm thread relief'
mat['original_revision_input']='Revisions/Fabric_v01'
manifest['notes'].append('Fabric v02 mean sRGB78/59/44, revised after actual rendered appearance review; plaid and underside unchanged.')
(ROOT/'SofaMaterialManifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',26)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
proof=Image.new('RGB',(1520,1070),(31,30,29));d=ImageDraw.Draw(proof)
d.text((28,15),'THREE-SEAT SOFA | PBR TEXTILES | FABRIC v02',font=font,fill=(235,225,207))
for row,(name,m) in enumerate(manifest['material_sets'].items()):
 y=66+row*330;d.text((25,y+10),name,font=font,fill=(232,222,208))
 d.text((25,y+47),f"Repeat {m['UV_repeat_m']} m",font=small,fill=(180,175,167))
 for col,kind in enumerate(['BaseColor','Normal','ORM']):
  im=Image.open(ROOT/m['files'][kind]).convert('RGB');x=240+col*415
  proof.paste(im.resize((290,290),Image.Resampling.LANCZOS),(x,y))
  d.text((x+300,y+8),kind,font=small,fill=(210,205,196))
proof.save(ROOT/'Sofa_Material_Proof.jpg',quality=93,subsampling=0)
proof=Image.new('RGB',(1536,1024),(30,28,26))
for col,name in enumerate(['Fabric','Plaid','Underside']):
 im=Image.open(ROOT/manifest['material_sets'][name]['files']['BaseColor'])
 tile=im.resize((256,256),Image.Resampling.LANCZOS)
 for y in range(2):
  for x in range(2):proof.paste(tile,(col*512+x*256,y*256))
 proof.paste(im.crop((512,512,1024,1024)),(col*512,512))
proof.save(ROOT/'Sofa_Tiling_And_Weave_Proof.jpg',quality=95,subsampling=0)
print(json.dumps({'success':True,'fabric_revision':mat['revision'],'stats':mat['stats']},indent=2))
