"""Capture report images from the just-recorded, real lesson database."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.fixture_server import fixture_server
from scripts.seed_lesson_demo import ACCOUNTS
from scripts.browser_verify import login, go
from playwright.sync_api import sync_playwright, expect


def main():
    evidence=json.loads((ROOT/'docs'/'demo-verification.json').read_text(encoding='utf-8'))
    database=ROOT/evidence['database']
    with fixture_server(name='lesson-images',port=8026,existing_database=database) as (base,password,_),sync_playwright() as p:
        browser=p.chromium.launch()
        for role, pages in [('student',[('home','student-desktop')]),
                            ('teacher',[('home','teacher-desktop')]),
                            ('admin',[('stats','statistics-desktop'),('sessions','schedule-desktop')])]:
            ctx=browser.new_context(viewport={'width':1440,'height':900},locale='zh-CN',timezone_id='Asia/Shanghai')
            page=ctx.new_page();login(page,base,ACCOUNTS[role],password)
            for nav,name in pages:
                go(page,nav);expect(page.locator('#page-content .loading')).to_have_count(0)
                page.screenshot(path=str(ROOT/'docs'/'images'/f'{name}.png'),full_page=True)
            ctx.close()
        browser.close()
    print('Captured report images from completed lesson demonstration.')


if __name__=='__main__':main()
