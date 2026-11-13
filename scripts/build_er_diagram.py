"""Draw the compact entity overview used in the course report."""
from html import escape
import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'images'
WIDTH, HEIGHT = 1000, 635
INK, LINE, BORDER, PALE = '#173955', '#64829F', '#CBD7E3', '#EDF3F9'


class Drawing:
    def __init__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for name, path in [('CJK', os.environ.get('ER_CJK_FONT', fonts/'simsun.ttc')),
                           ('Head', fonts/'simhei.ttf'),
                           ('Mono', os.environ.get('ER_MONO_FONT', fonts/'consola.ttf'))]:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        self.pdf = canvas.Canvas(str(OUT/'database-er.pdf'), pagesize=(WIDTH*.6, HEIGHT*.6), invariant=1)
        self.pdf.setTitle('课堂表情系统核心实体关系图')
        self.pdf.scale(.6, .6)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
                    '<title>课堂表情系统核心实体关系图</title>',
                    '<rect width="100%" height="100%" fill="white"/>']

    def text(self, x, y, value, size=20, font='CJK', color=INK, anchor='start'):
        self.pdf.setFillColor(color)
        self.pdf.setFont(font, size)
        method = self.pdf.drawCentredString if anchor == 'middle' else self.pdf.drawString
        method(x, HEIGHT-y, value)
        family = {'CJK': 'SimSun, serif', 'Head': 'SimHei, sans-serif', 'Mono': 'Consolas, monospace'}[font]
        self.svg.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" fill="{color}">{escape(value)}</text>')

    def path(self, points, color=LINE, width=1.8):
        self.pdf.setStrokeColor(color)
        self.pdf.setLineWidth(width)
        path = self.pdf.beginPath()
        path.moveTo(points[0][0], HEIGHT-points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, HEIGHT-y)
        self.pdf.drawPath(path)
        coords = ' '.join(f'{x},{y}' for x,y in points)
        self.svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}"/>')

    def card(self, x, y, title, subtitle, lines, height=130):
        self.pdf.setFillColor('white')
        self.pdf.setStrokeColor(BORDER)
        self.pdf.roundRect(x, HEIGHT-y-height, 270, height, 5, stroke=1, fill=1)
        self.svg.append(f'<rect x="{x}" y="{y}" width="270" height="{height}" rx="5" fill="white" stroke="{BORDER}"/>')
        self.pdf.setFillColor(PALE)
        self.pdf.rect(x+1, HEIGHT-y-56, 268, 55, stroke=0, fill=1)
        self.svg.append(f'<rect x="{x+1}" y="{y+1}" width="268" height="55" fill="{PALE}"/>')
        self.text(x+15, y+25, title, 23, 'Mono' if title.isascii() else 'Head')
        self.text(x+15, y+47, subtitle, 18)
        for i,line in enumerate(lines):
            self.text(x+15, y+83+i*25, line, 17, 'Mono')

    def save(self):
        self.pdf.showPage()
        self.pdf.save()
        (OUT/'database-er.svg').write_text('\n'.join(self.svg+['</svg>'])+'\n', encoding='utf-8')


def main():
    d = Drawing()
    # Same concise entity boxes as the original figure, routed through the gaps.
    d.path([(300,245),(330,245),(330,90),(365,90)])
    d.path([(635,90),(670,90),(670,245),(700,245)])
    d.path([(300,285),(365,285)])
    d.path([(700,285),(635,285)])
    d.path([(300,320),(330,320),(330,515),(365,515)])
    d.path([(700,320),(670,320),(670,515),(635,515)])
    d.path([(165,340),(165,450)])

    d.card(30,210,'User','用户',['id, username, role','password_hash, active'])
    d.card(365,25,'Course','课程',['id, name','teacher_id'])
    d.card(700,210,'ClassSession','课堂',['id, course_id','start_at, end_at, version'])
    d.card(365,210,'ScheduleUser','课堂名单',['session_id, user_id','scheduled_at'])
    d.card(365,450,'EmojiRecord','表情记录',['session_id, user_id?','emoji, source, confidence','timestamp, event_id'],155)
    d.card(30,450,'会话与审计','辅助实体',['LoginSession / AuditLog','user_id / actor_id'])

    for x,y,label in [(223,175,'1:N 授课'),(690,175,'1:N 开课'),
                      (318,276,'1:N'),(652,276,'N:1'),
                      (222,405,'1:N 记录'),(690,405,'N:1 收集'),(100,400,'1:N')]:
        d.text(x,y,label,18)
    d.save()
    print('Created compact database-er.svg and database-er.pdf')


if __name__ == '__main__':
    main()
