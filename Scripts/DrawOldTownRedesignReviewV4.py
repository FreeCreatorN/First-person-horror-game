"""V4 review-only hotel plan: centred door/reception, left offices, right stair/WC."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
import DrawOldTownRedesignReviewV2 as b
import DrawOldTownRedesignReviewV3 as v3

ROOT=b.ROOT
OUT=ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261008_V4'
C,W,H=b.C,b.W,b.H
Plan,text,notes,wrapped=b.Plan,b.text,b.notes,b.wrapped
furniture,toilet,basin=b.furniture,b.toilet,b.basin
translated,enclosed=b.translated,v3.enclosed
OFFICES=[((.2,2.6,4.4,4.8),'值班 / 员工\n9.2㎡'),
         ((.2,5.0,4.4,7.2),'管理 / 弱电\n9.2㎡'),
         ((.2,7.4,4.4,10.2),'前台办公室\n11.8㎡')]
LIFT=(10.2,7.2,13.2,10.2)
STAIR=(17.72,7.0,23.60,10.2)
WC=(18.2,2.6,23.8,5.8)
COUNTER=(9.9,4.8,14.1,5.6)
VESTIBULE=(10.0,.2,14.0,2.4)
SEATS=[(6.2,7.7,7.0,9.8),(8.8,7.7,9.6,9.8),
       (6.2,6.8,6.85,7.45),(9.0,6.8,9.65,7.45),(14.0,9.3,16.2,10.1)]


def sheet(n,title,subtitle):
    im=Image.new('RGB',(W,H),C['paper']);d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,24),fill=C['guest'])
    text(d,(170,92),'老城街区  /  建筑重设计',36,C['muted'],True)
    text(d,(170,166),title,74,bold=True)
    text(d,(170,274),subtitle,37,C['muted'])
    d.rounded_rectangle((3410,88,4030,180),radius=20,fill=C['circulation'])
    text(d,(3720,130),'V4  审查稿 · 未实施',35,C['guest'],True,'mm')
    d.line((170,355,4030,355),fill=C['grid'],width=3)
    d.line((170,2820,4030,2820),fill=C['grid'],width=3)
    text(d,(170,2855),'2026-10-08  |  先审查平面，再建模  |  单位：m  |  面积为方案估算',31,C['muted'])
    text(d,(4020,2866),f'{n:02d} / 07',35,C['muted'],anchor='ra')
    return im,d


def safety_stair(p,ground=False,detail=True):
    # Rear-right horizontal U stair. Left landing is the SAME FLOOR landing.
    enclosed(p,STAIR,C['circulation'])
    for ya,yb in ((7.0,8.4),(8.8,10.2)):
        p.rect((19.12,ya,22.2,yb),'#EEF3F5',C['muted'],3)
        for i in range(12):
            xx=19.12+3.08*i/11;p.line((xx,ya),(xx,yb),C['muted'],2)
    p.rect((19.12,8.4,22.2,8.8),C['paper'],C['muted'],2)
    p.line((19.18,8.46),(22.14,8.74),C['muted'],2)
    p.line((19.18,8.74),(22.14,8.46),C['muted'],2)
    p.route([(19.3,7.7),(22.0,7.7)],dash=False)
    p.route([(22.0,9.5),(19.3,9.5)],dash=False)
    p.door(17.62,7.3,1.2,'N','E')
    if ground:
        p.door(17.82,10.3,1.2,'E','N')
        p.route([(18.42,9.5),(18.42,11.05)],dash=False)
    p.label(18.42,8.6,'同层\n平台',28 if detail else 22)
    p.label(22.9,8.6,'半层\n转台',28 if detail else 22)
    if detail:p.label(20.66,7.7,'上',25,C['guest'])


def lift(p,detail=True):
    enclosed(p,LIFT,C['service'])
    # Right-facing lift door opens into the shared rear hall, away from reception.
    p.door(13.3,8.0,1.4,'N','E',False)
    p.label(11.7,8.8,'电梯井\n3 × 3',35 if detail else 26)


def public_wc(p,detail=True):
    enclosed(p,WC,C['service'])
    p.door(18.1,3.0,1.2,'N','E')
    p.wall((20.1,4.0),(23.8,4.0),.12)
    p.wall((20.1,4.0),(20.1,5.8),.12)
    p.wall((21.9,4.0),(21.9,5.8),.12)
    p.door(20.4,4.0,.8,'E','N');p.door(22.25,4.0,.8,'E','N')
    toilet(p,21.0,5.15);toilet(p,22.85,5.15)
    basin(p,(18.45,4.7,19.15,5.4));basin(p,(19.25,4.7,19.95,5.4))
    p.label(21.75,3.2,'公共厕所 / 2厕位',27 if detail else 23)
    if detail:p.label(19.2,4.4,'洗手区',23)


def lobby(p,detail=True):
    p.rect((.2,.2,23.8,10.2),C['public'])
    for box,label in OFFICES:
        enclosed(p,box,C['service'])
        cy=(box[1]+box[3])/2
        p.door(4.5,cy-.45,.9,'N','W')
        furniture(p,(.5,box[3]-.9,2.2,box[3]-.25),'desk')
        p.label(2.3,cy-.25,label,32 if detail else 24)
    # Four-metre wide foyer on the whole building centre line s35.
    enclosed(p,VESTIBULE,C['circulation'])
    p.door(11,.1,2,'E','N',False);p.door(11,2.5,2,'E','N',False)
    p.label(12,1.35,'门斗\n4 × 2.2',33 if detail else 24)
    furniture(p,COUNTER)
    p.label(12,5.2,'前台 4.2m',34 if detail else 26)
    for box in SEATS:furniture(p,box,'sofa')
    furniture(p,(7.6,8.3,8.2,9.0),'desk')
    safety_stair(p,True,detail);lift(p,detail);public_wc(p,detail)
    # Main axis is free from the foyer rear opening to reception's front face.
    p.route([(12,-1.0),(12,.45)])
    p.route([(12,2.9),(12,4.35)])
    # Side routes preserve the frontal public corridor, passing around the foyer.
    p.route([(10.7,3.7),(8.5,3.7),(8.5,1.3),(0,1.3)])
    p.route([(13.3,3.7),(15.5,3.7),(15.5,1.3),(24,1.3)])
    p.route([(15.5,3.7),(15.5,6.4),(15.5,8.7),(13.55,8.7)])
    p.route([(15.5,7.9),(17.3,7.9)])
    p.route([(16.1,3.6),(17.8,3.6)])
    p.route([(8.5,4.0),(8.5,6.5),(7.9,7.0)])
    p.route([(5.3,8.2),(5.3,6.3),(11.4,6.3),(11.4,5.8)],True)
    # Public wing connections lie below all office/WC enclosures.
    p.door(.1,.4,1.8,'N','E',False);p.door(23.9,.4,1.8,'N','W',False)
    if detail:
        p.label(5.3,8.8,'员工\n通道\n1.4',27,C['staff'])
        p.label(7.9,6.65,'6座会客',29)
        p.label(15.1,9.0,'2座候梯',27)
        p.label(11.8,6.3,'后台工作带 1.4',28,C['staff'])
        p.label(16.05,5.0,'公共\n过厅',29,C['guest'])
        p.label(10.65,4.15,'入口—前台中轴',26,C['guest'])
        p.win((.5,.1),(9.4,.1));p.win((14.6,.1),(23.4,.1))


def exit_inset(d):
    text(d,(2980,2280),'后侧出口接续：预留方案，待场地复核',30,C['red'],True)
    q=Plan(d,2990,2360,11,17)
    q.rect((0,3,70,13.4),C['public'],C['wall'],4)
    q.rect((0,0,73,3),'#ECE8DD')
    q.rect((40.52,9.8,46.8,13.4),C['circulation'],C['wall'],3)
    b.arrow(d,[q.p(*pt) for pt in [(41.42,13.4),(41.42,15.4),(72,15.4),(72,1.5),(66,1.5)]],C['red'],4,True)
    q.label(22,8.5,'酒店外壳（示意）',26)
    q.label(31,1.4,'临街前场',26,C['muted'])
    q.label(41.42,16.8,'后侧新增通道预留',25,C['red'])
    wrapped(d,(2980,2630),'需核实后侧及楼端用地可通行；此线不代表现有地图已连通。',1000,31,C['red'])


def draw_first_floor():
    im,d=sheet(2,'酒店首层  /  中轴接待，左办公、右梯厕','大门与前台位于整栋酒店正中；右上安全梯、右下公共厕所；办公室全部左置。')
    p=Plan(d,330,680,50,10.4);b.hotel_shell(p,True)
    p.wall((6,2.5),(23,2.5));p.wall((19,2.6),(19,10.2));p.wall((23,.2),(23,10.2))
    p.rect((6.2,2.6,18.8,10.2),C['public']);p.rect((19.2,2.6,22.8,10.2),C['service'])
    p.double(10.1,2.5,1.8,'N');p.door(19,7.0,1,'N','W')
    for xx in (8,12,16):
        for yy in (4.1,7.4):
            furniture(p,(xx,yy,xx+1.3,yy+.8),'desk')
            for cx in (xx+.1,xx+.75):
                for cy in (yy-.65,yy+.9):furniture(p,(cx,cy,cx+.45,cy+.45))
    furniture(p,(22.1,3.1,22.7,9.7),'cabinet')
    p.label(12.5,9.35,'早餐 / 茶厅 24座',33);p.label(20.6,6.8,'备餐',30)
    p.wall((47,.2),(47,10.2));lobby(translated(p,23),False)
    # Right wing has linen/changing/equipment only; all offices are left of reception.
    p.rect((47.2,2.6,63.8,6.8),C['service']);p.wall((47,2.5),(64,2.5))
    parts=[((47.2,7,51.0,10.2),'清布草'),((51.2,7,55.0,10.2),'污布草'),
           ((55.2,7,58.8,10.2),'更衣'),((59,7,61.2,10.2),'员工WC'),((61.4,7,63.8,10.2),'设备')]
    for box,label in parts:
        enclosed(p,box,C['service']);cx=(box[0]+box[2])/2
        p.door(cx-.45,6.9,.9,'E','N');p.label(cx,8.6,label,26)
    toilet(p,60.7,9.5);basin(p,(59.2,9.4,59.9,10.0))
    p.double(60.3,.2,1.4,'N');p.double(60.3,2.5,1.4,'N')
    p.route([(61,-1),(61,5.2),(56,5.2),(56,6.5)],True)
    p.label(54.0,4.3,'收货 / 备品整理',30,C['staff'])
    for xx in (8,12,16,20,24,47.6,51.6,55.6,59.2,62):p.win((xx,10.3),(xx+1.5,10.3))
    p.hdim(0,70,12.4,'70.0 m 总长 / 主入口轴线 s35',37)
    for a,z,t in [(0,6,'6 南梯'),(6,19,'13 餐茶'),(19,23,'4 备餐'),(23,47,'24 接待核心'),(47,64,'17 后勤'),(64,70,'6 北梯')]:p.hdim(a,z,11.35,t,30)
    p.vdim(-1.1,0,10.4,'10.4',35)
    p.label(35,-1.6,'正中主入口',35,C['guest'],True)
    for x,t in [(3,'出口'),(67,'出口')]:p.label(x,-1.6,t,30,C['guest'])
    p.label(61,-1.6,'后勤入口',30,C['staff'])
    text(d,(330,1410),'大门与前台同轴  /  左侧办公  /  右上安全梯、右下厕所',52,bold=True)
    text(d,(330,1510),'大厅段加宽至24m，公共净区约148㎡；行李室继续取消，前场公共通道不被办公室或厕所占用。',36,C['muted'])
    b.legend(d,330,1620)
    notes(d,330,1790,1060,'入口与接待',[
        ('整栋酒店正中','70m楼的正中为s35；门斗中心、2m主门中心及4.2m前台中心均在同一轴线上。'),
        ('分支绕开柜台','客人从门斗看见前台，去客房、电梯或卫生间走两侧公共过厅。')],36)
    notes(d,1660,1790,1040,'办公与厕所',[
        ('办公室全在左侧','三间办公室竖向成排，门朝右接1.4m员工通道；前台背后工作带净1.4m。'),
        ('右下公共厕所','两独立厕位和洗手缓冲，侧向进门；下方2.2m共有走廊完整保留。')],36)
    notes(d,2980,1790,980,'楼梯与后侧出口',[
        ('楼梯放右上','入口和首层后出口都接左端同层平台。原两端楼梯保留，上层梯井同轴。'),
        ('室外接续有条件','后出口需预留后侧绕楼端回街通道，右下示意；场地可行性尚需核实。')],33)
    exit_inset(d)
    return b.save(im,'02_Hotel_GroundFloor')


def draw_lobby():
    im,d=sheet(3,'接待大厅放大  /  大门居中，前台正对','图面上方为酒店后侧、下方为临街正面；左办公室、右上安全梯、右下厕所。')
    p=Plan(d,340,690,112,10.4)
    p.rect((0,-1.7,24,0),'#ECE8DD');p.rect((0,0,24,10.4),C['wall'])
    lobby(p,True)
    p.hdim(0,24,11.8,'24.0 m 大厅段：s23–47',38)
    p.vdim(-.75,.2,10.2,'10.0 m',36)
    p.label(12,-1.2,'整栋正中主入口 s35',35,C['guest'],True)
    p.label(4.4,-1.15,'临街前场（局部）',30,C['muted'])
    notes(d,3130,610,870,'按你的布局重排',[
        ('大门在正中','门斗与前台共同对齐整栋70m酒店的中轴，柜台正面朝门。'),
        ('办公室全部左置','三室竖排，各自侧开门；前台工作带向左接员工通道。'),
        ('右上安全楼梯','封闭两跑楼梯；左端为同层平台，右端只是半层转台。'),
        ('右下公共厕所','侧向进门，两独立厕位；不挤占前侧共有走廊。'),
        ('电梯同步挪位','后场偏左，门朝右侧公共梯厅；上下层一致。')],34)
    text(d,(340,2470),'后出口接续与面积',45,bold=True)
    wrapped(d,(340,2550),'首层后出口之后的室外绕行通道为新增预留方案，待场地复核（整段示意见02）。大厅内净236㎡，扣办公室、井道、梯间、公共厕所与门斗隔墙后，公共净区约148㎡，含柜台、候客及门斗。',2700,36,C['muted'])
    return b.save(im,'03_Hotel_Lobby_Enlarged')


def guest_room(p,x=0,bay=4.8,twin=True,detail=True):
    p.rect((x+.1,2.6,x+bay-.1,10.2),C['private'])
    p.wall((x,2.5),(x+bay,2.5));p.wall((x,2.6),(x,10.2));p.wall((x+bay,2.6),(x+bay,10.2))
    p.door(x+bay-1.6,2.5,1,'E','N')
    p.rect((x+.2,2.6,x+2.25,5.0),'#E5EEEA',C['wall'],max(5,round(.12*p.s)))
    p.door(x+2.25,3.5,.85,'N','W',False)
    p.rect((x+.3,2.8,x+1.25,3.75),None,C['muted'],3)
    toilet(p,x+.85,4.45);basin(p,(x+1.4,2.8,x+2.1,3.4))
    p.rect((x+1.8,4.5,x+2.2,4.95),C['wall'])
    furniture(p,(x+bay-.7,3.85,x+bay-.1,5.65),'cabinet')
    if twin:
        furniture(p,(x+.5,7.7,x+1.5,9.7),'bed')
        furniture(p,(x+bay-1.5,7.7,x+bay-.5,9.7),'bed')
        furniture(p,(x+1.75,9.5,x+2.65,10.1),'desk')
    else:
        furniture(p,(x+1.0,7.7,x+2.6,9.7),'bed')
        furniture(p,(x+bay-1.25,9.5,x+bay-.35,10.1),'desk')
    furniture(p,(x+.4,5.45,x+1.2,6.8),'sofa')
    furniture(p,(x+1.55,5.65,x+2.65,6.3),'desk')
    p.win((x+1.25,10.3),(x+bay-1.25,10.3))
    if detail:
        p.label(x+1.3,4.1,'卫浴',30)
        p.label(x+bay-1,3.1,'入口',28)
        p.label(x+bay/2,7.0,'床前通行',29,C['guest'])
        p.route([(x+bay-1.1,2.1),(x+bay-1.1,4.6),(x+bay-1.2,6.8),(x+bay/2,8.8)])


def upper_core(p,detail=True):
    p.rect((7.1,.2,23.9,10.2),C['circulation'])
    p.wall((7,2.5),(7,10.2));p.wall((24,2.5),(24,10.2))
    safety_stair(p,False,detail);lift(p,detail)
    for box,label in [((7.2,7.2,9.8,10.2),'楼层布草'),((7.2,3.0,9.8,5.6),'清洁')]:
        enclosed(p,box,C['service'])
        p.door(box[2]+.1,box[1]+.4,.9,'N','W')
        p.label((box[0]+box[2])/2,(box[1]+box[3])/2,label,28 if detail else 23)
    p.route([(7,1.3),(24,1.3)])
    p.route([(15.5,1.3),(15.5,8.7),(13.55,8.7)])
    p.route([(15.5,7.9),(17.3,7.9)])
    if detail:
        p.label(15.5,5.4,'公共过厅',32,C['guest'])
        p.label(15.1,9.6,'共有梯厅',27)
        p.label(15.5,2.4,'前側走廊连续贯通',28,C['guest'])


def draw_standard():
    im,d=sheet(4,'酒店标准层  /  后部梯井同轴，前廊贯通','二至四层各9间，共27间；左右翼房间模数随新核心调整，避免井道错层。')
    p=Plan(d,330,550,50,10.4);b.hotel_shell(p)
    for i in range(5):
        x=6+4.8*i;guest_room(p,x,4.8,i%3!=2,False)
        p.label(x+2.4,6.7,f'2{i+1:02d}\n35.0㎡',28)
    for i in range(4):
        x=47+4.25*i;guest_room(p,x,4.25,i%3!=1,False)
        p.label(x+2.125,6.7,f'2{i+6:02d}\n30.8㎡',27)
    upper_core(translated(p,23),False)
    p.hdim(0,70,12.6,'70.0 m',36)
    for a,z,t in [(0,6,'6'),(6,30,'5 × 4.8 = 24'),(30,47,'17 交通核心'),(47,64,'4 × 4.25 = 17'),(64,70,'6')]:p.hdim(a,z,11.5,t,30)
    p.vdim(-1,.2,2.4,'2.2',30);p.vdim(-1,2.6,10.2,'7.6',30)
    text(d,(330,1170),'右段4.25m客房放大',44,bold=True)
    q=Plan(d,425,1430,142,10.4);guest_room(q,0,4.25,True,True)
    q.hdim(.1,4.15,11.2,'净宽4.05m',32);q.vdim(-.6,2.6,10.2,'净深7.6',30)
    q.label(2.125,1.9,'共有走廊',30,C['guest'])
    text(d,(1370,1170),'中部17m交通核心放大',44,bold=True)
    a=Plan(d,1370,1430,91,10.4);a.rect((0,0,17,10.4),C['wall'])
    upper_core(translated(a,-7),True)
    a.hdim(0,17,11.2,'后部：电梯 / 右上安全梯',31)
    notes(d,3120,1330,885,'与首层一起调整',[
        ('轴线逐层一致','净井道s33.2–36.2，后右梯s40.72–46.60，各层叠置。'),
        ('客房尺寸重算','左5房每间约35.0㎡，右4房每间约30.8㎡，均含私用卫浴。'),
        ('前侧交通恢复贯通','2.2m共有走廊通过核心区，去任一端楼梯无需穿中部梯间。'),
        ('首层厕所独立','右下公共厕所仅在首层；上层对应公共交通区，管线位置后续深化。')],35)
    text(d,(330,2690),'图面已适配双床/单床、柜体与房门；原柱梁、层高、级数和完整疏散距离仍待深化。',34,C['muted'])
    return b.save(im,'04_Hotel_TypicalFloor')


def draw_site():
    # V3 site drawing contains verified V2 district geometry; use its source with V4 callouts.
    import inspect
    src=inspect.getsource(v3.draw_site)
    src=src.replace('V3调整酒店大厅与交通核心。','V4将酒店大门放整栋正中，并重排左右功能。')
    src=src.replace('(77.8,33.6),(82.5,33.6),(85.5,33.6)','(77.8,35),(82.5,35),(85.5,35)')
    src=src.replace("p.route([(85.5,41.9),(82.5,41.9)],dash=False)","# Rear exit is depicted in page02 conditional external route inset.")
    src=src.replace('首层20m中央大厅，后墙房间成排；角部电梯、新增临街安全梯。','首层24m大厅，大门和前台正中；左办公、右上梯、右下厕所。')
    src=src.replace('蓝色为共有入口 / 客人通行；酒店前场新增梯出口。','蓝色为共有入口 / 客人通行；后側新梯出口通路待核。')
    ns=dict(v3.__dict__);ns.update(sheet=sheet)
    exec(compile(src,'<V4 district geometry>','exec'),ns)
    return ns['draw_site']()


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True);b.OUT=OUT;b.sheet=sheet
    protected=[ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap',
        ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json',
        ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261007_V2/OldTown_Architecture_Redesign_V2_Review.pdf',
        ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261008_V3/OldTown_Architecture_Redesign_V3_Review.pdf']
    before={str(p):sha(p) for p in protected}
    paths=[draw_site(),draw_first_floor(),draw_lobby(),draw_standard(),b.draw_house(5,True),b.draw_house(6,False),b.draw_narrow()]
    pdf=OUT/'OldTown_Architecture_Redesign_V4_Review.pdf'
    cv=canvas.Canvas(str(pdf),pagesize=(420*mm,297*mm));cv.setTitle('Old Town Architecture V4 - Centred Hotel Entry')
    for path in paths:cv.drawImage(ImageReader(str(path)),0,0,width=420*mm,height=297*mm);cv.showPage()
    cv.save();assert len(PdfReader(str(pdf)).pages)==7
    assert before=={str(p):sha(p) for p in protected},'Protected map/evidence/history changed.'
    assert sum((6,24,17,17,6))==70
    deductions=dict(office_enclosures=4.4*7.8,stair_enclosure_inside_lobby=6.28*3.4,
                    lift_enclosure_inside_lobby=3.4*3.2,wc_enclosure_inside_lobby=5.8*3.6,vestibule_walls_after_door_openings=.96)
    net=236-sum(deductions.values())
    old=json.loads((ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261008_V3/Proposal.json').read_text(encoding='utf-8'))
    proposal=dict(status='AWAITING_USER_REVIEW',implemented=False,review_date='2026-10-08',created_at_utc=datetime.now(timezone.utc).isoformat(),changes_to_ue_assets=0,protected_file_sha256=before,
        hotel=dict(shell_m=[70,10.4],floors=4,ground_guest_rooms=0,total_rooms=27,upper_rooms_per_floor=9,
            lobby_segment_m=[23,47],main_door_axis_global_s_m=35,reception_axis_global_s_m=35,lobby_clear_envelope_m2=236,public_lobby_estimated_m2=round(net,2),area_deductions_m2=deductions,
            public_area_definition='Includes vestibule, reception and furniture; excludes offices, WC, shaft and stair enclosures. Concept estimate.',
            offices_side='left',office_clear_boxes_lobby_local_m=[box for box,label in OFFICES],office_staff_passage_clear_x_m=[4.6,6.0],
            reception_counter_clear_box_lobby_local_m=COUNTER,reception_staff_passage_clear_y_m=[5.6,7.0],vestibule_clear_box_lobby_local_m=VESTIBULE,main_door_clear_m=2,
            wc_clear_box_lobby_local_m=WC,wc_location='front right / image lower right',wc_stalls=2,
            lift_clear_box_lobby_local_m=LIFT,lift_clear_global_sd_m=[33.2,7.2,36.2,10.2],lift_door_side='right',
            stair_clear_box_lobby_local_m=STAIR,stair_clear_global_sd_m=[40.72,7.0,46.6,10.2],stair_location='rear right / image upper right',stair_same_floor_landing_side='left',stair_ground_exit_global_s_m=[40.82,42.02],stair_flight_clear_m=1.4,stair_run_m=3.08,stair_landings_m=1.4,
            rear_exit_route_status='NEW_RESERVED_ROUTE_REQUIRES_SITE_VERIFICATION',rear_route_verified_in_ue=False,rear_exit_route_schematic='rear exit -> reserved rear lane -> beyond north building end -> street-side forecourt; page02 inset',
            wing_corridor_clear_m=2.2,lobby_cross_passage_clear_y_m=[2.6,4.8],upper_core_segment_m=[30,47],left_rooms_per_floor=5,left_room_bay_m=4.8,left_room_envelope_m2=34.96,right_rooms_per_floor=4,right_room_bay_m=4.25,right_room_envelope_m2=30.78,
            luggage_room=False,waiting_seats=8,dining_seats=24,seat_boxes_lobby_local_m=SEATS,
            ground_program_segments=[['south_stair',0,6],['tea_dining',6,19],['pantry',19,23],['lobby_left_offices_right_stair_wc',23,47],['linen_changing_equipment',47,64],['north_stair',64,70]]),
        residential=old['residential'],drawing=dict(pages=7,pixel_size=[W,H],paper_mm=[420,297],page_files=[p.name for p in paths],png_sha256={p.name:sha(p) for p in paths},pdf=pdf.name,pdf_sha256=sha(pdf)),
        open_items=['User review of centred entry/reception and left offices/right stair/WC arrangement.','Rear and north-end reserved exit route requires real site geometry verification before implementation.','Actual structure, floor heights, risers, slab voids, fire door construction and full egress distances to be detailed.','Residential unchanged from V2; narrow-unit furniture and depth variants still pending.'],sources=old['sources'])
    (OUT/'Proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,pages=7,rooms=27,lobby_public_m2=round(net,2),door_axis=35,protected_files_unchanged=True,output=str(OUT)),ensure_ascii=False))


if __name__=='__main__':main()
