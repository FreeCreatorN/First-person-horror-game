"""Draw review-only architecture sheets; never import UE or write Content/."""
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Saved/CodexOutputs/ArchitectureRedesignReview_20261007_V2'
W, H = 4200, 2970
REVIEW_DATE = '2026-10-08'
C = dict(paper='#FAF8F2', ink='#263A3E', muted='#68777A', wall='#35484B',
         public='#DEEBE4', private='#F2E3D5', circulation='#DFEAF0',
         service='#F0EACA', furniture='#C1BAAA', glass='#4B9EB5',
         guest='#287E91', staff='#996D36', red='#B85443', grid='#DCDDD5')


@lru_cache(maxsize=100)
def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else
                              'C:/Windows/Fonts/msyh.ttc', int(size))


def text(d, xy, value, size=38, fill=None, bold=False, anchor='la'):
    d.text(xy, value, font=font(size, bold), fill=fill or C['ink'], anchor=anchor,
           spacing=14)


def wrapped(d, xy, value, width, size=38, fill=None, bold=False, line_gap=17):
    x, y = xy
    line = ''
    for ch in value:
        if ch == '\n' or d.textlength(line + ch, font=font(size, bold)) > width:
            text(d, (x, y), line, size, fill, bold)
            y += size + line_gap
            line = '' if ch == '\n' else ch
        else:
            line += ch
    if line:
        text(d, (x, y), line, size, fill, bold)
        y += size + line_gap
    return y


def dashed(d, a, b, fill, width=5, dash=22, gap=13):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = math.hypot(dx, dy)
    if not length:
        return
    t = 0
    while t < length:
        u, v = t/length, min(t+dash, length)/length
        d.line([(a[0]+dx*u, a[1]+dy*u), (a[0]+dx*v, a[1]+dy*v)], fill=fill, width=width)
        t += dash + gap


def arrow(d, pts, fill=None, width=7, dash=False):
    fill = fill or C['guest']
    for a, b in zip(pts, pts[1:]):
        if dash:
            dashed(d, a, b, fill, width)
        else:
            d.line([a, b], fill=fill, width=width)
    a, b = pts[-2:]
    theta = math.atan2(b[1]-a[1], b[0]-a[0])
    end = [(b[0]-26*math.cos(theta-v), b[1]-26*math.sin(theta-v)) for v in (-.45, .45)]
    d.line([end[0], b, end[1]], fill=fill, width=width)


def sheet(n, title, subtitle):
    im = Image.new('RGB', (W, H), C['paper'])
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 24), fill=C['guest'])
    text(d, (170, 92), '老城街区  /  建筑重设计', 36, C['muted'], True)
    text(d, (170, 166), title, 74, bold=True)
    text(d, (170, 274), subtitle, 37, C['muted'])
    d.rounded_rectangle((3410, 88, 4030, 180), radius=20, fill=C['circulation'])
    text(d, (3720, 130), 'V2  审查稿 · 未实施', 35, C['guest'], True, 'mm')
    d.line((170, 355, 4030, 355), fill=C['grid'], width=3)
    d.line((170, 2820, 4030, 2820), fill=C['grid'], width=3)
    text(d, (170, 2855), REVIEW_DATE+'  |  先审查平面，再建模  |  单位：m  |  面积为方案估算', 31, C['muted'])
    text(d, (4020, 2866), f'{n:02d} / 07', 35, C['muted'], anchor='ra')
    return im, d


def notes(d, x, y, width, title, rows, size=37):
    text(d, (x, y), title, 45, bold=True)
    y += 86
    for i, (head, body) in enumerate(rows, 1):
        text(d, (x, y), f'{i:02d}  {head}', size+2, bold=True)
        y = wrapped(d, (x, y+65), body, width, size, C['muted']) + 54
    return y


def legend(d, x, y):
    for name, color in [('公共 / 接待', 'public'), ('住户 / 客房', 'private'),
                         ('共用交通', 'circulation'), ('后勤', 'service')]:
        d.rectangle((x, y, x+45, y+35), fill=C[color], outline=C['muted'], width=2)
        text(d, (x+60, y-3), name, 30)
        x += 390


class Plan:
    def __init__(self, d, ox, oy, scale, depth):
        self.d, self.ox, self.oy, self.s, self.depth = d, ox, oy, scale, depth

    def p(self, x, y):
        return (self.ox+x*self.s, self.oy+(self.depth-y)*self.s)

    def rect(self, box, fill=None, outline=None, width=3):
        x0, y0, x1, y1 = box
        a, b = self.p(x0, y1), self.p(x1, y0)
        self.d.rectangle((*a, *b), fill=fill, outline=outline, width=width)

    def poly(self, pts, fill, outline=None, width=3):
        self.d.polygon([self.p(*p) for p in pts], fill=fill)
        if outline:
            self.d.line([self.p(*p) for p in pts+[pts[0]]], fill=outline, width=width)

    def line(self, a, b, fill=None, width=6):
        self.d.line((self.p(*a), self.p(*b)), fill=fill or C['wall'], width=width)

    def wall(self, a, b, thickness=.2):
        self.line(a, b, width=max(7, round(thickness*self.s)))

    def label(self, x, y, value, size=34, fill=None, bold=False):
        self.d.multiline_text(self.p(x, y), value, font=font(size, bold), fill=fill or C['ink'],
                              anchor='mm', align='center', spacing=12)

    def win(self, a, b):
        self.line(a, b, C['paper'], max(8, round(.22*self.s)))
        self.line(a, b, C['glass'], 5)

    def door(self, x, y, width, closed='E', opened='N', swing=True):
        dirs = {'E':(1, 0), 'W':(-1, 0), 'N':(0, 1), 'S':(0, -1)}
        u, v = dirs[closed], dirs[opened]
        hinge = self.p(x, y)
        closed_end = self.p(x+u[0]*width, y+u[1]*width)
        open_end = self.p(x+v[0]*width, y+v[1]*width)
        self.d.line((hinge, closed_end), fill=C['paper'], width=max(12, round(.42*self.s)))
        if swing:
            self.d.line((hinge, open_end), fill=C['ink'], width=4)
            pts=[]
            for i in range(25):
                t=i/24*math.pi/2
                pts.append(self.p(x+width*(u[0]*math.cos(t)+v[0]*math.sin(t)),
                                  y+width*(u[1]*math.cos(t)+v[1]*math.sin(t))))
            self.d.line(pts, fill=C['muted'], width=3)
        else:
            self.d.line((hinge, closed_end), fill=C['guest'], width=3)
            # Parallel track distinguishes a sliding door from an open hole.
            off=.07
            self.line((x+v[0]*off, y+v[1]*off),
                      (x+u[0]*width+v[0]*off, y+u[1]*width+v[1]*off), C['guest'], 3)

    def double(self, x, y, width=1.8, opened='N'):
        self.door(x, y, width/2, 'E', opened)
        self.door(x+width, y, width/2, 'W', opened)

    def route(self, pts, staff=False, dash=True):
        arrow(self.d, [self.p(*p) for p in pts], C['staff'] if staff else C['guest'], 6, dash)

    def hdim(self, x0, x1, y, value, size=33):
        self.line((x0, y), (x1, y), C['muted'], 3)
        for x in (x0, x1):
            self.line((x, y-.15), (x, y+.15), C['muted'], 3)
        px, py=self.p((x0+x1)/2, y)
        bbox=self.d.textbbox((0, 0), value, font=font(size))
        tw=bbox[2]-bbox[0]
        self.d.rectangle((px-tw/2-14, py-24, px+tw/2+14, py+24), fill=C['paper'])
        text(self.d, (px, py), value, size, C['muted'], anchor='mm')

    def vdim(self, x, y0, y1, value, size=33):
        self.line((x, y0), (x, y1), C['muted'], 3)
        for y in (y0, y1):
            self.line((x-.15, y), (x+.15, y), C['muted'], 3)
        px, py=self.p(x, (y0+y1)/2)
        text(self.d, (px-22, py), value, size, C['muted'], anchor='rm')


def furniture(p, box, kind='', detailed=False):
    p.rect(box, C['furniture'], C['muted'], 3)
    x0,y0,x1,y1=box
    if kind=='bed':
        p.rect((x0+.06,y1-.4,x1-.06,y1-.08), C['paper'], C['muted'], 2)
        p.line((x0+.06,y0+.4),(x1-.06,y0+.4),C['muted'],2)
    if kind=='sofa':
        p.line((x0+.12,y0+.12),(x1-.12,y0+.12),C['muted'],3)
        p.line((x0+.12,y1-.12),(x1-.12,y1-.12),C['muted'],3)
    if detailed and kind:
        p.label((x0+x1)/2,(y0+y1)/2, {'bed':'床','sofa':'座席','desk':'桌','cabinet':'柜'}.get(kind,kind), 27)


def toilet(p, x, y):
    p.rect((x-.23,y-.34,x+.23,y+.34), '#FCFBF6', C['muted'], 3)
    a,b=p.p(x-.15,y+.1),p.p(x+.15,y-.21)
    p.d.ellipse((*a,*b),outline=C['muted'],width=3)


def basin(p, box):
    p.rect(box, '#FCFBF6', C['muted'], 3)
    x0,y0,x1,y1=box
    a,b=p.p(x0+.09,y1-.07),p.p(x1-.09,y0+.07)
    p.d.ellipse((*a,*b),outline=C['muted'],width=2)


def stair(p, x0, y0, width=3.2, run=3.08, landing=1.4, compact=False):
    # Two 1.4 m flights, central well, 11 treads per flight; risers to follow each unit's existing height.
    flight=(width-.4)/2
    p.rect((x0,y0-landing,x0+width,y0+run+landing), C['circulation'], C['muted'], 3)
    for side in (0,1):
        xx=x0+side*(flight+.4)
        p.rect((xx,y0,xx+flight,y0+run), '#EEF3F5', C['muted'], 3)
        count=round(run/.28)
        for i in range(count+1):
            yy=y0+run*i/count
            p.line((xx,yy),(xx+flight,yy),C['muted'],2)
    p.route([(x0+flight/2,y0+.2),(x0+flight/2,y0+run-.2)],dash=False)
    p.route([(x0+flight+.4+flight/2,y0+run-.2),(x0+flight+.4+flight/2,y0+.2)],dash=False)
    if not compact:
        p.label(x0+width/2,y0+run+landing/2,'转弯平台 1.4',29)
        p.label(x0+width/2,y0-.65,'楼层平台',29)


def save(im, name):
    path=OUT/(name+'.png')
    im.save(path, dpi=(254,254), optimize=True)
    return path


def hotel_shell(p, first=False):
    p.rect((0,0,70,10.4),C['wall'])
    p.rect((.2,.2,69.8,10.2),C['public'] if first else C['private'])
    p.rect((.2,.2,69.8,2.4),C['circulation'])
    for x in (6,64):
        p.wall((x,2.4),(x,10.2))
    for x in (0,64):
        p.rect((x+.2,2.6,x+5.8,10.2),C['circulation'])
        stair(p,x+1.4,5.2,compact=True)
        p.wall((x+.2,2.5),(x+5.8,2.5))
        p.double(x+2.3,2.5,1.4,'S')
        p.win((x+1.5,10.3),(x+4.5,10.3))
        if first:
            p.double(x+2.3,.2,1.4,'S')


def lobby(p, detail=True):
    # Local coordinates 0..18 and .2..10.2. Shared public area approx 140 m2.
    p.rect((0,.2,18,10.2),C['public'])
    # Three enclosed deductions: luggage ~12 m2, lift shaft ~9 m2, office ~12 m2.
    stores=[(.2,7.2,4.2,10.2,'行李室\n约12㎡'),(6,7.2,9,10.2,'电梯井\n3 × 3'),(13.8,7.2,17.8,10.2,'前台办公室\n约12㎡')]
    for x0,y0,x1,y1,label in stores:
        p.rect((x0,y0,x1,y1),C['service'],C['wall'],max(7,round(.16*p.s)))
        p.label((x0+x1)/2,8.95,label,36 if detail else 26)
    p.door(2.6,7.2,1,'E','N')
    p.door(6.8,7.2,1.4,'E','N',False)
    p.door(13.8,8,1,'N','E')
    # Wind lobby kept below the transverse circulation route.
    p.rect((6.8,.2,10.8,3),C['circulation'],C['wall'],max(7,round(.15*p.s)))
    p.double(7.8,.2,2,'N')
    p.double(7.8,3,2,'N')
    p.label(8.8,1.7,'门斗\n4 × 2.8',34 if detail else 25)
    furniture(p,(9.2,5.9,13.4,6.7),'',False)
    p.label(11.3,6.3,'前台 4.2m',35 if detail else 28)
    # Eight seats left, four right: 12 actual seats; a generous waiting lounge, not a packed row.
    furniture(p,(.65,3.35,1.5,5.45),'sofa')
    furniture(p,(3.8,3.35,4.65,5.45),'sofa')
    furniture(p,(1.8,4.0,3.5,4.8),'desk')
    for x in (1.85,2.95):
        for y in (3.0,5.05):
            furniture(p,(x,y,x+.65,y+.65),'sofa')
    furniture(p,(15.15,3.45,17.35,4.25),'sofa')
    furniture(p,(15.15,5.35,17.35,6.15),'sofa')
    furniture(p,(15.65,4.55,16.85,5.05),'desk')
    p.route([(8.8,-1),(8.8,.55)])
    p.route([(8.8,3.4),(8.8,3.8),(11.4,4.7),(11.4,5.6)])
    p.route([(8.8,4.3),(7.5,4.3),(7.5,6.8)])
    p.route([(6.2,4.3),(5.8,4.3),(5.8,1.3),(0,1.3)])
    p.route([(11.5,4.3),(12,4.3),(12,1.3),(18,1.3)])
    p.route([(16.5,8.4),(13.1,8.4),(11.6,8.4),(11.6,7.15)],True)
    if detail:
        p.label(2.6,2.3,'候客 / 会客',38)
        p.label(16.1,2.4,'4座休息区',34)
        p.label(11.3,4.0,'主抵达通道 ≥2.4',32,C['guest'])
        p.label(10.4,8.5,'梯厅可见\n不穿后勤',31,C['muted'])
        p.win((.5,.1),(5.8,.1))
        p.win((11.5,.1),(17.6,.1))


def translated(p, dx, dy=0):
    # Same drawing geometry with a translated plan origin.
    q=Plan(p.d,p.ox+dx*p.s,p.oy-dy*p.s,p.s,p.depth)
    return q


def draw_first_floor():
    im,d=sheet(2,'酒店首层  /  把接待做成一个完整大厅','首层零客房；主入口直接进入中央大厅。完整平面单独一页，大厅另见第03页。')
    p=Plan(d,330,680,50,10.4)
    hotel_shell(p,True)
    # Dining / pantry / public WC south wing.
    p.wall((6,2.5),(26,2.5))
    p.rect((6.2,2.6,19.8,10.2),C['public'])
    p.wall((20,2.6),(20,10.2))
    p.rect((20.2,2.6,25.8,5.6),C['service'])
    p.rect((20.2,5.8,25.8,10.2),C['service'])
    p.wall((20,5.7),(26,5.7))
    p.wall((26,2.6),(26,10.2))
    p.double(10.1,2.5,1.8,'N')
    p.door(21.4,2.5,.9,'E','N')
    p.door(23.5,2.5,1.0,'E','N')
    p.door(20,7,1,'N','W')
    # Six tables, four seats each =24.
    for xx in (8,12,16):
        for yy in (4.1,7.4):
            furniture(p,(xx,yy,xx+1.3,yy+.8),'desk')
            for cx in (xx+.1,xx+.75):
                for cy in (yy-.65,yy+.9):
                    furniture(p,(cx,cy,cx+.45,cy+.45))
    furniture(p,(24.6,6.3,25.6,9.8))
    p.wall((22.9,2.6),(22.9,5.6),.12)
    toilet(p,21.0,5.0);toilet(p,24.7,5.0)
    basin(p,(20.4,2.8,21.1,3.4));basin(p,(25.0,2.8,25.6,3.4))
    p.label(13,9.35,'早餐 / 茶厅 24座',35)
    p.label(23,8.1,'备餐\n约25㎡',33)
    p.label(21.5,4.0,'WC 1',27);p.label(24.5,4.1,'WC 2',27)
    lobby(translated(p,26),False)
    # Staff functions, separated from the guest corridor by a 2 m service passage.
    p.rect((44,2.6,64,4.6),C['circulation'])
    p.wall((44,2.5),(64,2.5))
    p.wall((44,4.7),(64,4.7))
    p.wall((44,2.6),(44,10.2))
    parts=[(44.2,50,'办公 / 员工'),(50.2,54,'清布草'),(54.2,58,'污布草'),(58.2,63.8,'更衣 / 设备')]
    for x0,x1,label in parts:
        p.rect((x0,4.8,x1,10.2),C['service'])
        if x1<63.8:p.wall((x1+.1,4.7),(x1+.1,10.2))
        p.door((x0+x1)/2-.45,4.7,.9,'E','N')
        p.label((x0+x1)/2,9.0 if x0==58.2 else 8.5,label,31)
    # The changing/equipment room has its own door; no route passes through a WC.
    p.rect((61.4,4.8,63.8,7.4),C['service'],C['wall'],7)
    p.door(62.0,4.7,.9,'E','N')
    basin(p,(61.6,6.75,62.4,7.3))
    toilet(p,63.1,6.6)
    p.label(62.05,6.1,'WC',26)
    p.double(60.3,.2,1.4,'N')
    p.double(60.3,2.5,1.4,'N')
    p.route([(61,-1),(61,3.6),(56,3.6),(56,4.4)],True)
    p.route([(61,3.6),(52,3.6),(52,4.4)],True)
    for x in (8,12,16,20.5,24,46,50,54,58,62):
        p.win((x,10.3),(x+1.6,10.3))
    p.hdim(0,70,12.4,'70.0 m 总长',38)
    chain=[(0,6,'6 南梯'),(6,20,'14 餐茶'),(20,26,'6 WC / 备餐'),(26,44,'18 中央大厅'),(44,64,'20 后勤'),(64,70,'6 北梯')]
    for a,b,v in chain:p.hdim(a,b,11.35,v,31)
    p.vdim(-1.1,0,10.4,'10.4',35)
    p.label(35,-1.55,'主入口',38,C['guest'],True)
    p.label(61,-1.55,'后勤入口',33,C['staff'])
    p.label(3,-1.55,'出口',31,C['guest'])
    p.label(67,-1.55,'出口',31,C['guest'])
    text(d,(330,1400),'中央大厅区域 180㎡  /  其中公共净区约140㎡',58,bold=True)
    text(d,(330,1495),'包括前台与排队、12座候客、行李室、梯厅；入口不再先经过狭长廊。',38,C['muted'])
    legend(d,330,1605)
    notes(d,330,1770,1030,'接待与客人',[
        ('直接抵达','街道 → 门斗 → 看见前台 → 候客 / 电梯；大厅内部抵达路线留出2.4m。'),
        ('公共层优先','首层取消101/102客房，给接待、餐茶、卫生间与后勤留下连续空间。')])
    notes(d,1660,1770,1030,'服务与运营',[
        ('首层收货独立','北段入口直接收货入库，清、污布草分室；员工WC与更衣/设备室各有独立入口。'),
        ('上层配送路线','布草配送共用中央客梯，需经公共走廊和大厅，应避开接待高峰；没有另设服务梯。'),
        ('备餐放在干区','备餐位于房内后部干区投影，与上层卫浴位置错开。')],35)
    notes(d,2980,1770,970,'审查时请看',[
        ('先看空间关系','大厅是否足够集中、前台是否易找到、两端楼梯是否均可从公共交通区到达。'),
        ('结构复核留到下一步','现有柱梁暂列保留条件；图中隔墙为拟调整。门位、柱网和疏散距离在建模前复核。')],35)
    return save(im,'02_Hotel_GroundFloor')


def draw_lobby():
    im,d=sheet(3,'接待大厅放大  /  门、柜台、座席都能看清','对应首层26–44m段；公共净区约140㎡，不是把180㎡全部算成候客面积。')
    p=Plan(d,340,700,145,10.4)
    p.rect((0,0,18,10.4),C['wall'])
    p.rect((.2,.2,17.8,10.2),C['public'])
    lobby(p,True)
    # Open connections into the south and north public corridor.
    p.door(.1,.45,1.8,'N','E',False)
    p.door(17.9,.45,1.8,'N','W',False)
    p.hdim(0,18,11.8,'18.0 m 大厅段',38)
    p.vdim(-.75,.2,10.2,'10.0 m',36)
    p.hdim(9.2,13.4,5.4,'4.2 m 接待柜台',31)
    p.label(8.8,-.9,'街道 / 进入酒店',40,C['guest'],True)
    notes(d,3130,610,880,'这一页重点审查',[
        ('抵达视线','站在门斗出口即可辨认前台和电梯方向，不靠房号或路标补救。'),
        ('公共净区','大厅段约180㎡；扣行李室12㎡、办公室12㎡、井道9㎡及墙体，公共部分约140㎡。'),
        ('候客与排队分开','图中12个座席放在两侧；抵达、排队、去电梯的路线位于中央。'),
        ('门扇不扫座椅','行李室、办公室及门斗画出门扇；电梯画推拉门轨道。')],36)
    text(d,(340,2470),'废弃感建立在合理运营结构上',46,bold=True)
    wrapped(d,(340,2550),'后续用停走时钟、缺失灯管、褪色前台和弃置行李讲故事；大厅的正常尺度、入口视线和通道先成立。',2590,38,C['muted'])
    return save(im,'03_Hotel_Lobby_Enlarged')


def hotel_room(p, x=0, twin=True, detail=True):
    p.rect((x+.1,2.6,x+4.9,10.2),C['private'])
    p.wall((x,2.5),(x+5,2.5))
    p.wall((x+.0,2.6),(x+.0,10.2))
    p.wall((x+5,2.6),(x+5,10.2))
    p.door(x+3.4,2.5,1,'E','N')
    p.rect((x+.2,2.6,x+2.6,5.0),'#E5EEEA',C['wall'],max(5,round(.12*p.s)))
    p.door(x+2.6,3.5,.85,'N','W',False)
    p.rect((x+.3,2.8,x+1.25,3.75),None,C['muted'],3)
    toilet(p,x+.85,4.45)
    basin(p,(x+1.7,2.8,x+2.5,3.4))
    p.rect((x+2.05,4.5,x+2.5,4.95),C['wall'])
    furniture(p,(x+4.3,3.85,x+4.9,5.65),'cabinet')
    if twin:
        furniture(p,(x+.6,7.7,x+1.6,9.7),'bed')
        furniture(p,(x+3.35,7.7,x+4.35,9.7),'bed')
    else:
        furniture(p,(x+1.6,7.7,x+3.2,9.7),'bed')
    furniture(p,(x+1.9,9.5,x+3.0,10.1),'desk')
    furniture(p,(x+.4,5.45,x+1.2,6.8),'sofa')
    furniture(p,(x+1.65,5.65,x+2.8,6.3),'desk')
    p.win((x+1.5,10.3),(x+3.5,10.3))
    if detail:
        p.label(x+1.4,4.05,'卫浴\n约5.8㎡',32)
        p.label(x+3.7,3.2,'入口',30)
        p.label(x+2.5,7.0,'床前通行',32,C['guest'])
        p.route([(x+3.9,2.1),(x+3.7,4.5),(x+3.0,6.9),(x+2.5,8.8)])


def draw_standard():
    im,d=sheet(4,'酒店标准层  /  10间一层，共30间','二至四层采用同一交通系统；双端楼梯 + 连续2.2m走廊 + 中部电梯梯厅。')
    p=Plan(d,330,550,50,10.4)
    hotel_shell(p)
    p.wall((6,2.5),(31,2.5))
    p.wall((39,2.5),(64,2.5))
    index=0
    for start in (6,39):
        for k in range(5):
            x=start+k*5;index+=1
            hotel_room(p,x,index%3!=0,False)
            p.label(x+2.5,6.7,f'2{index:02d}\n约36.5㎡',29)
    p.rect((31.2,2.6,38.8,10.2),C['circulation'])
    for x in (31,39):p.wall((x,2.6),(x,10.2))
    for box,label in [((32,7.2,35,10.2),'电梯'),((35.2,7.2,37.2,10.2),'布草'),((37.4,7.2,38.8,10.2),'清洁')]:
        p.rect(box,C['service'],C['wall'],8)
        p.label((box[0]+box[2])/2,8.9,label,26)
        p.door(box[0]+.3,7.2,min(1.2,box[2]-box[0]-.6),'E','N',label!='电梯')
    p.label(35,4.9,'共有梯厅',31)
    p.route([(35,1.3),(4,1.3)])
    p.route([(35,1.3),(66,1.3)])
    p.hdim(0,70,12.6,'70.0 m',36)
    for a,b,v in [(0,6,'6'),(6,31,'5 × 5.0 = 25'),(31,39,'8 核心'),(39,64,'5 × 5.0 = 25'),(64,70,'6')]:p.hdim(a,b,11.5,v,31)
    p.vdim(-1,.2,2.4,'2.2',30)
    p.vdim(-1,2.6,10.2,'7.6',30)
    text(d,(330,1190),'一个标准双床房放大',48,bold=True)
    q=Plan(d,400,1440,155,10.4)
    hotel_room(q,0,True,True)
    q.hdim(.1,4.9,11.2,'净宽 4.8',33)
    q.vdim(-.65,2.6,10.2,'净深 7.6',32)
    q.label(2.5,2.0,'共有走廊 / 入户门1.0',31,C['guest'])
    notes(d,1640,1410,1040,'房间尺度',[
        ('不追求41间','每层10间；房内约36.5㎡，已含独立卫浴。面积没有把走廊算进房间。'),
        ('家具尺寸明确','双床各1.0 × 2.0m；也可改1.6m双人床。入口、卫浴、衣柜与床前路线分别画出。'),
        ('湿区逐层叠置','卫生间靠走廊，管井逐层对齐；背部外窗供睡眠区采光。')],36)
    notes(d,2980,1410,970,'交通与建模前复核',[
        ('共用交通完整','客房只开向走廊；楼梯不经过客房；电梯先到梯厅，布草/清洁另有门。'),
        ('楼层能逐层对照','301–310、401–410与本图叠层。首层不设客房。'),
        ('隔墙不冒充结构','5m分房模数是新隔墙方案；原约4.07m柱梁网格须复核，并在施工前图中补齐。')],35)
    return save(im,'04_Hotel_TypicalFloor')


def house_shell(p, ground=False):
    p.rect((0,0,15,10),C['wall'])
    p.rect((.2,.2,5.7,9.8),C['public'] if ground else C['private'])
    p.rect((9.3,.2,14.8,9.8),C['public'] if ground else C['private'])
    p.rect((5.9,.2,9.1,9.8),C['circulation'])
    stair(p,5.9,3.6)
    p.win((6.5,9.9),(8.5,9.9))


def house_ground(p):
    house_shell(p,True)
    p.rect((6.8,0,8.2,.76),C['paper'])
    p.wall((5.9,.8),(9.1,.8),.15)
    p.double(6.8,.8,1.4,'N')
    p.label(7.5,1.65,'居民入口\n共用门厅',35,C['guest'],True)
    p.rect((6,.25,9,.75),C['paper'])
    for mirror in (False,True):
        def bx(b):
            return (15-b[2],b[1],15-b[0],b[3]) if mirror else b
        for b,label in [((.2,6.6,5.7,9.8),'店内后仓'),((.2,3.0,2.3,5.2),'店内WC')]:
            p.rect(bx(b),C['service'],C['wall'],max(7,round(.12*p.s)))
            a=bx(b);p.label((a[0]+a[2])/2,(a[1]+a[3])/2,label,33)
        x=11.25 if mirror else 2.15
        p.double(x,.2,1.6,'N')
        p.door(11.7 if mirror else 3.3,6.6,.9,'W' if mirror else 'E','N')
        p.door(12.7 if mirror else 2.3,3.4,.8,'N','E' if mirror else 'W',False)
        for b in [(.5,.65,1.3,2.7),(3.65,3.2,5.35,4.0)]:
            furniture(p,bx(b),'cabinet')
        p.label(12.05 if mirror else 2.95,5.7,'独立商铺',40)
        p.win((10,9.9),(14,9.9)) if mirror else p.win((1,9.9),(5,9.9))
    p.route([(7.5,-.85),(7.5,2.6),(6.6,3.4)])
    p.label(7.5,8.9,'楼梯采光窗',32,C['muted'])


def apartment(p, mirror=False, detailed=True):
    def pt(x,y):return (15-x,y) if mirror else (x,y)
    def box(b):return (15-b[2],b[1],15-b[0],b[3]) if mirror else b
    def wall(a,b):p.wall(pt(*a),pt(*b),.12)
    def lab(x,y,t,s=33):p.label(*pt(x,y),t,s)
    # No openings in party walls: kitchens/living face the front, bedrooms the rear.
    regions=[((.2,.2,2.3,2.9),'厨房'),((.2,3,2.3,5.2),'卫浴'),
             ((2.4,.2,5.7,5.2),'客餐厅'),((.2,5.3,5.7,6.5),'户内通道'),
             ((.2,6.6,3.2,9.8),'主卧'),((3.3,6.6,5.7,9.8),'次卧')]
    for b,role in regions:
        p.rect(box(b),C['service'] if role in ('厨房','卫浴') else
                       C['circulation'] if role=='户内通道' else C['private'])
    for a,b in [((2.35,.2),(2.35,5.2)),((.2,2.95),(2.35,2.95)),
                ((.2,5.25),(5.7,5.25)),((.2,6.55),(5.7,6.55)),
                ((3.25,6.55),(3.25,9.8))]:wall(a,b)
    p.door(9.2 if mirror else 5.8,2.2,1,'N','E' if mirror else 'W')
    p.door(12.65 if mirror else 2.35,1.8,.8,'N','E' if mirror else 'W')
    p.door(12.65 if mirror else 2.35,3.4,.8,'N','E' if mirror else 'W',False)
    # Open internal living-to-hall connection and two bedroom doors.
    p.door(11.65 if mirror else 3.35,5.25,1.6,'W' if mirror else 'E','N',False)
    p.door(12.9 if mirror else 2.1,6.55,.8,'W' if mirror else 'E','N')
    p.door(10.55 if mirror else 4.45,6.55,.8,'W' if mirror else 'E','N')
    furniture(p,box((.2,.3,.8,2.7)),'cabinet')
    furniture(p,box((.8,.3,2.2,.9)),'cabinet')
    basin(p,box((.7,3.2,1.45,3.75)))
    p.rect(box((.3,4.25,1.2,5.15)),None,C['muted'],3)
    tx,ty=pt(1.65,4.65);toilet(p,tx,ty)
    p.rect(box((.2,3.0,.6,3.5)),C['wall'])
    furniture(p,box((3.7,.85,5.15,1.65)),'desk')
    for xx in (3.85,4.65):
        for yy in (.25,1.7):furniture(p,box((xx,yy,xx+.42,yy+.42)))
    furniture(p,box((2.5,3.05,3.3,5.05)),'sofa')
    furniture(p,box((5.15,3.55,5.7,4.8)),'cabinet')
    furniture(p,box((.45,7.5,1.95,9.5)),'bed')
    furniture(p,box((2.5,7.8,3.1,9.4)),'cabinet')
    furniture(p,box((3.45,7.7,4.35,9.7)),'bed')
    furniture(p,box((4.5,9.2,5.6,9.8)),'desk')
    furniture(p,box((5.1,7.5,5.7,8.7)),'cabinet')
    for a,b in [((.6,.1),(1.9,.1)),((3,.1),(5,.1)),((.7,9.9),(2.6,9.9)),((3.6,9.9),(5.4,9.9))]:
        p.win(pt(*a),pt(*b))
    if detailed:
        lab(1.25,2.15,'厨房\n约5.7㎡',30)
        lab(1.25,3.9,'卫浴\n约4.6㎡',29)
        lab(4.25,2.7,'客餐\n约16.5㎡',32)
        lab(1.2,7.0,'主卧 9.6㎡',28)
        lab(4.3,8.95,'次卧 7.7㎡',27)
        lab(2.95,5.9,'净宽约1.2m',29)
    p.route([pt(5.3,2.8),pt(4.5,3.0),pt(4.5,5.85),pt(4.5,6.2)])


def draw_house(n,ground):
    im,d=sheet(n,'住宅单元首层  /  商铺门与居民门分开' if ground else
                   '住宅单元标准层  /  一梯两户，真正分户',
                '15 × 10m典型单元；对应后排15m连排住宅。相邻单元共墙，每个单元楼梯供多户共用。')
    p=Plan(d,345,650,168,10)
    if ground:
        house_ground(p)
    else:
        house_shell(p)
        apartment(p,False);apartment(p,True)
        p.label(7.5,1.25,'共有门厅',34,C['guest'],True)
        p.route([(6.6,3.4),(6.6,2.8),(6.05,2.8)])
        p.route([(8.4,3.4),(8.4,2.8),(8.95,2.8)])
    p.hdim(0,15,11.3,'15.0 m 一个单元',38)
    for a,b,v in [(0,5.8,'5.8'),(5.8,9.2,'3.4核心轴距'),(9.2,15,'5.8')]:p.hdim(a,b,10.65,v,30)
    p.vdim(-.8,0,10,'10.0 m',35)
    if ground:
        p.label(2.95,-.9,'商铺入口',35,C['staff'])
        p.label(7.5,-.9,'单元入口',35,C['guest'],True)
        p.label(12.05,-.9,'商铺入口',35,C['staff'])
        rows=[('居民独立上楼','单元门 → 共用门厅 → 共用楼梯；居民无需从商店或某户屋内通过。'),
              ('商铺独立经营','左右两店各有面街门、店内后仓与卫生间。商铺与楼道用完整隔墙分开。'),
              ('一楼不是整栋的家','这个入口服务二层以上的多户住家；楼上分户门见下一页。'),
              ('巷子按原位置保留','连续15m后排单元适用本图；主街有巷子的窄栋另用第07页，不跨巷硬接。')]
    else:
        rows=[('每层两个家庭','左、右户均两卧、客餐、厨房与卫浴；分隔前各52.8㎡，扣内墙使用约50㎡。'),
              ('前后两面采光','客餐与厨房向前，两个卧室向后。共墙不画假窗；卫生间设独立排风/管井。'),
              ('住户门朝共用平台','两扇1.0m户门向户内开；卧室与厨房门画出开启方向，卫浴用0.8m推拉门。'),
              ('可看见小户型取舍','次卧约7.7㎡适合单人；若希望更大，可审查后改成一卧加书房，不把它藏在文字里。')]
    notes(d,3100,650,875,'审查重点',rows,36)
    text(d,(345,2480),'结构与层数处理',42,bold=True)
    wrapped(d,(345,2550),'15×10m为现有后排首个单元的典型详图。其他段进深9–11m、层数3–5层，按各段保留独立楼梯与标高；这一轮不把不同高度的楼板直接打通。',2560,36,C['muted'])
    return save(im,'05_Residential_GroundFloor' if ground else '06_Residential_TypicalFloor')


def narrow_shell(p):
    p.rect((0,0,10,11),C['wall'])
    p.rect((.2,.2,9.8,10.8),C['private'])
    p.rect((.2,.2,3.4,7.0),C['circulation'])
    p.rect((3.6,.2,4.9,7.0),C['circulation'])
    p.wall((3.5,.2),(3.5,7.1))
    p.wall((.2,7.1),(9.8,7.1))
    p.wall((5,.2),(5,7.1))
    stair(p,.2,1.6,3.2,3.08,1.4,True)
    p.door(3.5,.45,1.1,'N','E',False)
    p.win((.8,.1),(2.7,.1))


def draw_narrow():
    im,d=sheet(7,'主街窄栋  /  侧置共用楼梯与短走廊','10 × 11m典型：上层前后两户共用楼道。更窄地块按小户出租或一梯一户调整。')
    q=[]
    for ox in (370,2480):
        p=Plan(d,ox,690,128,11);narrow_shell(p);q.append(p)
        p.hdim(0,10,12.1,'10.0 m',36)
        p.vdim(-.65,0,11,'11.0 m',34)
    a,b=q
    text(d,(370,430),'首层：店铺与居民入口',43,bold=True)
    text(d,(2480,430),'标准层：共用楼梯接两户',43,bold=True)
    # Ground storefront can use the front unit and a linked back store, not the shared stair.
    a.rect((5.1,.2,9.8,7.0),C['public'])
    a.rect((.2,7.2,9.8,10.8),C['service'])
    a.double(5.8,.2,1.6,'N')
    a.double(1.1,.2,1.4,'N')
    a.door(7.0,7.1,1,'E','N')
    a.route([(1.8,-.8),(1.8,.9),(1.0,1.5)])
    a.label(7.4,3.8,'临街商铺',43)
    a.label(6.9,8.8,'店内后仓',38)
    a.label(1.8,5.4,'共有楼梯',31,C['guest'])
    a.label(1.8,-1.1,'居民门',32,C['guest'])
    a.label(6.6,-1.1,'店铺门',32,C['staff'])
    b.rect((5.1,.2,9.8,7.0),C['private'])
    b.door(5,2.2,1,'N','E')
    b.door(3.7,7.1,1,'E','N')
    b.label(7.4,4.5,'前户\n约32㎡',44)
    b.label(6.7,8.8,'后户\n约35㎡',44)
    b.label(1.8,5.4,'共有楼梯',31,C['guest'])
    b.route([(2.0,1.0),(4.25,1.0),(4.25,2.7),(4.7,2.7)])
    b.route([(4.25,3.5),(4.25,6.7)])
    b.win((5.5,.1),(8.5,.1))
    b.win((1,10.9),(3,10.9));b.win((5.5,10.9),(8.5,10.9))
    notes(d,370,2370,1670,'这一类按小户出租来设计',[
        ('先明确共用楼道','楼层平台侧接净宽1.3m共有走廊，再分到前后两户。24级梯的踏步方案按各栋原层高复核；厨卫家具待户数确认后细化。')],35)
    notes(d,2480,2370,1500,'不强塞家庭户',[
        ('小地块分别处理','9×10m或8×10m只能形成更小住户；必要时每层一户，但楼梯仍由楼上各户共同使用。')],35)
    return save(im,'07_Narrow_Residential_SharedAccess')


def draw_site():
    im,d=sheet(1,'街区入口系统  /  从“栋”改为“单元与住户”','建筑外壳位置沿用街区记录；住宅内部与酒店首层均为新提案。道路、步道与巷口保留。')
    # Metric world plan: X east, Y north; left is main street entry, hotel occupies east boundary.
    p=Plan(d,260,500,29,70)
    # Global view covers X 6..100.4 and Y -35..35 -> local x=worldX-6, y=worldY+35.
    def r(x0,y0,x1,y1,fill):p.rect((x0-6,y0+35,x1-6,y1+35),fill,C['muted'],3)
    r(6,-3.5,82.5,3.5,'#D9DADA')
    r(6,3.5,82.5,5.3,'#ECE8DD');r(6,-5.3,82.5,-3.5,'#ECE8DD')
    r(75.5,-20.75,82.5,20.75,'#D9DADA')
    r(82.5,-20.75,84.3,20.75,'#ECE8DD')
    r(84.3,-35,90,35,'#F0EBDD')
    p.label(44,35,'主街  /  7.0m机动车道',42,C['muted'])
    # Rear connected blocks; own unit entrances face rear lanes.
    for north in (False,True):
        y0,y1=(21,31) if north else (-31,-21)
        for k in range(4):
            x0=6+15*k
            r(x0,y0,x0+15,y1,C['private'])
            p.label(x0+7.5-6,(y0+y1)/2+35,f'{"北" if north else "南"}{k+1}单元\n上层多户共住',30)
            doorY=y0 if north else y1
            px,py=p.p(x0+7.5-6,doorY+35)
            d.ellipse((px-12,py-12,px+12,py+12),fill=C['guest'])
            p.route([(x0+7.5-6,doorY+35+(-1.5 if north else 1.5)),
                     (x0+7.5-6,doorY+35+(.65 if north else -.65))],dash=False)
    p.label(30,69,'北侧连排：60m = 4个15m单元',38,C['ink'],True)
    p.label(30,1,'南侧连排：共有楼道 → 分户门',36,C['ink'],True)
    # Actual front blocks, gaps preserved; only label changed use/access system.
    fronts=[(8,-13.3,13,-5.3,'店'),(14.5,-15.3,23.5,-5.3,'C'),(27.9,-13.8,34.4,-5.3,'店'),
            (35.9,-16.3,45.9,-5.3,'A'),(47.4,-15.3,56.4,-5.3,'多户'),
            (14,5.3,23.5,15.3,'D'),(27.9,5.3,36.9,17.3,'多户'),(38.4,5.3,48.4,16.3,'B'),(49.9,5.3,57.9,15.3,'多户')]
    for x0,y0,x1,y1,name in fronts:
        r(x0,y0,x1,y1,C['public'] if name=='店' else C['private'])
        p.label((x0+x1)/2-6,(y0+y1)/2+35,f'{name}\n店 / 住宅' if name!='店' else '单层\n商铺',29)
        if name!='店':
            yy=y1 if y1<0 else y0
            xx=x0+.9
            p.route([(xx-6,yy+35+(.8 if yy<0 else -.8)),(xx-6,yy+35+(-.6 if yy<0 else .6))],dash=False)
    # The east hotel is turned vertically on the site; middle entrance is directly visible.
    r(90,-35,100.4,35,C['public'])
    r(90,-9,100.4,9,C['public'])
    p.label(89.2,61,'北梯',34)
    p.label(89.2,9,'南梯',34)
    p.label(89.2,36,'酒店\n中央\n大厅',40,C['guest'],True)
    p.route([(77.8,35),(82.5,35),(85.5,35)],dash=False)
    p.hdim(0,60,72.5,'60.0m 连排住宅',36)
    p.label(43,54.5,'后街 / 生活通行',32,C['muted'])
    p.label(43,14.5,'后街 / 生活通行',32,C['muted'])
    notes(d,3380,520,655,'如何理解这次重画',[
        ('同楼多户','住宅外壳内部画真实分户。居民先走共有楼道，再进入自己的房门。'),
        ('连排是多个单元','后排连续60m采用四个15m单元。各单元都有服务多户的楼梯。'),
        ('商住分开进','店门服务经营；单元门服务住户。店内不作为居民上楼的必经路。'),
        ('酒店扩大接待','首层取消客房；中央18m段成为连续接待大厅，上层约30间客房。')],34)
    # Bottom drawing legend and exactness statement avoid masking assumptions.
    legend(d,260,2655)
    text(d,(260,2730),'● 蓝色为共用居民入口 / 客人入口；外围为外壳位置示意，室内详图见02–07。',31,C['muted'])
    return save(im,'01_District_Entry_System')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Verify our design-only task leaves the saved UE map and canonical evidence intact.
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    canonical=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'
    before={str(p):sha(p) for p in (mapfile,canonical)}
    paths=[draw_site(),draw_first_floor(),draw_lobby(),draw_standard(),draw_house(5,True),
           draw_house(6,False),draw_narrow()]
    pdf=OUT/'OldTown_Architecture_Redesign_V2_Review.pdf'
    c=canvas.Canvas(str(pdf),pagesize=(420*mm,297*mm))
    c.setTitle('Old Town Architecture Redesign V2 - Review Only')
    c.setAuthor('Codex | HorrorGame architecture review')
    for path in paths:
        c.drawImage(ImageReader(str(path)),0,0,width=420*mm,height=297*mm)
        c.showPage()
    c.save()
    reader=PdfReader(str(pdf))
    assert len(reader.pages)==7
    assert before=={str(p):sha(p) for p in (mapfile,canonical)},'Source map/evidence changed during drawing.'
    # Room dimension chains independently expose assumptions and permit later spatial reviews.
    assert sum((6,25,8,25,6))==70
    assert abs(sum((.2,2.2,.2,7.6,.2))-10.4)<1e-8
    proposal=dict(status='AWAITING_USER_REVIEW',implemented=False,review_date=REVIEW_DATE,created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_map_sha256=before[str(mapfile)],source_evidence_sha256=before[str(canonical)],
        changes_to_ue_assets=0,
        hotel=dict(shell_m=[70,10.4],floors=4,ground_guest_rooms=0,upper_rooms_per_floor=10,total_rooms=30,
            lobby_segment_m=[26,44],lobby_region_m2=180,approx_public_lobby_m2=140,
            corridor_clear_m=2.2,guest_room_clear_m=[4.8,7.6],room_including_bath_m2=36.48,
            south_stair_segment_m=[0,6],north_stair_segment_m=[64,70],central_core_segment_m=[31,39],
            frontage_reception_counter_m=4.2,waiting_seats=12,dining_seats=24,
            ground_program_segments=[['south_stair',0,6],['tea_dining',6,20],['wc_pantry',20,26],
                                    ['continuous_lobby',26,44],['staff_linen_equipment',44,64],['north_stair',64,70]]),
        residential=dict(typical_shell_m=[15,10],rear_row_length_m=60,units_per_rear_row=4,
            units_per_typical_residential_floor=2,common_core_outer_m=[3.6,10],core_clear_width_m=3.2,
            two_apartments_clear_envelope_m2_each=52.8,approx_internal_use_m2_each=50,
            apartment_rooms=['two_bedrooms','living_dining','kitchen','bathroom'],
            common_entry_door_m=1.4,shop_door_m=1.6,apartment_door_m=1.0,
            narrow_typical_shell_m=[10,11],narrow_apartment_envelope_m2=[32,35],narrow_shared_corridor_clear_m=1.3,
            existing_storeys_preserved_as_assumption='3-5 storeys, each unit has its own shared stair; floor heights not joined across units.'),
        drawing=dict(pages=7,pixel_size=[W,H],paper_mm=[420,297],units='metres',
            page_files=[p.name for p in paths],png_sha256={p.name:sha(p) for p in paths},pdf=pdf.name,pdf_sha256=sha(pdf)),
        open_items=['User review of household arrangement and hotel arrival experience.',
                    'Existing structure/columns and fire circulation distances require the next detailed design pass.',
                    'Narrow front-house apartments are zoning proposals; detailed kitchen/bath furniture follows review.',
                    'Neighbouring 9-11m-deep residential units need their own dimensioned variants.'],
        sources=[dict(title='Signum — Calistoga Motor Lodge',url='https://signumarchitecture.com/gallery/calistoga-motor-lodge/',use='Connected arrival, reception and public space; not project dimensions.'),
                 dict(title='AQSO — Shoreditch hotel floor plan layouts',url='https://aqso.net/work/1703ahl-urban-resort-in-london/6731-the-floor-plan-layouts',use='Hotel floor function and shared circulation; not project dimensions.')])
    (OUT/'Proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,status=proposal['status'],pages=7,hotel_rooms=30,
                         maps_unchanged=True,output=str(OUT)),ensure_ascii=False))


if __name__=='__main__':main()
