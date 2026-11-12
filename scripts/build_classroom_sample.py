"""Compose licensed dynamic faces into an explicitly illustrated classroom sample.

Every original clip loops in full for eight seconds, without prediction-based cuts.
The green studio background is replaced by a drawn classroom, never real footage.
"""
from pathlib import Path
import json
import subprocess
import hashlib
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'demo-assets'
INK = '#183C67'
BLUE = '#265DC5'
FONT = Path('C:/Windows/Fonts/msyh.ttc')
BOLD = Path('C:/Windows/Fonts/msyhbd.ttc')
STAGES = [
    ('课前准备', '回顾课堂目标', '识别参与者，描述系统边界', '1045_IEO_NEU_XX.mp4'),
    ('概念讲解', '从需求到用例', '理解参与者、目标与交互', '1045_IEO_HAP_HI.mp4'),
    ('案例讨论', '讨论用例关系', '分析 include 与 extend 的适用条件', '1045_IEO_ANG_HI.mp4'),
    ('随堂练习', '绘制用例图', '完成选课场景，提出待澄清的问题', '1045_IEO_SAD_HI.mp4'),
]


def font(size, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def background(index):
    im = Image.new('RGB', (1280, 720), '#F4F7FB')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((38, 30, 73, 65), 10, fill=BLUE)
    d.arc((45, 37, 66, 58), 5, 175, fill='white', width=2)
    d.ellipse((47, 40, 50, 43), fill='white');d.ellipse((60, 40, 63, 43), fill='white')
    d.text((88, 28), '课间晴雨', font=font(26, True), fill=INK)
    d.text((228, 37), '课堂表情采样', font=font(17), fill='#65768C')
    d.rounded_rectangle((1058, 31, 1240, 65), 16, fill='#E6EDFA')
    d.text((1082, 37), '课堂场景模拟', font=font(19), fill=BLUE)
    d.text((40, 94), '需求分析与用例建模', font=font(36, True), fill=INK)
    d.text((42, 150), '软件工程实践  /  计算机2301  /  高新校区', font=font(19), fill='#65768C')
    d.line((40, 190, 1240, 190), fill='#DCE4EF', width=1)
    for i, (title, _, _, _) in enumerate(STAGES):
        y = 225 + i * 83
        active = i == index
        if active:d.rounded_rectangle((36, y - 8, 433, y + 59), 13, fill='#E7EEFC')
        d.rounded_rectangle((51, y + 3, 85, y + 37), 10, fill=BLUE if active else '#E1E7F0')
        d.text((59, y + 5), str(i + 1), font=font(19, True), fill='white' if active else '#7B899D')
        d.text((104, y + 3), title, font=font(24, active), fill=INK if active else '#8290A4')
    d.text((48, 579), '当前任务', font=font(16), fill='#718197')
    d.text((48, 608), STAGES[index][2], font=font(18), fill=INK)
    # An illustration of a classroom; never presented as actual class footage.
    d.rounded_rectangle((466, 217, 1240, 631), 18, fill='#E5EAF0')
    d.rectangle((487, 235, 1219, 584), fill='#E9EEF3')
    d.rounded_rectangle((499, 245, 812, 432), 8, fill='#607A79')
    d.rounded_rectangle((507, 253, 804, 424), 5, outline='#9EAFAB', width=2)
    d.text((525, 272), '软件工程实践', font=font(21), fill='#F4F8EF')
    d.text((525, 315), STAGES[index][1], font=font(23), fill='#F4F8EF')
    d.line((525, 362, 701, 362), fill='#B9CAC1', width=2)
    d.text((526, 380), 'ACTOR · GOAL · INTERACTION', font=font(12), fill='#D8E2DC')
    for x in (1030, 1126):
        d.rectangle((x, 248, x+76, 411), fill='#CADAE8', outline='#B6C6D6', width=3)
        d.line((x, 329, x+76, 329), fill='#F7FAFC', width=5)
    d.rounded_rectangle((493, 475, 660, 499), 6, fill='#B8C5D0')
    d.line((511, 499, 511, 574), fill='#A2B1BD', width=7)
    d.line((642, 499, 642, 574), fill='#A2B1BD', width=7)
    d.text((41, 668), 'CREMA-D 授权人物素材合成 · 仅用于视频采样演示', font=font(16), fill='#6A7A8D')
    d.text((950, 668), 'ODbL 1.0 / DbCL 1.0', font=font(16), fill='#6A7A8D')
    return im


def person(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32)
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
    # Chroma key only removes the source studio backdrop; expression stays intact.
    excess = g - np.maximum(r,b)
    alpha = np.clip((28 - excess) / 18, 0, 1)
    alpha = cv2.GaussianBlur(alpha, (3,3), .55)
    rgb[:,:,1] = np.minimum(g, np.maximum(r,b) + 12)
    rgba = np.dstack((rgb.astype(np.uint8), (alpha*255).astype(np.uint8)))
    return Image.fromarray(rgba).resize((616,462), Image.Resampling.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    target = OUT / 'classroom-expressions.mp4'
    cmd = [ffmpeg,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','15','-i','-',
           '-an','-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for i, stage in enumerate(STAGES):
        video = cv2.VideoCapture(str(OUT/'source'/stage[3]));frames=[]
        while True:
            ok, frame = video.read()
            if not ok:break
            frames.append(frame)
        fps=video.get(cv2.CAP_PROP_FPS);video.release()
        if not frames:raise RuntimeError(stage[3])
        bg=background(i)
        for n in range(120):
            frame = frames[int(n / 15 * fps) % len(frames)]
            image = bg.copy();cutout=person(frame)
            image.paste(cutout,(616,169),cutout)
            d=ImageDraw.Draw(image)
            # Foreground desk anchors the illustrated scene and hides the source crop edge.
            d.rounded_rectangle((681,581,1222,611),8,fill='#B1BDC9')
            d.rectangle((695,606,1205,630),fill='#8FA0B0')
            d.rounded_rectangle((989,547,1138,590),6,fill='#C6D0DC',outline='#9EADBC',width=2)
            d.line((981,589,1148,589),fill='#9EADBC',width=5)
            elapsed=i*8+n/15
            d.line((40,649,1240,649),fill='#DCE4EF',width=3)
            d.line((40,649,40+int(1200*elapsed/32),649),fill=BLUE,width=3)
            if n == 45:image.save(OUT/f'preview-{i+1}.png')
            proc.stdin.write(image.tobytes())
        print('Composed classroom stage:',stage[0],flush=True)
    proc.stdin.close();err=proc.stderr.read();proc.wait()
    if proc.returncode:raise RuntimeError(err.decode('utf-8',errors='replace'))
    evidence={'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'duration_seconds':32,'width':1280,'height':720,'fps':15,
        'stage_seconds':8,'stages':[{'stage':s[0],'task':s[2],'source':s[3]} for s in STAGES],
        'transform':'Original clips looped in full; green backdrop replaced by illustrated classroom; no prediction overlays',
        'source_manifest':'source-manifest.json'}
    (OUT/'composition.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Created:',target)


if __name__ == '__main__':main()
