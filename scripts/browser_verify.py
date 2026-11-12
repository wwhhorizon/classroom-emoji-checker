"""Exercise the real UI on a fresh database. No fabricated records or chart values."""
import csv
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.fixture_server import fixture_server
from playwright.sync_api import sync_playwright, expect

OUT = ROOT / 'artifacts' / 'browser'
IMAGES = ROOT / 'docs' / 'images'
HEADERS = {'X-Requested-With': 'EmojiApp'}


def launch_browser(playwright, **options):
    channel=os.environ.get('DEMO_BROWSER_CHANNEL')
    if channel:
        options['channel']=channel
    return playwright.chromium.launch(**options)


def login(page, base, username, password):
    page.goto(base)
    expect(page.locator('#login-form')).to_be_visible()
    page.locator('#login-form [name=username]').fill(username)
    page.locator('#login-form [name=password]').fill(password)
    page.locator('#auth-submit').click()
    expect(page.locator('#nav-home')).to_be_visible()
    expect(page.locator('#page-content .loading')).to_have_count(0)


def go(page, name):
    page.locator('#nav-' + name).click()
    expect(page.locator('#page-content .loading')).to_have_count(0)


def accessibility(page):
    return page.evaluate('''() => {
      const issues=[];
      for(const el of document.querySelectorAll('input:not([type=hidden]),select,textarea')) {
        if(!el.getClientRects().length)continue;
        if(!(el.labels?.length||el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')))issues.push('unlabelled '+el.outerHTML.slice(0,100));
      }
      for(const el of document.querySelectorAll('button')) {
        if(el.getClientRects().length&&!el.textContent.trim()&&!el.getAttribute('aria-label'))issues.push('unnamed button');
      }
      if(document.documentElement.scrollWidth>innerWidth+1)issues.push('horizontal page overflow');
      return issues;
    }''')


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    stages = []
    errors = []
    checks = {}
    with fixture_server() as (base, password, database), sync_playwright() as p:
        browser = launch_browser(p)
        contexts = {role: browser.new_context(viewport={'width':1440,'height':1000}, locale='zh-CN',
            timezone_id='Asia/Shanghai', accept_downloads=True) for role in ['student','student2','teacher','admin','guest']}
        pages = {role: ctx.new_page() for role,ctx in contexts.items()}
        for page in pages.values():
            page.on('pageerror', lambda e: errors.append(str(e)))
        guest=pages['guest']
        guest.goto(base)
        expect(guest.locator('#login-form')).to_be_visible()
        guest.screenshot(path=str(IMAGES/'login-desktop.png'), full_page=True)
        checks['login']=accessibility(guest)
        # New student is created through the registration form.
        guest.locator('#show-register').click()
        guest.locator('#register-form [name=username]').fill('课堂新同学')
        guest.locator('#register-form [name=password]').fill(password)
        guest.locator('#auth-submit').click()
        expect(guest.locator('#login-form')).to_be_visible()
        stages.append('注册学生账号')
        for role in ['student','student2','teacher','admin']:
            login(pages[role],base,role,password)
        admin=pages['admin'];teacher=pages['teacher'];student=pages['student'];student2=pages['student2']
        assert contexts['admin'].request.get(base+'/api/emoji/history').json()['total']==0
        expect(teacher.locator('[data-stat=total]')).to_contain_text('0')
        stages.append('三角色登录；初始表情记录为零')
        go(admin,'sessions')
        admin.locator('#new-course').click()
        admin.locator('#course-form [name=name]').fill('面向对象设计')
        users=contexts['admin'].request.get(base+'/api/admin/users').json()
        uid={u['username']:u['id'] for u in users}
        admin.locator('#course-form [name=teacher_id]').select_option(str(uid['teacher']))
        admin.locator('#course-form [type=submit]').click()
        expect(admin.locator('#modal')).not_to_be_visible()
        courses=contexts['admin'].request.get(base+'/api/courses').json()
        cid=next(c['id'] for c in courses if c['name']=='面向对象设计')
        admin.locator('#new-session').click()
        form=admin.locator('#session-form')
        form.locator('[name=course_id]').select_option(str(cid))
        form.locator('[name=class_name]').fill('计算机2301')
        form.locator('[name=room]').fill('G2-B403')
        form.locator('[name=start_at]').fill((datetime.now()-timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M'))
        form.locator('[name=end_at]').fill((datetime.now()+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'))
        form.locator('[type=submit]').click()
        expect(admin.locator('#modal')).not_to_be_visible()
        sessions=contexts['admin'].request.get(base+'/api/sessions').json()
        sid=next(s['id'] for s in sessions if s['course_id']==cid)
        admin.locator(f'[data-schedule="{sid}"]').click()
        for username in ['student','student2','课堂新同学']:
            admin.locator(f'#schedule-form [name=user_ids][value="{uid[username]}"]').check()
        admin.screenshot(path=str(IMAGES/'schedule-desktop.png'), full_page=True)
        admin.locator('#schedule-form [type=submit]').click()
        expect(admin.locator('#modal')).not_to_be_visible()
        stages.append('管理员创建课程、课堂时段及三人名单')
        student.reload()
        expect(student.locator('#session-select')).to_be_visible()
        student.locator('#session-select').select_option(str(sid))
        expect(student.locator('[data-emoji=happy]')).to_be_enabled()
        student.locator('[data-emoji=happy]').click()
        expect(student.locator('[data-emoji=happy]')).to_have_attribute('aria-pressed','true')
        student.screenshot(path=str(IMAGES/'student-desktop.png'), full_page=True)
        student.locator('#send-emoji').click()
        expect(student.locator('[data-record-id]')).to_have_count(1)
        student.locator('[data-emoji=surprised]').click()
        student.locator('#send-emoji').click()
        expect(student.locator('[data-record-id]')).to_have_count(2)
        student2.reload()
        expect(student2.locator('#session-select')).to_be_visible()
        student2.locator('#session-select').select_option(str(sid))
        student2.locator('[data-emoji=neutral]').click()
        student2.locator('#send-emoji').click()
        expect(student2.locator('[data-record-id]')).to_have_count(1)
        stages.append('两名学生提交三条反馈，个人历史隔离')
        teacher.reload()
        expect(teacher.locator('#session-select')).to_be_visible()
        teacher.locator('#session-select').select_option(str(sid))
        expect(teacher.locator('[data-stat=total]')).to_contain_text('3',timeout=15000)
        expect(teacher.locator('#connection-status')).to_contain_text('实时更新中')
        # Send another feedback after opening teacher's WebSocket; do not refresh teacher.
        student.locator('[data-emoji=sad]').click();student.locator('#send-emoji').click()
        expect(teacher.locator('[data-stat=total]')).to_contain_text('4',timeout=15000)
        teacher.screenshot(path=str(IMAGES/'teacher-desktop.png'), full_page=True)
        checks['teacher']=accessibility(teacher)
        stages.append('教师实时看板无需刷新收到第四条反馈')
        go(admin,'stats')
        form=admin.locator('#filters-form')
        form.locator('[name=course]').select_option(str(cid))
        form.locator('[name=class_name]').fill('计算机2301')
        form.locator('[name=from]').fill((datetime.now()-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
        form.locator('[name=to]').fill((datetime.now()+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
        form.locator('[type=submit]').click()
        expect(admin.locator('[data-stat=total]')).to_contain_text('4')
        admin.screenshot(path=str(IMAGES/'statistics-desktop.png'), full_page=True)
        checks['statistics']=accessibility(admin)
        with admin.expect_download() as dl:
            admin.locator('#export-csv').click()
        target=OUT/'课堂表情记录.csv';dl.value.save_as(target)
        content=target.read_bytes()
        assert content.startswith(b'\xef\xbb\xbf')
        rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
        assert len(rows)==5,rows
        stages.append('课程、班级、时间组合筛选与四条记录CSV导出')
        go(admin,'users')
        admin.locator(f'[data-user-toggle="{uid["课堂新同学"]}"]').click()
        expect(admin.locator(f'[data-user-toggle="{uid["课堂新同学"]}"]')).to_have_attribute('data-active','true')
        response=contexts['guest'].request.post(base+'/api/auth/login',headers=HEADERS,data={'username':'课堂新同学','password':password})
        assert response.status==401
        admin.locator(f'[data-user-toggle="{uid["课堂新同学"]}"]').click()
        expect(admin.locator(f'[data-user-toggle="{uid["课堂新同学"]}"]')).to_have_attribute('data-active','false')
        stages.append('账号停用阻止登录，启用后恢复')
        # Register role and password UI validation without altering demonstration accounts.
        login(guest,base,'课堂新同学',password)
        go(guest,'settings')
        form=guest.locator('#password-form')
        form.locator('[name=old_password]').fill(password)
        new_password='Changed-Classroom-2026'
        form.locator('[name=new_password]').fill(new_password)
        form.locator('[name=confirm_password]').fill(new_password)
        form.locator('[type=submit]').click()
        expect(guest.locator('#login-form')).to_be_visible()
        login(guest,base,'课堂新同学',new_password)
        stages.append('浏览器修改密码并重新登录')
        teacher2=browser.new_context()
        teacher2.request.post(base+'/api/auth/login',headers=HEADERS,data={'username':'teacher2','password':password})
        assert teacher2.request.get(base+f'/api/admin/dashboard/realtime?sessionId={sid}').status==404
        assert contexts['student'].request.get(base+'/api/admin/users').status==403
        assert contexts['teacher'].request.get(base+'/api/admin/emoji/export').status==403
        stages.append('学生与非任课教师越权被后端拒绝')
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,locale='zh-CN',timezone_id='Asia/Shanghai')
        mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append(str(e)))
        login(mp,base,'student',password)
        checks['mobile-student']=accessibility(mp)
        mp.screenshot(path=str(IMAGES/'student-mobile.png'),full_page=True)
        stages.append('390像素手机界面无横向溢出，表单与按钮有可读标签')
        go(admin,'audit')
        expect(admin.locator('tbody')).to_contain_text('导出记录')
        admin.screenshot(path=str(IMAGES/'audit-desktop.png'),full_page=True)
        stages.append('导出与课堂安排操作审计可查')
        final=contexts['admin'].request.get(base+'/api/emoji/statistics').json()
        assert final['total']==4 and final['manual']==4 and final['ai']==0
        assert not errors,errors
        assert all(not v for v in checks.values()),checks
        result={'passed':True,'stages':stages,'page_errors':errors,'accessibility':checks,
            'csv_records':len(rows)-1,'statistics':final,'database':str(database.relative_to(ROOT)),
            'screenshots':[str(f.relative_to(ROOT)) for f in IMAGES.glob('*.png')]}
        (ROOT/'docs'/'browser-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        browser.close()


if __name__=='__main__':run()
