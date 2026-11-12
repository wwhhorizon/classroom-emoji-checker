"""Check getUserMedia, AI sampling and camera track cleanup in Chromium."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.fixture_server import fixture_server
from scripts.browser_verify import login,launch_browser
from scripts.record_demo import ffmpeg
from playwright.sync_api import sync_playwright,expect


def main():
    media=ROOT/'artifacts'/'camera-input.y4m'
    media.parent.mkdir(exist_ok=True)
    subprocess.run([ffmpeg(),'-y','-i',str(ROOT/'demo-assets'/'classroom-expressions.mp4'),
        '-t','8','-vf','scale=640:360','-r','10','-pix_fmt','yuv420p',str(media)],check=True,capture_output=True)
    errors=[]
    with fixture_server(name='camera',port=8027) as (base,password,database),sync_playwright() as p:
        browser=launch_browser(p,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',
            '--use-file-for-fake-video-capture='+str(media)])
        ctx=browser.new_context(permissions=['camera'],viewport={'width':1440,'height':900},locale='zh-CN')
        page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        login(page,base,'teacher',password)
        page.locator('#session-select').select_option('1')
        expect(page.locator('#page-content .loading')).to_have_count(0)
        page.locator('#camera-start').click()
        expect(page.locator('#sampling-source')).to_have_text('摄像头实时采样')
        expect(page.locator('#camera-result')).to_contain_text('本次保存 1 条',timeout=30000)
        tracks=page.locator('#camera-video').evaluate_handle('video=>video.srcObject.getTracks()')
        assert tracks.evaluate('tracks=>tracks.length>0 && tracks.every(track=>track.readyState==="live")')
        page.locator('#camera-stop').click()
        expect(page.locator('#camera-stop')).not_to_be_visible()
        assert tracks.evaluate('tracks=>tracks.every(track=>track.readyState==="ended")')
        response=ctx.request.get(base+'/api/emoji/history?source=AI&session_id=1')
        assert response.status==200,response.text()
        records=response.json();assert records['total']>=1
        assert all(row['user_id'] is None and row['source']=='AI' for row in records['items'])
        assert not errors,errors
        evidence=dict(passed=True,browser_version=browser.version,input='Chromium test camera with classroom video Y4M',
            get_user_media=True,tracks_ended_after_stop=True,ai_records=records['total'],page_errors=errors,
            database=str(database.relative_to(ROOT)))
        (ROOT/'docs'/'camera-verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(evidence,ensure_ascii=False))
        browser.close()


if __name__=='__main__':main()
