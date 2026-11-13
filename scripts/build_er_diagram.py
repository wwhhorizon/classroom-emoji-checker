"""Draw the database ER diagram as editable SVG and vector PDF.

Requires reportlab. On Windows, uses SimHei, SimSun and Consolas from Fonts.
ER_CJK_FONT and ER_MONO_FONT can supply alternative TrueType font paths.
"""
from html import escape
import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'images'
WIDTH,HEIGHT=1000,1210
INK='#173955'
BLUE='#255A94'
MUTED='#62758A'
LINE='#64829F'
BORDER='#CBD7E3'
PALE='#EDF3F9'

# Field order and key annotations follow app/models.py.
ENTITIES=[
    ('LoginSession','登录会话','login_sessions',40,100,[
        ('PK','token_hash',False),('FK','user_id',False),('','expires',False)],None),
    ('Course','课程','courses',375,100,[
        ('PK','id',False),('','name',False),('FK','teacher_id',False)],'UK (name, teacher_id)'),
    ('User','用户','users',40,375,[
        ('PK','id',False),('UK','username',False),('','password_hash',False),
        ('','role',False),('','email',False),('','active',False),('','created_at',False)],None),
    ('ClassSession','课堂会话','class_sessions',710,375,[
        ('PK','id',False),('FK','course_id',False),('','class_name',False),('','room',False),
        ('','start_at',False),('','end_at',False),('','version',False)],None),
    ('ScheduleUser','课堂名单','schedule_users',375,430,[
        ('PK','id',False),('FK','session_id',False),('FK','user_id',False),
        ('','scheduled_at',False)],'UK (session_id, user_id)'),
    ('EmojiRecord','表情记录','emoji_records',375,770,[
        ('PK','id',False),('FK','session_id',False),('FK','user_id',True),
        ('','emoji',False),('','source',False),('','confidence',True),('','timestamp',False),
        ('','device_id',False),('','model_version',False),('UK','event_id',True)],None),
    ('AuditLog','操作审计','audit_logs',40,800,[
        ('PK','id',False),('FK','actor_id',True),('','action',False),
        ('','detail',False),('','created_at',False)],None),
]


class Drawing:
    def __init__(self):
        OUT.mkdir(parents=True,exist_ok=True)
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        cjk=Path(os.environ.get('ER_CJK_FONT',fonts/'simsun.ttc'))
        mono=Path(os.environ.get('ER_MONO_FONT',fonts/'consola.ttf'))
        bold=fonts/'simhei.ttf'
        for name,path in [('CJK',cjk),('CJKHead',bold if bold.exists() else cjk),('Mono',mono)]:
            pdfmetrics.registerFont(TTFont(name,str(path)))
        self.pdf=canvas.Canvas(str(OUT/'database-er.pdf'),pagesize=(WIDTH*.6,HEIGHT*.6))
        self.pdf.setTitle('课堂表情系统数据库 ER 图')
        self.pdf.setAuthor('袁谦朗 吴卫昊 李阳 吕祖灿')
        self.pdf.scale(.6,.6)
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
                  '<title>课堂表情系统数据库 ER 图</title>',
                  '<desc>七个实体及八组外键关系，标注主键、外键、唯一键、可空字段和关系基数。</desc>',
                  '<rect width="100%" height="100%" fill="white"/>']

    def rect(self,x,y,w,h,fill='white',stroke=None,r=0):
        self.pdf.setFillColor(fill)
        if stroke:self.pdf.setStrokeColor(stroke)
        self.pdf.setLineWidth(1.25)
        self.pdf.roundRect(x,HEIGHT-y-h,w,h,r,stroke=int(stroke is not None),fill=1)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="1.25"/>')

    def text(self,x,y,value,size=20,font='CJK',color=INK,anchor='start',rotate=0):
        self.pdf.saveState();self.pdf.setFillColor(color);self.pdf.setFont(font,size)
        self.pdf.translate(x,HEIGHT-y)
        if rotate:self.pdf.rotate(-rotate)
        {'start':self.pdf.drawString,'middle':self.pdf.drawCentredString,'end':self.pdf.drawRightString}[anchor](0,0,value)
        self.pdf.restoreState()
        family={'CJK':'SimSun, serif','CJKHead':'SimHei, sans-serif','Mono':'Consolas, monospace'}[font]
        transform=f' transform="rotate({rotate} {x} {y})"' if rotate else ''
        self.svg.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" fill="{color}"{transform}>{escape(value)}</text>')

    def path(self,points,color=LINE,width=1.9):
        self.pdf.setStrokeColor(color);self.pdf.setLineWidth(width)
        path=self.pdf.beginPath();path.moveTo(points[0][0],HEIGHT-points[0][1])
        for x,y in points[1:]:path.lineTo(x,HEIGHT-y)
        self.pdf.drawPath(path,stroke=1,fill=0)
        self.svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')

    def circle(self,x,y,r):
        self.pdf.setFillColor('white');self.pdf.setStrokeColor(LINE);self.pdf.setLineWidth(1.9)
        self.pdf.circle(x,HEIGHT-y,r,stroke=1,fill=1)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="{LINE}" stroke-width="1.9"/>')

    def marker(self,point,direction,cardinality):
        x,y=point;dx,dy=direction
        def p(along,across=0):return (x+dx*along-dy*across,y+dy*along+dx*across)
        if cardinality=='many':
            for spread in [-8,0,8]:self.path([p(5,spread),p(18)])
            self.circle(*p(29),4.5)
        else:
            self.path([p(9,-8),p(9,8)])
            if cardinality=='optional':self.circle(*p(25),4.5)
            else:self.path([p(21,-8),p(21,8)])

    def edge(self,points,start_direction,end_direction,optional=False):
        self.path(points)
        self.marker(points[0],start_direction,'optional' if optional else 'one')
        self.marker(points[-1],end_direction,'many')

    def card(self,entity):
        name,label,table,x,y,fields,note=entity
        h=64+len(fields)*27+16+(30 if note else 0)
        self.rect(x,y,250,h,'white',BORDER,7)
        self.rect(x+1,y+1,248,61,PALE,r=6)
        self.rect(x+1,y+48,248,14,PALE)
        self.text(x+16,y+27,name,24,'Mono',BLUE)
        self.text(x+16,y+50,label,18,'CJKHead',MUTED)
        for i,(key,field,nullable) in enumerate(fields):
            baseline=y+86+i*27
            if i%2==1:self.rect(x+1,baseline-20,248,27,'#F7F9FC')
            if key:self.text(x+16,baseline,key,15,'Mono',BLUE)
            self.text(x+58,baseline,field,20,'Mono')
            if nullable:self.text(x+237,baseline,'NULL',12,'Mono',MUTED,'end')
        if note:
            bottom=y+h-13
            self.path([(x+15,bottom-22),(x+235,bottom-22)],BORDER,1)
            self.text(x+16,bottom,note,15,'Mono',MUTED)

    def save(self):
        self.pdf.showPage();self.pdf.save()
        (OUT/'database-er.svg').write_text('\n'.join(self.svg+['</svg>'])+'\n',encoding='utf-8')


def main():
    drawing=Drawing()
    drawing.text(40,38,'课堂表情系统数据库 ER 图',29,'CJKHead')
    drawing.text(40,65,'核心业务、登录会话与操作审计',18,color=MUTED)

    # Eight foreign-key associations. Connectors stay in the gaps between cards.
    drawing.edge([(165,375),(165,261)],(0,-1),(0,1))
    drawing.edge([(290,425),(332.5,425),(332.5,197),(375,197)],(1,0),(-1,0))
    drawing.edge([(625,197),(667.5,197),(667.5,425),(710,425)],(1,0),(-1,0))
    drawing.edge([(290,555),(375,555)],(1,0),(-1,0))
    drawing.edge([(710,555),(625,555)],(-1,0),(1,0))
    drawing.edge([(290,625),(332.5,625),(332.5,950),(375,950)],(1,0),(-1,0),True)
    drawing.edge([(710,625),(667.5,625),(667.5,950),(625,950)],(-1,0),(1,0))
    drawing.edge([(165,644),(165,800)],(0,1),(0,-1),True)
    for entity in ENTITIES:drawing.card(entity)

    drawing.text(180,325,'登录会话',17,color=MUTED)
    drawing.text(325,310,'授课',17,color=MUTED,anchor='middle',rotate=-90)
    drawing.text(660,310,'开设课堂',17,color=MUTED,anchor='middle',rotate=-90)
    drawing.text(332.5,538,'参加',16,color=MUTED,anchor='middle')
    drawing.text(667.5,538,'安排',16,color=MUTED,anchor='middle')
    drawing.text(325,775,'提交 / 关联',17,color=MUTED,anchor='middle',rotate=-90)
    drawing.text(660,775,'收集',17,color=MUTED,anchor='middle',rotate=-90)
    drawing.text(180,727,'操作审计',17,color=MUTED)

    drawing.text(710,816,'读图说明',21,'CJKHead')
    drawing.path([(710,831),(960,831)],BORDER,1)
    drawing.text(710,858,'PK 主键    FK 外键',17,color=MUTED)
    drawing.text(710,884,'UK 唯一键   NULL 可为空',17,color=MUTED)
    for y,kind,label in [(923,'one','必须一个'),(963,'optional','可选一个'),(1003,'many','零到多个')]:
        drawing.path([(714,y),(771,y)])
        drawing.marker((714,y),(1,0),kind)
        drawing.text(788,y+6,label,18,color=MUTED)
    drawing.text(710,1051,'人工记录：user_id 非空',16,color=MUTED)
    drawing.text(710,1077,'AI 记录：confidence 非空',16,color=MUTED)
    drawing.text(710,1103,'默认匿名 AI：user_id 为空',16,color=MUTED)

    drawing.path([(40,1151),(960,1151)],BORDER,1)
    drawing.text(40,1178,'实体与外键对应 app/models.py；列类型及检查约束见 database/schema.sql。',17,color=MUTED)
    drawing.save()
    print('Created docs/images/database-er.svg and database-er.pdf')


if __name__=='__main__':main()
