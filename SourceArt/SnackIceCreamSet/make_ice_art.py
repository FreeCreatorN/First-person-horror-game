"""Original freezer packaging artwork. Pillow/NumPy only; no external artwork.

UV contract: flavor bands ordered bottom-first; front occupies U 0..0.5,
back U 0.5..1. Artwork is inset 8 pixels from each island edge. Draw each
panel at its physical aspect before resampling into its atlas rectangle.
"""
from pathlib import Path
import json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'Textures'
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 2048
FONT = 'C:/Windows/Fonts/msyh.ttc'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'

PALETTES = {
 'Vanilla': ((36,124,189),(213,238,243),(255,245,211),(25,70,111)),
 'Strawberry': ((201,61,102),(250,200,210),(255,244,230),(112,34,64)),
 'Milk': ((35,130,182),(209,240,247),(255,253,236),(20,70,106)),
 'Orange': ((223,150,24),(244,224,98),(255,249,219),(80,113,37)),
 'Chocolate': ((75,39,30),(143,92,58),(251,230,185),(61,30,21)),
 'VanillaGold': ((184,138,61),(249,228,172),(255,250,226),(80,54,30)),
}
FAMILIES = [
 ('BoxIce',1.6,[('Vanilla','香草味','香草冰淇淋','CREAMY VANILLA','盒装 · 120 g'),('Strawberry','草莓味','草莓冰淇淋','STRAWBERRY CREAM','盒装 · 120 g')]),
 ('IcePop',.55,[('Milk','牛乳味','奶香棒冰','MILK ICE POP','净含量 70 g'),('Orange','香橙味','果味冰棒','ORANGE ICE POP','净含量 70 g')]),
 ('ChocoBar',.55,[('Chocolate','巧克力味','脆皮雪糕','CHOCOLATE CRUNCH','净含量 75 g'),('Vanilla','香草味','巧克力雪糕','VANILLA & CHOCOLATE','净含量 75 g')]),
 ('CupIce',1.7,[('Strawberry','草莓味','杯装雪糕','STRAWBERRY CREAM','净含量 100 g'),('Vanilla','香草味','杯装雪糕','CREAMY VANILLA','净含量 100 g')]),
 ('Cone',.6,[('Vanilla','香草味','甜筒雪糕','VANILLA CONE','净含量 90 g'),('Chocolate','巧克力味','甜筒雪糕','CHOCOLATE CONE','净含量 90 g'),('Strawberry','草莓味','甜筒雪糕','STRAWBERRY CONE','净含量 90 g')]),
 ('FamilyTub',2.2,[('Vanilla','香草味','家庭装雪糕','FAMILY VANILLA','分享装 · 净含量 500 g'),('Strawberry','草莓味','家庭装雪糕','FAMILY STRAWBERRY','分享装 · 净含量 500 g')]),
]

def font(s,bold=False): return ImageFont.truetype(BOLD if bold else FONT,max(8,int(s)))
def text(d,xy,txt,size,fill,bold=False,anchor=None,stroke=0,strokefill=None):
 d.text(tuple(map(int,xy)),txt,font=font(size,bold),fill=fill,anchor=anchor,stroke_width=stroke,stroke_fill=strokefill)
def fitted(d,xy,txt,maxw,size,fill,bold=False,anchor=None):
 f=font(size,bold)
 while d.textbbox((0,0),txt,font=f)[2]>maxw and size>9:
  size-=1; f=font(size,bold)
 d.text(tuple(map(int,xy)),txt,font=f,fill=fill,anchor=anchor)
def rr(d,box,r,fill,outline=None,width=1): d.rounded_rectangle(tuple(map(int,box)),radius=int(r),fill=fill,outline=outline,width=width)

def shaded_ellipse(canvas,box,base,seed=0,texture=1.6):
 """Soft spherical shading, tiny ice/flesh texture, no photograph inputs."""
 x0,y0,x1,y1=map(int,box); w=x1-x0; h=y1-y0
 yy,xx=np.mgrid[-1:1:complex(h),-1:1:complex(w)]
 q=xx*xx+yy*yy; z=np.sqrt(np.maximum(0,1-q))
 light=.56+.42*z-.12*xx-.13*yy
 rng=np.random.default_rng(seed)
 noise=rng.normal(0,texture,(h,w))
 noise+=texture*1.7*(np.sin(xx*36+np.sin(yy*12))*np.sin(yy*31+xx*3))
 rgb=np.clip(np.array(base)[None,None,:]*light[:,:,None]+noise[:,:,None],0,255).astype('uint8')
 alpha=(np.clip((1-q)*140,0,1)*255).astype('uint8')
 canvas.alpha_composite(Image.fromarray(np.dstack([rgb,alpha]),'RGBA'),(x0,y0))

def strawberry(canvas,cx,cy,r,seed=1):
 rng=np.random.default_rng(seed)
 # Upright berry silhouette, broad shoulder and a rounded tapered tip.
 w=int(r*2.1); h=int(r*2.5)
 lay=Image.new('RGBA',(w,h)); mask=Image.new('L',(w,h)); md=ImageDraw.Draw(mask)
 pts=[(.11,.33),(.19,.17),(.39,.10),(.56,.11),(.79,.18),(.90,.34),(.86,.53),(.71,.75),(.53,.94),(.43,.95),(.27,.78),(.15,.57)]
 md.polygon([(int(a*w),int(b*h)) for a,b in pts],fill=255)
 mask=mask.filter(ImageFilter.GaussianBlur(max(1,r*.025)))
 yy,xx=np.mgrid[0:h,0:w]; shade=.7+.36*np.exp(-((xx-w*.33)**2/(w*.5)**2+(yy-h*.33)**2/(h*.7)**2))
 col=np.zeros((h,w,4),np.uint8)
 col[:,:,0]=np.clip(225*shade+rng.normal(0,3,(h,w)),0,255)
 col[:,:,1]=np.clip(42*shade,0,255); col[:,:,2]=np.clip(58*shade,0,255); col[:,:,3]=np.asarray(mask)
 lay=Image.fromarray(col); d=ImageDraw.Draw(lay)
 for i in range(5):
  fy=.26+i*.135
  span=.33*(1-(fy-.25)*.7)
  for fx in np.linspace(.5-span,.5+span,5-i//2):
   sx=int((fx+rng.uniform(-.015,.015))*w); sy=int(fy*h+rng.uniform(-.02,.02)*h)
   d.ellipse((sx-r*.018,sy-r*.035,sx+r*.018,sy+r*.035),fill=(255,218,119,220))
 for k in range(5):
  a=-math.pi/2+(k-2)*.62
  p=(w*.49+math.cos(a)*r*.65,h*.18+math.sin(a)*r*.5)
  d.polygon([(w*.49,h*.24),(p[0]-r*.16,p[1]),(p[0],p[1]-r*.13),(p[0]+r*.15,p[1])],fill=(59,113+12*k,53,255))
 canvas.alpha_composite(lay,(int(cx-w/2),int(cy-h/2)))

def orange(canvas,cx,cy,r):
 shaded_ellipse(canvas,(cx-r,cy-r,cx+r,cy+r),(252,170,31),18,2.4)
 d=ImageDraw.Draw(canvas)
 # Juicy cross section beside the whole fruit.
 sr=r*.77; sx=cx+r*.55; sy=cy+r*.40
 d.ellipse((sx-sr,sy-sr,sx+sr,sy+sr),fill=(255,239,173))
 d.ellipse((sx-sr*.88,sy-sr*.88,sx+sr*.88,sy+sr*.88),fill=(255,160,24))
 for k in range(9):
  a=k*2*math.pi/9
  d.line((sx,sy,sx+math.cos(a)*sr*.86,sy+math.sin(a)*sr*.86),fill=(255,236,163),width=max(2,int(r*.04)))
 d.ellipse((sx-r*.07,sy-r*.07,sx+r*.07,sy+r*.07),fill=(255,242,190))
 d.ellipse((cx-r*.15,cy-r*1.04,cx+r*.7,cy-r*.77),fill=(58,126,52))

def vanilla(canvas,cx,cy,r):
 d=ImageDraw.Draw(canvas)
 for delta in [-.12,.12]:
  d.line((cx-r,cy+r*.4+delta*r,cx+r*.6,cy-r*.24+delta*r),fill=(79,43,32),width=max(3,int(r*.075)))
 petals=[(-.9,-.1),(-.5,-.56),(.1,-.4),(.24,.17),(-.4,.45)]
 for dx,dy in petals:
  d.ellipse((cx+(dx-.23)*r,cy+(dy-.35)*r,cx+(dx+.27)*r,cy+(dy+.3)*r),fill=(255,250,222),outline=(235,215,169),width=2)
 d.ellipse((cx-r*.48,cy-r*.2,cx-r*.15,cy+r*.12),fill=(240,185,54))

def scoop(canvas,cx,cy,r,flavor,seed=9):
 base={'Vanilla':(255,242,204),'Milk':(253,250,226),'Strawberry':(248,170,183),'Chocolate':(127,75,49)}.get(flavor,(255,242,204))
 d=ImageDraw.Draw(canvas)
 for dx,dy,scale in [(-.49,.40,.43),(.43,.42,.42),(0,.55,.45)]:
  shaded_ellipse(canvas,(cx+(dx-scale)*r,cy+(dy-scale)*r,cx+(dx+scale)*r,cy+(dy+scale)*r),base,seed+4,2.5)
 shaded_ellipse(canvas,(cx-r,cy-r,cx+r,cy+r*.87),base,seed,2.2)
 rng=np.random.default_rng(seed)
 for _ in range(40):
  xx,yy=rng.uniform(-.82,.82,2)
  if xx*xx+yy*yy<.69:
   rad=rng.uniform(.004,.011)*r
   if flavor=='Strawberry': col=(203,109,131,255)
   elif flavor=='Chocolate': col=(103,64,46,255)
   else: col=(198,177,133,255)
   d.ellipse((cx+xx*r-rad,cy+yy*r-rad,cx+xx*r+rad,cy+yy*r+rad),fill=col)

def pop(canvas,cx,cy,w,h,flavor,chocolate=False):
 d=ImageDraw.Draw(canvas)
 rr(d,(cx-w*.10,cy+h*.3,cx+w*.10,cy+h*.72),w*.09,(204,164,104),outline=(171,128,76),width=max(1,int(w*.015)))
 rr(d,(cx-w*.48,cy-h*.48,cx+w*.5,cy+h*.4),w*.18,(82,65,47))
 base=(99,53,35) if chocolate else ((255,239,202) if flavor in ['Milk','Vanilla'] else (255,170,33))
 x0=int(cx-w*.5); y0=int(cy-h*.5); x1=int(cx+w*.46); y1=int(cy+h*.38)
 sw=x1-x0; sh=y1-y0; yy,xx=np.mgrid[0:sh,0:sw]; nx=xx/sw; ny=yy/sh
 shade=.76+.22*np.exp(-((nx-.30)/.44)**2)+.04*(1-ny)
 shade-=.13*np.exp(-((nx-.96)/.06)**2)
 rng=np.random.default_rng(442)
 rgb=np.clip(np.array(base)[None,None,:]*shade[:,:,None]+rng.normal(0,1.2,(sh,sw,1)),0,255)
 highlight=np.exp(-((nx-.21)/.06)**2)*10
 rgb=np.clip(rgb+highlight[:,:,None],0,255).astype('uint8')
 mask=Image.new('L',(sw,sh)); ImageDraw.Draw(mask).rounded_rectangle((0,0,sw-1,sh-1),radius=int(w*.16),fill=255)
 top=Image.new('RGBA',canvas.size)
 top.alpha_composite(Image.fromarray(np.dstack([rgb,np.asarray(mask)]),'RGBA'),(x0,y0))
 td=ImageDraw.Draw(top)
 if chocolate:
  rng=np.random.default_rng(42)
  for _ in range(100):
   x=rng.uniform(cx-w*.43,cx+w*.38); y=rng.uniform(cy-h*.4,cy+h*.3); r=rng.uniform(w*.01,w*.028)
   td.ellipse((x-r,y-r,x+r,y+r),fill=(137,87,51,210))
  # Reveal a pale vanilla bite at upper right.
  td.polygon([(cx+w*.07,cy-h*.5),(cx+w*.39,cy-h*.5),(cx+w*.46,cy-h*.37),(cx+w*.32,cy-h*.32),(cx+w*.23,cy-h*.36),(cx+w*.13,cy-h*.32),(cx+w*.05,cy-h*.41)],fill=(255,235,186))
 canvas.alpha_composite(top)

def cone(canvas,cx,cy,w,h,flavor):
 d=ImageDraw.Draw(canvas)
 ytop=cy-h*.16; ybot=cy+h*.54
 d.polygon([(cx-w*.43,ytop),(cx+w*.43,ytop),(cx,ybot)],fill=(194,132,62),outline=(141,83,33))
 # Clip diagonal baked waffle grid to the tapered cone.
 grid=Image.new('RGBA',canvas.size); gd=ImageDraw.Draw(grid)
 for j in range(-14,15):
  y=ytop+j*w*.10
  gd.line((cx-w*.5,y,cx+w*.5,y+w*.9),fill=(119,73,30,185),width=max(2,int(w*.018)))
  gd.line((cx-w*.5,y,cx+w*.5,y-w*.9),fill=(239,182,99,220),width=max(2,int(w*.02)))
 m=Image.new('L',canvas.size); ImageDraw.Draw(m).polygon([(cx-w*.43,ytop),(cx+w*.43,ytop),(cx,ybot)],fill=255)
 grid.putalpha(Image.composite(grid.getchannel('A'),Image.new('L',canvas.size),m)); canvas.alpha_composite(grid)
 scoop(canvas,cx,cy-h*.25,w*.54,flavor)

def food(canvas,family,flavor,box):
 x0,y0,x1,y1=box; w=x1-x0; h=y1-y0; cx=(x0+x1)/2; cy=(y0+y1)/2
 shadow=Image.new('RGBA',canvas.size); sd=ImageDraw.Draw(shadow)
 sd.ellipse((x0+w*.06,y1-h*.12,x1-w*.02,y1+h*.02),fill=(30,31,32,38))
 canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(3,w*.04))))
 if family in ['BoxIce','CupIce','FamilyTub']:
  r=min(w*.33,h*.49)
  scoop(canvas,cx+w*.05,cy-h*.08,r,flavor)
  if flavor=='Strawberry': strawberry(canvas,cx-w*.27,cy+h*.16,r*.46,2); strawberry(canvas,cx+w*.30,cy+h*.30,r*.33,4)
  elif flavor=='Chocolate':
   dd=ImageDraw.Draw(canvas); dd.polygon([(cx-r,cy+r*.25),(cx-r*.1,cy+r*.35),(cx-r*.1,cy+r*.7),(cx-r,cy+r*.6)],fill=(76,39,28))
  else: vanilla(canvas,cx-w*.22,cy+h*.3,r*.65)
 elif family=='Cone':
  cone(canvas,cx,cy+h*.045,w*.64,h*.82,flavor)
  if flavor=='Strawberry': strawberry(canvas,cx-w*.27,cy+h*.26,w*.16,7)
  elif flavor=='Vanilla': vanilla(canvas,cx+w*.15,cy+h*.29,w*.23)
 elif family=='ChocoBar': pop(canvas,cx,cy-h*.05,w*.58,h*.73,flavor,True)
 else:
  pop(canvas,cx,cy-h*.07,w*.57,h*.68,flavor)
  if flavor=='Orange': orange(canvas,cx-w*.14,cy+h*.31,w*.20)
  else: vanilla(canvas,cx+w*.1,cy+h*.36,w*.25)

def snowflake(d,x,y,r,col):
 for k in range(6):
  a=k*math.pi/3; ex=x+math.cos(a)*r; ey=y+math.sin(a)*r
  d.line((x,y,ex,ey),fill=col,width=max(1,int(r*.09)))
  for sign in [-1,1]:
   bx=x+math.cos(a)*r*.62; by=y+math.sin(a)*r*.62
   aa=a+sign*math.pi*.23
   d.line((bx,by,bx-math.cos(aa)*r*.27,by-math.sin(aa)*r*.27),fill=col,width=max(1,int(r*.06)))

def basepanel(w,h,palette,seed):
 deep,light,cream,ink=palette
 yy,xx=np.mgrid[0:h,0:w]; t=(yy/h)*.62+(xx/w)*.12
 arr=np.array(light)[None,None,:]*(1-t[:,:,None])+np.array(deep)[None,None,:]*t[:,:,None]
 rng=np.random.default_rng(seed); arr+=rng.normal(0,.55,(h,w,1))
 canvas=Image.fromarray(np.clip(arr,0,255).astype('uint8')).convert('RGBA'); d=ImageDraw.Draw(canvas)
 # Low flowing cream ribbon, snowflakes and tiny frost dots.
 d.ellipse((-w*.4,h*.70,w*1.6,h*1.50),fill=cream+(250,))
 d.ellipse((-w*.5,-h*.22,w*.5,h*.18),fill=(255,255,255,30))
 for _ in range(14):
  snowflake(d,rng.uniform(w*.02,w*.98),rng.uniform(h*.03,h*.82),rng.uniform(min(w,h)*.015,min(w,h)*.04),(255,255,255,67))
 return canvas

def front(family,aspect,flavor,flavortxt,title,english,weight):
 w=1200; h=int(w/aspect); sc=min(w,h)
 pal=PALETTES['VanillaGold' if family=='ChocoBar' and flavor=='Vanilla' else flavor]
 deep,light,cream,ink=pal
 title_ink=cream if flavor=='Chocolate' else ink
 im=basepanel(w,h,pal,sum(map(ord,family+flavor))); d=ImageDraw.Draw(im)
 tall=aspect<1
 # Tear/crimp margin on flexible wrappers; carton stripe on wider packaging.
 if tall:
  d.rectangle((0,0,w,h*.028),fill=deep)
  d.rectangle((0,h*.964,w,h),fill=deep)
  for x in range(8,w,16):
   d.line((x,0,x,h*.027),fill=tuple(min(255,c+32) for c in deep),width=2)
   d.line((x,h*.965,x,h),fill=tuple(max(0,c-25) for c in deep),width=2)
  text(d,(w*.5,h*.064),'冷 冻 甜 品',sc*.043,ink,True,'mm')
  # Short horizontal title lines keep every character readable on slim packs.
  if len(title)>4:
   t1=title[:3]; t2=title[3:]
   fitted(d,(w*.5,h*.135),t1,w*.87,sc*.135,title_ink,True,'mm')
   fitted(d,(w*.5,h*.205),t2,w*.87,sc*.135,title_ink,True,'mm')
   badgeY=.27
  else:
   fitted(d,(w*.5,h*.15),title,w*.88,sc*.16,title_ink,True,'mm'); badgeY=.225
  rr(d,(w*.29,h*badgeY,w*.71,h*(badgeY+.045)),sc*.023,cream)
  text(d,(w*.5,h*(badgeY+.022)),flavortxt,sc*.055,ink,True,'mm')
  fitted(d,(w*.5,h*(badgeY+.075)),english,w*.85,sc*.035,cream,True,'mm')
  food(im,family,flavor,(w*.08,h*.34,w*.92,h*.85))
  d=ImageDraw.Draw(im)
  text(d,(w*.5,h*.885),'绵密细腻  ·  冰爽一刻',sc*.044,ink,False,'mm')
  text(d,(w*.5,h*.934),weight,sc*.044,ink,True,'mm')
 else:
  text(d,(w*.045,h*.085),'冷 冻 甜 品',sc*.044,ink,True)
  fitted(d,(w*.045,h*.21),title,w*.59,sc*.117,title_ink,True)
  fitted(d,(w*.047,h*.40),english,w*.54,sc*.036,cream,True)
  rr(d,(w*.047,h*.51,w*.047+sc*.28,h*.625),sc*.018,cream)
  text(d,(w*.047+sc*.14,h*.565),flavortxt,sc*.052,ink,True,'mm')
  text(d,(w*.045,h*.77),'绵密细腻 · 冰爽一刻',sc*.043,ink)
  text(d,(w*.045,h*.89),weight,sc*.039,ink,True)
  food(im,family,flavor,(w*.54,h*.05,w*.99,h*.92))
 # Print lot field and understated freezer storage requirement.
 return finish(im,family+flavor)

def barcode(d,box,seed):
 x0,y0,x1,y1=map(int,box); d.rectangle(box,fill=(255,251,236))
 rng=np.random.default_rng(seed); x=x0+(x1-x0)*.04; unit=(x1-x0)/145
 for _ in range(48):
  bw=unit*int(rng.integers(1,4)); gap=unit*int(rng.integers(1,3))
  if x+bw>x1-(x1-x0)*.04: break
  d.rectangle((int(x),y0+3,int(x+bw),int(y1-(y1-y0)*.23)),fill=(37,37,32)); x+=bw+gap
 text(d,((x0+x1)/2,y1-(y1-y0)*.10),'690 2026 1208',max(10,(y1-y0)*.14),(37,37,32),False,'mm')

def back(family,aspect,flavor,flavortxt,title,english,weight):
 w=1200; h=int(w/aspect); sc=min(w,h)
 pal=PALETTES['VanillaGold' if family=='ChocoBar' and flavor=='Vanilla' else flavor]
 deep,light,cream,ink=pal
 im=basepanel(w,h,pal,10+sum(map(ord,family+flavor))); d=ImageDraw.Draw(im)
 rr(d,(w*.045,h*.045,w*.955,h*.955),sc*.018,(255,250,231,244))
 if aspect<1:
  text(d,(w*.10,h*.072),title,sc*.078,ink,True)
  text(d,(w*.10,h*.126),flavortxt+' / '+english,sc*.026,ink)
  y=.195; line=.029
  ingredients=['产品类型：冷冻饮品','配料：饮用水、牛乳、白砂糖、','稀奶油、乳粉、食用植物油。']
  if flavor=='Strawberry': ingredients+=['草莓果酱、草莓浓缩汁。']
  elif flavor=='Orange': ingredients=['产品类型：冷冻饮品','配料：饮用水、白砂糖、橙汁、','食用葡萄糖、食品添加剂。']
  elif family=='ChocoBar': ingredients+=['巧克力脆皮、可可粉。']
  for t in ingredients+['过敏原信息：含乳及乳制品。','本品请勿反复解冻后食用。']:
   text(d,(w*.10,h*y),t,sc*.036,ink); y+=line
  table=(w*.10,h*.44,w*.90,h*.69)
  storageY=.73; barbox=(w*.22,h*.82,w*.78,h*.91)
 else:
  text(d,(w*.075,h*.075),title+'  '+flavortxt,sc*.062,ink,True)
  rows=['产品类型：冷冻饮品','配料：饮用水、牛乳、白砂糖、稀奶油、乳粉。','过敏原信息：含乳及乳制品。','食用提示：开封后请尽快食用。']
  if flavor=='Strawberry': rows[1]='配料：饮用水、牛乳、白砂糖、草莓果酱、乳粉。'
  for k,t in enumerate(rows): text(d,(w*.075,h*(.245+k*.10)),t,sc*.030,ink)
  table=(w*.56,h*.23,w*.91,h*.68)
  storageY=.73; barbox=(w*.68,h*.745,w*.91,h*.90)
 # Nutrition table uses real units but deliberately generic fictional values.
 x0,y0,x1,y1=table; rows=[('营养成分表',''),('项目','每 100 克'),('能量','850 kJ'),('蛋白质','3.2 g'),('脂肪','10.0 g'),('碳水化合物','25.0 g'),('钠','65 mg')]
 rh=(y1-y0)/len(rows); d.rectangle(table,outline=ink,width=2)
 for k,(a,b) in enumerate(rows):
  yy=y0+k*rh
  if k==0: d.rectangle((x0,yy,x1,yy+rh),fill=deep)
  elif k: d.line((x0,yy,x1,yy),fill=ink,width=1)
  text(d,(x0+(x1-x0)*.035,yy+rh*.17),a,min(sc*.038,rh*.52),(255,249,228) if k==0 else ink,k==0)
  if b: text(d,(x0+(x1-x0)*.61,yy+rh*.17),b,min(sc*.035,rh*.50),ink)
 sy=h*storageY
 for k,t in enumerate(['贮存条件：－18℃以下冷冻保存','保质期：12 个月','生产日期 / 批次：见封口喷码']):
  text(d,(w*.10 if aspect<1 else w*.075,sy+k*sc*.049),t,sc*.030,ink)
 barcode(d,barbox,sum(map(ord,flavor+family)))
 text(d,(w*.5,h*.932),'包装图案仅供识别 · 请按当地规定回收',sc*.024,ink,False,'mm')
 return finish(im,'back'+family+flavor)

def finish(im,key):
 # Subtle ink fade, stress at folds, fine scuffing: used grocery packaging.
 w,h=im.size; rng=np.random.default_rng(sum(map(ord,key)))
 lay=Image.new('RGBA',im.size); d=ImageDraw.Draw(lay)
 for x in [int(w*.025),int(w*.975)]:
  d.line((x,0,x,h),fill=(255,255,240,35),width=max(2,int(w*.004)))
  d.line((x+int(w*.006),0,x+int(w*.006),h),fill=(32,35,35,15),width=max(1,int(w*.002)))
 for _ in range(70):
  x=rng.uniform(0,w); y=rng.choice([rng.uniform(0,h*.04),rng.uniform(h*.96,h)])
  d.line((x,y,x+rng.uniform(2,w*.025),y+rng.uniform(-3,3)),fill=(255,249,224,55),width=1)
 im=Image.alpha_composite(im,lay)
 return im.convert('RGB')

def make_wafer():
 yy,xx=np.mgrid[0:SIZE,0:SIZE]; p=165
 a=np.mod(xx+yy,p); b=np.mod(xx-yy,p)
 dist=np.minimum(np.minimum(a,p-a),np.minimum(b,p-b))
 shade=.78+.22*np.minimum(dist/25,1)
 rng=np.random.default_rng(7)
 col=np.clip(np.array([210,154,83])[None,None,:]*shade[:,:,None]+rng.normal(0,1.7,(SIZE,SIZE,1)),0,255).astype('uint8')
 Image.fromarray(col).save(OUT/'T_Ice_Wafer_BaseColor.png')
 orm=np.zeros((SIZE,SIZE,3),np.uint8); orm[:,:,0]=np.clip(196+59*np.minimum(dist/18,1),0,255); orm[:,:,1]=220
 Image.fromarray(orm).save(OUT/'T_Ice_Wafer_ORM.png')

def main():
 manifest={'texture_size':[SIZE,SIZE],'v_order':'bottom-first','island_inset_px':8,'channels':{'BaseColor':'sRGB RGB','ORM':'linear: R ambient occlusion, G roughness, B metallic = 0'},'uv_rect_order':['u_min','v_min','u_max','v_max'],'families':{}}
 previews=[]
 for family,aspect,flavors in FAMILIES:
  atlas=Image.new('RGB',(SIZE,SIZE),(235,233,220)); orm=np.empty((SIZE,SIZE,3),np.uint8); orm[:]=[255,160,0]
  meta={'aspect':aspect,'base_color':f'T_Ice_{family}_BaseColor.png','orm':f'T_Ice_{family}_ORM.png','flavors':[]}
  for i,fl in enumerate(flavors):
   flavor,flavortxt,title,en,weight=fl
   ya=math.floor(SIZE*(1-(i+1)/len(flavors))); yb=math.floor(SIZE*(1-i/len(flavors)))
   entry={'index_bottom_first':i,'flavor':flavor,'flavor_label':flavortxt,'title':title,'band_v':[i/len(flavors),(i+1)/len(flavors)]}
   for side,xa,xb in [('front',0,SIZE//2),('back',SIZE//2,SIZE)]:
    art=(front if side=='front' else back)(family,aspect,*fl)
    rect=(xa+8,ya+8,xb-8,yb-8)
    atlas.paste(art.resize((rect[2]-rect[0],rect[3]-rect[1]),Image.Resampling.LANCZOS),rect[:2])
    # Bleed to raw band edges so gutter interpolation never exposes off-color.
    if side=='front':
     pd=ImageDraw.Draw(atlas)
     pd.rectangle((xa,ya,xb-1,ya+7),fill=art.getpixel((art.width//2,0)))
     pd.rectangle((xa,yb-8,xb-1,yb-1),fill=art.getpixel((art.width//2,art.height-1)))
    entry[side+'_pixel_rect_top_left']=list(rect)
    entry[side+'_uv_rect']=[rect[0]/SIZE,(SIZE-rect[3])/SIZE,rect[2]/SIZE,(SIZE-rect[1])/SIZE]
    rough=.65 if family in ['BoxIce','FamilyTub','CupIce'] else .43
    rng=np.random.default_rng(i+len(family)+(0 if side=='front' else 100))
    g=np.clip(255*rough+rng.normal(0,1.0,(rect[3]-rect[1],rect[2]-rect[0])),0,255).astype('uint8')
    orm[rect[1]:rect[3],rect[0]:rect[2],1]=g
    if side=='front': previews.append((family+' / '+flavor,art))
   meta['flavors'].append(entry)
  atlas.save(OUT/meta['base_color']); Image.fromarray(orm).save(OUT/meta['orm']); manifest['families'][family]=meta
 make_wafer()
 (OUT/'IcePackagingUV.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 # Restore physical panel aspect in a contact sheet: source atlas is packed.
 tw,th=720,820; sheet=Image.new('RGB',(tw*4,th*4),(227,229,228)); sd=ImageDraw.Draw(sheet)
 for i,(name,art) in enumerate(previews):
  x=(i%4)*tw; y=(i//4)*th
  text(sd,(x+22,y+17),name,25,(29,39,47),True)
  art.thumbnail((tw-40,th-80),Image.Resampling.LANCZOS)
  sheet.paste(art,(x+(tw-art.width)//2,y+60+(th-80-art.height)//2))
 sheet.save(OUT/'IcePackaging_ContactSheet.png')
 # Back proof separately, physical-aspect for food copy and barcodes.
 proof=Image.new('RGB',(1800,2400),(226,229,228)); pd=ImageDraw.Draw(proof)
 for i,(fam,aspect,flavors) in enumerate(FAMILIES):
  art=back(fam,aspect,*flavors[0]); art.thumbnail((850,700))
  x=(i%2)*900; y=(i//2)*800
  text(pd,(x+20,y+20),fam+' / back',25,(29,39,47),True)
  proof.paste(art,(x+(900-art.width)//2,y+65+(710-art.height)//2))
 proof.save(OUT/'IcePackaging_BackProof.png')
 print(json.dumps({'maps':14,'flavor_looks':len(previews),'output':str(OUT),'metadata':str(OUT/'IcePackagingUV.json')},ensure_ascii=False))

if __name__=='__main__': main()
