"""Real Playwright recordings with Chinese narration and subtitles.

python scripts/record_demo.py --dry-run
python scripts/record_demo.py
The background AI service on 8011 must be running. Backend uses an isolated DB.
"""
import argparse
import asyncio
import csv
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.demo_story import SCENES, COURSE, CLASS_NAME
from scripts.seed_lesson_demo import ACCOUNTS
from scripts.fixture_server import fixture_server
from scripts.browser_verify import login,go

WORK=ROOT/'artifacts'/'demo'
EXPORT=ROOT/'deliverables'/'demo-source'
VIDEO=ROOT/'demo-assets'/'classroom-expressions.mp4'


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path):
    r=subprocess.run([ffmpeg(),'-i',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',r.stderr)
    if not m:raise RuntimeError('Cannot probe '+str(path))
    h,m,s=map(float,m.groups());return h*3600+m*60+s


async def narrate():
    import edge_tts
    semaphore=asyncio.Semaphore(3)
    async def one(i,title,script):
        path=EXPORT/f'{i:02}-voice.mp3';bound=EXPORT/f'{i:02}-sentences.json'
        textpath=EXPORT/f'{i:02}-narration.txt'
        if path.exists() and bound.exists() and textpath.exists() and textpath.read_text(encoding='utf-8')==script:return
        async with semaphore:
            for attempt in range(3):
                try:
                    chunks=[]
                    voice=edge_tts.Communicate(script,'zh-CN-XiaoxiaoNeural',rate='-2%',boundary='SentenceBoundary')
                    with path.open('wb') as f:
                        async for chunk in voice.stream():
                            if chunk['type']=='audio':f.write(chunk['data'])
                            elif chunk['type']=='SentenceBoundary':chunks.append({k:chunk[k] for k in ['offset','duration','text']})
                    bound.write_text(json.dumps(chunks,ensure_ascii=False,indent=2),encoding='utf-8')
                    textpath.write_text(script,encoding='utf-8')
                    print('Narration',i,round(duration(path),2),flush=True)
                    return
                except Exception:
                    if attempt==2:raise
                    await asyncio.sleep(2)
    await asyncio.gather(*(one(i,title,script) for i,(title,script) in enumerate(SCENES,1)))


def capture(dry=False):
    from playwright.sync_api import sync_playwright,expect
    errors=[];manifest=[];state={}
    with fixture_server(name='demo-dry' if dry else 'demo',port=8023,seed_module='scripts.seed_lesson_demo') as (base,password,database),sync_playwright() as p:
        browser=p.chromium.launch()
        contexts={}
        for role in ['guest','student','student2','teacher','admin','docs']:
            settings=dict(viewport={'width':1440,'height':900},locale='zh-CN',timezone_id='Asia/Shanghai',accept_downloads=True)
            if not dry:settings.update(record_video_dir=str(WORK/'raw'),record_video_size={'width':1440,'height':900})
            ctx=browser.new_context(**settings)
            if role in ['student','student2','teacher','admin']:
                r=ctx.request.post(base+'/api/auth/login',headers={'X-Requested-With':'EmojiApp'},data={'username':ACCOUNTS[role],'password':password})
                assert r.status==200,r.text()
            contexts[role]=ctx
        # Actual pointer motion is emphasized, page data is untouched.
        pointer="""document.addEventListener('DOMContentLoaded',()=>{const c=document.createElement('div');c.style.cssText='position:fixed;width:16px;height:16px;border:2px solid #255dcc;border-radius:50%;background:#ffffff99;pointer-events:none;z-index:2147483647;left:-30px;top:-30px;transform:translate(-50%,-50%)';document.body.append(c);document.addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px'});document.addEventListener('mousedown',()=>c.animate([{boxShadow:'0 0 0 0 #255dcc88'},{boxShadow:'0 0 0 16px #255dcc00'}],{duration:450}))})"""
        for ctx in contexts.values():ctx.add_init_script(pointer)

        def click(page,selector):
            el=page.locator(selector).first;el.scroll_into_view_if_needed();box=el.bounding_box()
            if box:page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2,steps=12)
            page.wait_for_timeout(60 if dry else 400);el.click();page.wait_for_timeout(60 if dry else 650)

        def fill(page,selector,value):
            el=page.locator(selector);el.scroll_into_view_if_needed();el.fill(value)
            page.wait_for_timeout(30 if dry else 450)

        def ready(page):
            expect(page.locator('#nav-home')).to_be_visible();expect(page.locator('#page-content .loading')).to_have_count(0)

        def choose(page):
            page.locator('#session-select').select_option(str(state['sid']));page.wait_for_timeout(80 if dry else 600)

        def scene(i,role,action):
            page=contexts[role].new_page();page.on('pageerror',lambda e:errors.append(str(e)));started=time.monotonic()
            page.goto(base);action(page)
            minimum=0 if dry else max(24.0,duration(EXPORT/f'{i:02}-voice.mp3')+2)
            remaining=minimum-(time.monotonic()-started)
            if remaining>0:page.wait_for_timeout(int(remaining*1000))
            elapsed=round(time.monotonic()-started,3)
            path=page.video.path() if page.video else None
            page.close()
            if path:
                destination=EXPORT/f'{i:02}-screen.webm';Path(path).replace(destination)
            manifest.append(dict(scene=i,title=SCENES[i-1][0],source_type='real_browser_recording',
                narration=SCENES[i-1][1],screen=f'{i:02}-screen.webm',voice=f'{i:02}-voice.mp3',seconds=elapsed))
            print('Scene',i,SCENES[i-1][0],elapsed,flush=True)

        scene(1,'guest',lambda page:expect(page.locator('#login-form')).to_be_visible())
        def registration(page):
            click(page,'#show-register');fill(page,'[name=username]','许沐阳');fill(page,'[name=password]',password)
            click(page,'#auth-submit');expect(page.locator('#login-form')).to_be_visible()
        scene(2,'guest',registration)
        users=contexts['admin'].request.get(base+'/api/admin/users').json();uid={u['username']:u['id'] for u in users}
        def course(page):
            ready(page);click(page,'#nav-sessions');click(page,'#new-course')
            fill(page,'#course-form [name=name]',COURSE)
            page.locator('#course-form [name=teacher_id]').select_option(str(uid[ACCOUNTS['teacher']]))
            click(page,'#course-form [type=submit]');expect(page.locator('#modal')).not_to_be_visible()
        scene(3,'admin',course)
        courses=contexts['admin'].request.get(base+'/api/courses').json()
        state['cid']=next(c['id'] for c in courses if c['name']==COURSE)
        def schedule(page):
            ready(page);click(page,'#nav-sessions');click(page,'#new-session')
            page.locator('#session-form [name=course_id]').select_option(str(state['cid']))
            fill(page,'#session-form [name=class_name]',CLASS_NAME);fill(page,'#session-form [name=room]','G2-B403')
            fill(page,'#session-form [name=start_at]',(datetime.now()-timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M'))
            fill(page,'#session-form [name=end_at]',(datetime.now()+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'))
            click(page,'#session-form [type=submit]');expect(page.locator('#modal')).not_to_be_visible()
            state['sid']=next(s['id'] for s in contexts['admin'].request.get(base+'/api/sessions').json() if s['course_id']==state['cid'])
            click(page,f'[data-schedule="{state["sid"]}"]')
            for name in ['student','student2']:page.locator(f'#schedule-form [name=user_ids][value="{uid[ACCOUNTS[name]]}"]').check()
            page.wait_for_timeout(80 if dry else 1800);click(page,'#schedule-form [type=submit]')
            expect(page.locator('#modal')).not_to_be_visible()
        scene(4,'admin',schedule)
        def first(page):
            ready(page);choose(page);click(page,'[data-emoji=happy]');click(page,'#send-emoji')
            expect(page.locator('[data-record-id]')).to_have_count(1)
        scene(5,'student',first)
        def second(page):
            ready(page);choose(page);click(page,'[data-emoji=surprised]');click(page,'#send-emoji');click(page,'#nav-history')
            expect(page.locator('[data-record-id]')).to_have_count(2)
            page.wait_for_timeout(100 if dry else 3000)
            click(page,'#logout')
            fill(page,'#login-form [name=username]',ACCOUNTS['student2']);fill(page,'#login-form [name=password]',password)
            click(page,'#auth-submit');ready(page);choose(page)
            click(page,'[data-emoji=neutral]');click(page,'#send-emoji');click(page,'#nav-history')
            expect(page.locator('[data-record-id]')).to_have_count(1)
            contexts['student'].request.post(base+'/api/auth/login',headers={'X-Requested-With':'EmojiApp'},data={'username':ACCOUNTS['student'],'password':password})
        scene(6,'student',second)
        def realtime(page):
            ready(page);choose(page);expect(page.locator('[data-stat=total]')).to_contain_text('3')
            page.wait_for_timeout(100 if dry else 6500)
            other=contexts['student'].new_page();other.goto(base);ready(other);choose(other)
            click(other,'[data-emoji=sad]');click(other,'#send-emoji');other.close();page.bring_to_front()
            expect(page.locator('[data-stat=total]')).to_contain_text('4',timeout=15000)
        scene(7,'teacher',realtime)
        def statistics(page):
            ready(page);click(page,'#nav-stats')
            page.locator('#filters-form [name=course]').select_option(str(state['cid']))
            fill(page,'#filters-form [name=class_name]','计算机2301')
            fill(page,'#filters-form [name=from]',(datetime.now()-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
            fill(page,'#filters-form [name=to]',(datetime.now()+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
            click(page,'#filters-form [type=submit]');expect(page.locator('[data-stat=manual]')).to_contain_text('4')
            page.locator('.secondary-charts').scroll_into_view_if_needed()
        scene(8,'admin',statistics)
        def ai(page):
            pending=set()
            page.on('request',lambda request:pending.add(request) if '/api/ai/frame?' in request.url else None)
            page.on('requestfinished',lambda request:pending.discard(request))
            page.on('requestfailed',lambda request:pending.discard(request))
            ready(page);choose(page);page.locator('.camera-section').scroll_into_view_if_needed()
            page.locator('#local-video-file').set_input_files(str(VIDEO));expect(page.locator('#sampling-source')).to_contain_text(VIDEO.name)
            expect(page.locator('#camera-preview')).to_be_visible()
            page.locator('#camera-preview').scroll_into_view_if_needed()
            expect(page.locator('#camera-result')).to_contain_text('本次保存',timeout=45000)
            page.wait_for_timeout(100 if dry else 8500)
            page.screenshot(path=str(ROOT/'docs'/'images'/'ai-video-desktop.png'),full_page=True)
            # Keep the video visible during actual sampling; no invented labels or results.
            if dry:
                page.wait_for_timeout(2500)
                if page.locator('#camera-stop').is_visible():click(page,'#camera-stop')
            else:
                expect(page.locator('#camera-stop')).not_to_be_visible(timeout=45000)
            deadline=time.monotonic()+40
            while pending and time.monotonic()<deadline:page.wait_for_timeout(100)
            assert not pending,'AI frame request did not complete'
            rows=contexts['admin'].request.get(base+f'/api/emoji/history?source=AI&session_id={state["sid"]}').json()
            assert rows['total']>=1,rows
            state['ai_count']=rows['total']
        scene(9,'teacher',ai)
        def ai_history(page):
            ready(page);click(page,'#nav-history');page.locator('#filters-form [name=source]').select_option('AI')
            click(page,'#filters-form [type=submit]');expect(page.locator('[data-record-id]')).to_have_count(state['ai_count'])
            page.screenshot(path=str(ROOT/'docs'/'images'/'ai-records-desktop.png'),full_page=True)
        scene(10,'teacher',ai_history)
        def export(page):
            ready(page);click(page,'#nav-stats');page.locator('#filters-form [name=course]').select_option(str(state['cid']))
            fill(page,'#filters-form [name=class_name]','计算机2301');click(page,'#filters-form [type=submit]')
            with page.expect_download() as dl:click(page,'#export-csv')
            dest=EXPORT/'课堂表情记录.csv';dl.value.save_as(dest)
            rows=list(csv.reader(io.StringIO(dest.read_text(encoding='utf-8-sig'))))
            assert len(rows)-1==4+state['ai_count']
            state['csv_rows']=len(rows)-1
        scene(11,'admin',export)
        def audit(page):
            ready(page);click(page,'#nav-users')
            click(page,f'[data-user-toggle="{uid["许沐阳"]}"]');click(page,f'[data-user-toggle="{uid["许沐阳"]}"]')
            click(page,'#nav-audit');expect(page.locator('tbody')).to_contain_text('导出记录')
        scene(12,'admin',audit)
        def closing(page):
            ready(page);click(page,'#nav-settings');page.wait_for_timeout(100 if dry else 6500)
            page.goto(base+'/docs');expect(page.locator('.swagger-ui')).to_be_visible()
            page.wait_for_timeout(100 if dry else 3500)
            page.mouse.wheel(0,450)
        scene(13,'teacher',closing)
        result=contexts['admin'].request.get(base+'/api/emoji/statistics').json()
        assert result['manual']==4 and result['ai']==state['ai_count'] and result['total']==state['csv_rows']
        assert not errors,errors
        evidence={'passed':True,'scene_count':len(manifest),'page_errors':errors,'database':str(database.relative_to(ROOT)),
            'statistics':result,'csv_rows':state['csv_rows'],'ai_input':'CREMA-D licensed expression video in a designed classroom scenario',
            'scenes':manifest}
        path=ROOT/'docs'/('demo-rehearsal.json' if dry else 'demo-verification.json')
        path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
        if not dry:(EXPORT/'MANIFEST.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    return evidence


def ass_time(seconds):
    cs=int(seconds*100);return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def subtitles(i,title):
    chunks=json.loads((EXPORT/f'{i:02}-sentences.json').read_text(encoding='utf-8'))
    header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1000\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,24,&H00FFFFFF,&H00FFFFFF,&H0010243B,&H0010243B,0,0,0,0,100,100,0,0,1,0,0,2,45,45,22,1\nStyle: Title,Microsoft YaHei,18,&H00B7C8DD,&H00B7C8DD,&H0010243B,&H0010243B,0,0,0,0,100,100,0,0,1,0,0,7,28,28,912,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    length=max(24,duration(EXPORT/f'{i:02}-voice.mp3')+2)
    lines=[f'Dialogue: 0,0:00:00.00,{ass_time(length+2)},Title,,0,0,0,,{i:02}  {title}']
    if not chunks:
        chunks=[dict(offset=0,duration=int((length-2)*1e7),text=SCENES[i-1][1])]
    for c in chunks:
        s=c['offset']/1e7+.6;end=s+c['duration']/1e7
        text=c['text'].replace('\n',' ').replace('{','').replace('}','')
        # Long utterances wrap into two lines without changing their words.
        if len(text)>48:
            mid=len(text)//2;text=text[:mid]+r'\N'+text[mid:]
        lines.append(f'Dialogue: 1,{ass_time(s)},{ass_time(end)},Default,,0,0,0,,{text}')
    path=EXPORT/f'{i:02}-subtitles.ass';path.write_text(header+'\n'.join(lines)+'\n',encoding='utf-8-sig')
    return path


def render():
    for i,(title,script) in enumerate(SCENES,1):
        ass=subtitles(i,title)
        screen=EXPORT/f'{i:02}-screen.webm';voice=EXPORT/f'{i:02}-voice.mp3';output=EXPORT/f'{i:02}-scene.mp4'
        length=max(duration(screen),duration(voice)+1)
        # Use relative subtitle paths inside cwd to avoid Windows drive-colon parsing.
        vf=f"fps=15,pad=1440:1000:0:0:color=0x10243b,subtitles={ass.name}"
        cmd=[ffmpeg(),'-y','-i',str(screen),'-i',str(voice),'-vf',vf,'-af','adelay=600|600,apad',
            '-t',str(length),'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-movflags','+faststart',str(output)]
        r=subprocess.run(cmd,cwd=EXPORT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if r.returncode:raise RuntimeError(r.stderr[-4000:])
        print('Rendered',i,round(length,2),flush=True)
    listing=EXPORT/'concat.txt';listing.write_text('\n'.join(f"file '{i:02}-scene.mp4'" for i in range(1,len(SCENES)+1)),encoding='utf-8')
    target=ROOT/'deliverables'/'课堂表情管理-中文解说演示.mp4'
    subprocess.run([ffmpeg(),'-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(target)],check=True,capture_output=True)
    full=duration(target)
    if not 300<=full<=480:raise RuntimeError(f'Video duration {full:.2f}s does not meet 5-8 minute requirement')
    decode=subprocess.run([ffmpeg(),'-v','error','-i',str(target),'-f','null','-'],capture_output=True,text=True)
    if decode.returncode or decode.stderr.strip():raise RuntimeError('Video decode failed: '+decode.stderr)
    evidence=json.loads((ROOT/'docs'/'demo-verification.json').read_text(encoding='utf-8'))
    evidence['video']={'path':str(target.relative_to(ROOT)),'duration_seconds':round(full,2),'width':1440,'height':1000,'video_codec':'H.264','audio_codec':'AAC','bytes':target.stat().st_size,'complete_decode':'passed'}
    (ROOT/'docs'/'demo-verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence['video'],ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');parser.add_argument('--render-only',action='store_true');parser.add_argument('--voice-only',action='store_true');args=parser.parse_args()
    WORK.mkdir(parents=True,exist_ok=True);EXPORT.mkdir(parents=True,exist_ok=True)
    introduction='''# 中文解说演示

## 课堂情境与素材

围绕“软件工程实践 · 需求分析与用例建模”完整演示。计算机2301班，高新校区G2-B403教室；周老师授课，林予安和陈知远为参加学生，许沐阳演示新生注册。人物姓名均为虚构账号，课程、课堂、反馈及导出由真实浏览器操作产生。

| 课堂环节 | 操作与观察 |
|---|---|
| 课前安排 | 管理员建立课程、当前时段课堂及两人名单；初始零表情记录 |
| 概念讲解 | 林予安主动提交开心 |
| 案例讨论 | 林予安提交惊讶；陈知远提交平静，并分别检查个人历史 |
| 随堂练习 | 林予安提交低落；教师无需刷新收到第四条反馈 |
| 课后核对 | 课程、班级、时间筛选，真实视频采样，匿名识别记录及CSV导出 |

课堂环节属于讲解编排，系统不额外存储环节标签；趋势使用实际提交时间。主动反馈、AI观测与参加人数分别统计。单个表情不直接代表知识掌握程度。

AI输入为 `demo-assets/classroom-expressions.mp4`，32秒，四个环节各8秒。CREMA-D授权动态表情素材以完整片段循环，绿幕替换为绘制的教室；画面明确标注课堂场景模拟及来源，没有预设识别结果。授权、原始素材、哈希及未筛选的模型结果见 `demo-assets/ATTRIBUTION.md` 和 `source-manifest.json`。

## 录制与复现

```powershell
python -m pip install -r requirements-video.txt
python -m playwright install chromium
python -m ai_service.prepare_classroom_assets
python scripts/build_classroom_sample.py
python scripts/record_demo.py --dry-run
python scripts/record_demo.py
```

后台8011推理服务需要先运行；录制脚本使用独立8023后端与新数据库，仅提前创建账号，表情记录均从零产生。中文解说与字幕、分镜屏幕原件和CSV保存在 `deliverables/demo-source/`。语音缓存依据文本检查，修改解说后会重新生成。

## 分镜与解说

'''
    (ROOT/'docs'/'demo.md').write_text(introduction+'\n\n'.join(f'### {i:02} {title}\n\n{text}' for i,(title,text) in enumerate(SCENES,1))+'\n',encoding='utf-8')
    if args.render_only:render();return
    if not args.dry_run:asyncio.run(narrate())
    if args.voice_only:return
    capture(args.dry_run)
    if not args.dry_run:render()


if __name__=='__main__':main()
