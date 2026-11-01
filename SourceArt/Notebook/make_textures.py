"""Deterministic, original notebook PBR textures; no external source imagery."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'Textures'
OUT.mkdir(parents=True, exist_ok=True)
N = 2048
rng = np.random.default_rng(193110)
report = {'resolution': N, 'source': 'original procedural textures, seed 193110',
          'color_space': 'BaseColor sRGB; Roughness linear/non-color', 'textures': {}}

def noise(n=N, scales=(8, 32, 128, 512), weights=(.43,.27,.19,.11)):
    a = np.zeros((n,n), dtype=np.float32)
    for scale, weight in zip(scales, weights):
        src = rng.normal(0,1,(scale,scale)).astype('float32')
        im = Image.fromarray(src).resize((n,n),Image.Resampling.BICUBIC)
        a += np.asarray(im) * weight
    return a

def rgb_array(base, variation, n=N):
    return np.clip(np.array(base,dtype='float32')[None,None,:] + variation[:,:,None],0,255).astype('uint8')

def save(key, im):
    p = OUT / f'T_Notebook_{key}.png'
    im.save(p, optimize=True)
    report['textures'][key] = {'file': str(p), 'dimensions': list(im.size),
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'mode': im.mode}
    return im

def rough(key, base=.72, amp=.045):
    a=np.clip(base+noise() * amp,0,1)
    return save(key+'_Roughness',Image.fromarray((a*255).astype('uint8'),'L'))

# Kraft: pressed warm fibreboard, fine fibre fragments and worn light edges.
v = noise() * 11 + rng.normal(0,1.1,(N,N))
yy,xx = np.mgrid[0:N,0:N]
edge = np.minimum.reduce([xx,yy,N-1-xx,N-1-yy]).astype('float32')
v += np.exp(-edge/22) * (5.0 + noise()*3)
kraft=Image.fromarray(rgb_array((164,130,91),v))
d=ImageDraw.Draw(kraft,'RGBA')
for i in range(36000):
    x,y=rng.integers(0,N,2); length=float(rng.uniform(1,7)); ang=float(rng.uniform(-math.pi,math.pi))
    light=bool(rng.integers(0,2)); col=(233,211,175, int(rng.integers(9,31))) if light else (73,47,28,int(rng.integers(6,23)))
    d.line((int(x),int(y),float(x+math.cos(ang)*length),float(y+math.sin(ang)*length)),fill=col,width=1)
for i in range(3200):
    x,y=rng.integers(0,N,2); r=float(rng.uniform(.4,1.5))
    d.ellipse((x-r,y-r,x+r,y+r),fill=(69,47,28,int(rng.integers(8,24))))
save('Kraft_BaseColor',kraft); rough('Kraft',.82,.035)

# Plain-weave spine cloth. The woven threads remain visible in close-ups only.
v=noise()*4
cx=np.mod(xx,14); cy=np.mod(yy,14)
thread=(np.exp(-((cx-3)/1.8)**2)+np.exp(-((cy-3)/1.8)**2))*3.7
checks=((xx//14+yy//14)%2)*1.3
v += thread + checks
cloth=Image.fromarray(rgb_array((42,49,45),v))
d=ImageDraw.Draw(cloth,'RGBA')
for i in range(11000):
    x,y=rng.integers(0,N,2)
    horizontal=bool(rng.integers(0,2)); length=float(rng.uniform(2,9))
    d.line((x,y,x+length if horizontal else x,y if horizontal else y+length),fill=(154,148,120,int(rng.integers(5,19))),width=1)
save('Cloth_BaseColor',cloth); rough('Cloth',.88,.035)

# Old cream paper. Rules deliberately visible, but subtle enough for ink/photo overlays.
v = noise() * 3.2 + rng.normal(0,.65,(N,N))
v -= np.exp(-edge/75) * (5.0 + noise()*1.4)
paper = Image.fromarray(rgb_array((224,214,191),v))
d=ImageDraw.Draw(paper,'RGBA')
for i in range(18000):
    x,y=rng.integers(0,N,2); r=float(rng.uniform(.3,1.1))
    d.ellipse((x-r,y-r,x+r,y+r),fill=(110,91,61,int(rng.integers(4,12))))
endpaper=paper.copy()
save('Endpaper_BaseColor',endpaper)
front=paper.copy(); d=ImageDraw.Draw(front,'RGBA')
line_y=[]
for i in range(27):
    y=round(N*(.09+i*.031))
    line_y.append(y)
    d.line((round(N*.055),y,round(N*.95),y),fill=(92,109,111,105),width=2)
d.line((round(N*.835),round(N*.075),round(N*.835),round(N*.94)),fill=(139,59,49,153),width=3)
save('PaperFront_BaseColor',front)
back=paper.copy(); d=ImageDraw.Draw(back,'RGBA')
for y in line_y:
    d.line((round(N*.05),y,round(N*.945),y),fill=(92,109,111,105),width=2)
d.line((round(N*.165),round(N*.075),round(N*.165),round(N*.94)),fill=(139,59,49,153),width=3)
save('PaperBack_BaseColor',back); rough('Paper',.79,.025)

# End grain of the bound text block: layers run horizontally in texture image.
v=noise()*3
rows=rng.normal(0,1,N)
rows=np.convolve(rows,np.ones(3)/3,mode='same')
v+=rows[:,None]*7
for y in range(3,N,13):
    v[y:y+1]-=float(rng.uniform(10,18))
    v[y+1:y+2]+=float(rng.uniform(2,5))
save('PageEdges_BaseColor',Image.fromarray(rgb_array((205,192,161),v)))
rough('PageEdges',.85,.025)

# Woven muted oxblood ribbon.
v=noise()*4 + np.cos(xx*2*math.pi/9)*2.8 + np.cos(yy*2*math.pi/18)*1.2
save('Ribbon_BaseColor',Image.fromarray(rgb_array((104,38,30),v))); rough('Ribbon',.84,.035)

# Flat printed paper title label, 2:1. Entire image maps to the label UV island.
W,H=2048,1024
labv=noise()*2.5
lab = Image.fromarray(rgb_array((224,211,181),labv)).resize((W,H),Image.Resampling.LANCZOS)
d=ImageDraw.Draw(lab,'RGBA')
d.rectangle((38,38,W-39,H-39),outline=(81,69,46,197),width=3)
d.rectangle((58,58,W-59,H-59),outline=(81,69,46,150),width=2)
font=ImageFont.truetype(r'C:\Windows\Fonts\simkai.ttf',420)
title='手记'
b=d.textbbox((0,0),title,font=font)
tw=b[2]-b[0]; th=b[3]-b[1]
d.text(((W-tw)/2-b[0],(H-th)/2-b[1]-8),title,font=font,fill=(42,41,32,248),stroke_width=0)
save('Label_BaseColor',lab)
rough('Label',.81,.025)

# Small truthfully assembled contact sheet for inspection.
sheet=Image.new('RGB',(1600,1390),(31,32,29)); d=ImageDraw.Draw(sheet)
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',26)
tiles=[('Kraft_BaseColor','旧牛皮纸'),('Cloth_BaseColor','深色布书脊'),
       ('PaperFront_BaseColor','横线正面 · 右红线'),('PaperBack_BaseColor','横线背面 · 左红线'),
       ('Endpaper_BaseColor','衬纸'),('PageEdges_BaseColor','纸页层纹'),
       ('Ribbon_BaseColor','红棕书签'),('Label_BaseColor','封面标签')]
for i,(key,label) in enumerate(tiles):
    col=i%4; row=i//4; x=20+col*395; y=20+row*685
    im=Image.open(report['textures'][key]['file']).convert('RGB')
    thumb=ImageOps.contain(im,(370,595),Image.Resampling.LANCZOS)
    sheet.paste(thumb,(x+(370-thumb.width)//2,y+(595-thumb.height)//2))
    d.text((x,y+605),label,font=font,fill=(221,214,195))
sheet.save(OUT/'Notebook_Texture_ContactSheet.jpg',quality=94)
report['uv_convention']={'all':'UV0 0..1; image top corresponds to V=1; no baked light or emissive',
    'Label':'2:1 physical panel; full UV0; Chinese title 手记 with double border',
    'PaperFront':'+Z-facing recto, image top +Y, right red margin U=.835',
    'PaperBack':'-Z-facing verso, image top +Y, left red margin U=.165; do not mirror the texture again',
    'PageEdges':'horizontal texture rows follow the physical layer lines; U along edge length, V along stack height',
    'Cloth':'seamless fine weave at 14/2048 repeat per thread',
    'Paper_rule_count':27}
(ROOT/'texture_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('NOTEBOOK_TEXTURES_COMPLETE',len(report['textures']))
