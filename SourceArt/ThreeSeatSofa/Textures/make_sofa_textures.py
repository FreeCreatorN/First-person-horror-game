"""Original periodic upholstery PBR textures for the three-seat sofa.

All operations are confined to this directory. No stock imagery or downloads.
Normal maps use tangent-space OpenGL (+Y); ORM is linear R=AO,G=roughness,B=0.
"""
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
N = 2048
TAU = np.float32(2*np.pi)
rng = np.random.default_rng(20261123)
axis = np.arange(N, dtype=np.float32)/N
X = axis[None, :]
Y = axis[:, None]


def noise(cells, seed):
    """Smooth periodic lattice noise, with no repeat discontinuity."""
    gen = np.random.default_rng(seed)
    g = gen.uniform(-1, 1, (cells, cells)).astype(np.float32)
    p = axis*cells
    i = np.floor(p).astype(np.int32)
    t = p-i
    t = t*t*(3-2*t)
    a = g[i[:,None], i[None,:]]
    b = g[i[:,None], ((i+1)%cells)[None,:]]
    c = g[((i+1)%cells)[:,None], i[None,:]]
    d = g[((i+1)%cells)[:,None], ((i+1)%cells)[None,:]]
    return ((a*(1-t[None,:])+b*t[None,:])*(1-t[:,None])+
            (c*(1-t[None,:])+d*t[None,:])*t[:,None]).astype(np.float32)


def fractal(seed):
    return (noise(5,seed)*.49 + noise(13,seed+1)*.28 +
            noise(37,seed+2)*.15 + noise(103,seed+3)*.08)


def normalize(a):
    return np.clip((a+1)*.5, 0, 1)


def make_normal(height, amount):
    dx = (np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.5*amount
    dy = (np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.5*amount
    # Image row grows downward, whereas tangent +Y points up in the image.
    n = np.stack([-dx,dy,np.ones_like(dx)],axis=-1)
    n /= np.sqrt(np.sum(n*n,axis=-1))[...,None]
    return np.uint8(np.clip(n*.5+.5,0,1)*255+.5)


def save(name, color, rough, height, strength, repeat):
    ao = np.clip(.977 - np.maximum(-height,0)*.055, .91,1)
    orm = np.stack([ao,np.clip(rough,0,1),np.zeros_like(rough)],axis=-1)
    maps = {
        'BaseColor':np.uint8(np.clip(color,0,255)+.5),
        'Normal':make_normal(height,strength),
        'ORM':np.uint8(np.clip(orm,0,1)*255+.5)
    }
    files = {}
    stats = {}
    for kind,pixels in maps.items():
        fn=f'T_Sofa_{name}_{kind}.png'
        path=ROOT/fn
        Image.fromarray(pixels,'RGB').save(path,optimize=True)
        files[kind]=fn
        stats[kind]={'minimum':pixels.min(axis=(0,1)).tolist(),
                     'maximum':pixels.max(axis=(0,1)).tolist(),
                     'mean':np.round(pixels.mean(axis=(0,1)),3).tolist(),
                     'edge_mean_delta':float(np.abs(pixels[:,0].astype(float)-pixels[:,-1]).mean()+
                                             np.abs(pixels[0].astype(float)-pixels[-1]).mean())/2,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return {'material':f'M_Sofa_{name}','texture_prefix':f'T_Sofa_{name}',
            'files':files,'resolution':[N,N],'UV_repeat_m':repeat,
            'normal_convention':'OpenGL +Y','normal_strength':1.0,
            'base_color_space':'sRGB','normal_color_space':'linear','orm_color_space':'linear',
            'ORM_channels':{'R':'AmbientOcclusion','G':'Roughness','B':'Metallic'},
            'stats':stats}


def weave(seed,cycles=384):
    # Slightly irregular coarse upholstery, kept below visible checker density.
    wx = TAU*cycles*X + .13*np.sin(TAU*17*Y)
    wy = TAU*cycles*Y + .13*np.sin(TAU*19*X)
    warp = np.sin(wx)
    weft = np.sin(wy)
    basket = (warp+weft)*.26 + warp*weft*.22
    fuzz = noise(577,seed)*.18 + noise(241,seed+1)*.12
    return (basket+fuzz).astype(np.float32)


materials={}

# Warm, worn taupe-brown upholstery. Rubbed fibers form broad, restrained marks;
# no leather cracks, punctures, holes or directional scratch stamps.
age=fractal(110)
rub=np.clip(noise(9,114)*.72+noise(23,115)*.28-.05,0,1)
fine=noise(281,116)
grain=weave(117)
base=np.array([101,84,70],dtype=np.float32)
color=np.empty((N,N,3),dtype=np.float32)
color[:]=base
color+=age[...,None]*np.array([27,24,21],dtype=np.float32)
color+=rub[...,None]*np.array([22,23,23],dtype=np.float32)
color+=fine[...,None]*2.3+grain[...,None]*2.4
# Sparse dark fibers add textile character without producing speckles at distance.
fibers=np.maximum(noise(433,118)-.74,0)
color-=fibers[...,None]*12
rough=np.clip(.845+age*.035-rub*.105+grain*.022,.68,.94)
height=grain*.34+fine*.06+age*.08
materials['Fabric']=save('Fabric',color,rough,height,.70,.45)
del color,age,rub,fine,grain,rough,height,fibers

# Muted plaid cloth for the two decorative cushions. Eight checks per 28 cm tile
# give 3.5 cm checks; paired narrow lines are woven into the broad brown bands.
age=fractal(210)
grain=weave(211,416)
ux=np.mod(X*8,2)
uy=np.mod(Y*8,2)
stripe_x=(np.cos(TAU*X*4)+1)*.5
stripe_y=(np.cos(TAU*Y*4)+1)*.5
broad_x=np.clip((stripe_x-.34)/.34,0,1)
broad_y=np.clip((stripe_y-.34)/.34,0,1)
line_x=np.exp(-np.square(np.sin(TAU*X*8))/.006)
line_y=np.exp(-np.square(np.sin(TAU*Y*8))/.006)
sub_x=np.exp(-np.square(np.sin(TAU*(X*8+.075)))/.0025)
sub_y=np.exp(-np.square(np.sin(TAU*(Y*8+.075)))/.0025)
color=np.empty((N,N,3),dtype=np.float32)
color[:]=np.array([146,140,125],dtype=np.float32)
color-=broad_x[...,None]*np.array([31,32,30],dtype=np.float32)
color-=broad_y[...,None]*np.array([26,27,24],dtype=np.float32)
color-=np.maximum(line_x,line_y)[...,None]*np.array([15,17,17],dtype=np.float32)
color+=np.maximum(sub_x,sub_y)[...,None]*np.array([11,10,8],dtype=np.float32)
color+=age[...,None]*12+grain[...,None]*2.7
rough=np.clip(.85+age*.035+grain*.02,.76,.94)
height=grain*.29+age*.05
materials['Plaid']=save('Plaid',color,rough,height,.66,.28)
del color,age,grain,rough,height,broad_x,broad_y,line_x,line_y,sub_x,sub_y

# Dark woven dust-cover cloth on the underside. Almost black, but not a void.
age=fractal(310)
grain=weave(311,448)
color=np.empty((N,N,3),dtype=np.float32)
color[:]=np.array([36,35,33],dtype=np.float32)
color+=age[...,None]*6+grain[...,None]*1.8
rough=np.clip(.92+age*.018+grain*.015,.85,.98)
height=grain*.26+age*.035
materials['Underside']=save('Underside',color,rough,height,.58,.45)

manifest={
 'success':True,'description':'Original seamless aged woven fabric for ThreeSeatSofa',
 'method':'Deterministic periodic procedural textile with original color design; no external images',
 'resolution':[N,N],'map_count':9,'material_sets':materials,
 'notes':[
  'Rotate/offset UV islands by modest amounts to avoid repeated rub patterns across cushions.',
  'Fabric should use 0.45 m physical repeat, plaid 0.28 m repeat, underside 0.45 m repeat.',
  'Normals are subtle thread relief. Cushion folds and piping should be modeled independently.',
  'Blender OpenGL normal; Unreal flip green channel on import.',
  'BaseColor sRGB; Normal and ORM NonColor/linear. All maps tile periodically.'
 ]}
(ROOT/'SofaMaterialManifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

font_path=Path('C:/Windows/Fonts/arial.ttf')
font=ImageFont.truetype(str(font_path),26) if font_path.is_file() else ImageFont.load_default()
small=ImageFont.truetype(str(font_path),18) if font_path.is_file() else ImageFont.load_default()
proof=Image.new('RGB',(1520,1070),(31,30,29))
d=ImageDraw.Draw(proof)
d.text((28,15),'THREE-SEAT SOFA | ORIGINAL SEAMLESS PBR TEXTILES',font=font,fill=(235,225,207))
for row,(name,mat) in enumerate(materials.items()):
 y=66+row*330
 d.text((25,y+10),name,font=font,fill=(232,222,208))
 d.text((25,y+47),f"Repeat {mat['UV_repeat_m']} m",font=small,fill=(180,175,167))
 for col,kind in enumerate(['BaseColor','Normal','ORM']):
  im=Image.open(ROOT/mat['files'][kind]).convert('RGB')
  x=240+col*415
  proof.paste(im.resize((290,290),Image.Resampling.LANCZOS),(x,y))
  d.text((x+300,y+8),kind,font=small,fill=(210,205,196))
proof.save(ROOT/'Sofa_Material_Proof.jpg',quality=93,subsampling=0)
print(json.dumps({'success':True,'material_sets':list(materials),'texture_count':9,
 'manifest':str(ROOT/'SofaMaterialManifest.json'),'proof':str(ROOT/'Sofa_Material_Proof.jpg')},indent=2))
