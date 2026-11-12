"""Isolated HTTP, domain and authorization tests; no production database is touched."""
import io
import os
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

os.environ['DATABASE_URL']=os.getenv('EMOJI_TEST_DATABASE_URL','sqlite:///'+str(Path(tempfile.gettempdir())/f'emoji-tests-{uuid.uuid4().hex}.db').replace('\\','/'))

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app,hash_token
from app.models import Base,engine,SessionLocal,User,Course,ClassSession,ScheduleUser,EmojiRecord,LoginSession,now,iso
from app.services import safe_cell

PWD='ClassroomTest2026'
PASSWORD_HASH=bcrypt.hashpw(PWD.encode(),bcrypt.gensalt()).decode()
H={'X-Requested-With':'EmojiApp'}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN','test-service-secret')
    monkeypatch.setenv('AI_CONFIDENCE_THRESHOLD','0.6')
    monkeypatch.setenv('AI_SAMPLE_SECONDS','3')
    monkeypatch.setenv('TEACHER_INVITE_CODE','teacher-invite')
    monkeypatch.setenv('ADMIN_INVITE_CODE','admin-invite')
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for i,(name,role) in enumerate([('student','student'),('student2','student'),('teacher','teacher'),('teacher2','teacher'),('admin','admin')],1):
            db.add(User(id=i,username=name,role=role,password_hash=PASSWORD_HASH))
        db.flush()
        db.add_all([Course(id=1,name='软件工程实践',teacher_id=3),Course(id=2,name='数据库系统',teacher_id=4)]);db.flush()
        for sid in [1,2]:
            db.add(ClassSession(id=sid,course_id=sid,start_at=now()-timedelta(hours=1),end_at=now()+timedelta(hours=1),class_name='230'+str(sid),room='G2-B403'))
        db.flush()
        db.add_all([ScheduleUser(session_id=1,user_id=1),ScheduleUser(session_id=2,user_id=2)])
        db.commit()
    with TestClient(app) as client:
        tokens={}
        for name in ['student','student2','teacher','teacher2','admin']:
            response=client.post('/api/auth/login',json={'username':name,'password':PWD},headers=H)
            assert response.status_code==200,response.text
            tokens[name]={**H,'Authorization':'Bearer '+response.json()['access_token']}
        client.cookies.clear()
        yield client,tokens


def ai_payload(**changes):
    data=dict(session_id=1,emoji='happy',confidence=.9,timestamp=iso(now()),device_id='camera-01',event_id=str(uuid.uuid4()),model_version='test-model')
    return {**data,**changes}


def test_registration_role_invites_and_salted_hash(setup):
    c,t=setup
    for name in ['newstudent','otherstudent']:
        r=c.post('/api/auth/register',headers=H,json=dict(username=name,password=PWD));assert r.status_code==201
    assert c.post('/api/auth/register',headers=H,json=dict(username='privileged',password=PWD,role='admin')).status_code==403
    assert c.post('/api/auth/register',headers=H,json=dict(username='wronginvite',password=PWD,role='admin',invite_code='错误邀请码')).status_code==403
    r=c.post('/api/auth/register',headers=H,json=dict(username='newteacher',password=PWD,role='teacher',invite_code='teacher-invite'))
    assert r.status_code==201
    with SessionLocal() as db:
        a=db.scalar(select(User).where(User.username=='newstudent'));b=db.scalar(select(User).where(User.username=='otherstudent'))
        assert a.password_hash!=PWD and a.password_hash!=b.password_hash and bcrypt.checkpw(PWD.encode(),a.password_hash.encode())


@pytest.mark.parametrize('password',['short','onlyletterspassword','1234567890123','界'*30+'1'])
def test_weak_or_too_long_password_rejected(setup,password):
    c,t=setup
    assert c.post('/api/auth/register',headers=H,json=dict(username='newstudent',password=password)).status_code==422


def test_authentication_csrf_origin_and_logout(setup):
    c,t=setup
    assert c.get('/api/users/me').status_code==401
    assert c.post('/api/auth/login',json={'username':'student','password':PWD}).status_code==403
    assert c.post('/api/emoji',headers={**t['student'],'Origin':'https://evil.example'},json=dict(session_id=1,emoji='happy')).status_code==403
    assert c.post('/api/auth/logout',headers=t['student']).status_code==200
    assert c.get('/api/users/me',headers=t['student']).status_code==401


def test_password_change_revokes_all_sessions(setup):
    c,t=setup
    r=c.post('/api/auth/login',headers=H,json=dict(username='student',password=PWD));second={**H,'Authorization':'Bearer '+r.json()['access_token']}
    assert c.put('/api/auth/password',headers=t['student'],json=dict(old_password='wrong',new_password='ChangedPassword2026')).status_code==400
    assert c.put('/api/auth/password',headers=t['student'],json=dict(old_password=PWD,new_password='ChangedPassword2026')).status_code==200
    assert c.get('/api/users/me',headers=t['student']).status_code==401
    assert c.get('/api/users/me',headers=second).status_code==401


def test_login_rate_limit(setup):
    c,t=setup
    for _ in range(10):assert c.post('/api/auth/login',headers=H,json=dict(username='absent',password='wrong')).status_code==401
    assert c.post('/api/auth/login',headers=H,json=dict(username='absent',password='wrong')).status_code==429


def test_student_sends_only_enrolled_active_class_and_enums(setup):
    c,t=setup
    assert c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy')).status_code==201
    assert c.post('/api/emoji',headers=t['student'],json=dict(session_id=2,emoji='happy')).status_code==404
    assert c.post('/api/emoji',headers=t['teacher'],json=dict(session_id=1,emoji='happy')).status_code==403
    assert c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='invalid')).status_code==422
    with SessionLocal() as db:
        s=db.get(ClassSession,1);s.start_at=now()+timedelta(hours=1);s.end_at=now()+timedelta(hours=2);db.commit()
    assert c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy')).status_code==409


def test_history_statistics_and_courses_scope(setup):
    c,t=setup
    c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy'))
    c.post('/api/emoji',headers=t['student2'],json=dict(session_id=2,emoji='sad'))
    for role,total in [('student',1),('student2',1),('teacher',1),('teacher2',1),('admin',2)]:
        h=c.get('/api/emoji/history',headers=t[role]).json();assert h['total']==total
        stat=c.get('/api/emoji/statistics',headers=t[role]).json();assert stat['total']==total and sum(stat['distribution'].values())==total
        assert all(r['timestamp'].endswith('Z') for r in h['items'])
    assert len(c.get('/api/courses',headers=t['student']).json())==1
    assert len(c.get('/api/sessions',headers=t['teacher']).json())==1
    assert c.get('/api/emoji/history?session_id=2',headers=t['teacher']).status_code==404
    assert c.get('/api/admin/dashboard/realtime?sessionId=2',headers=t['teacher']).status_code==404


def test_schedule_replace_version_and_validation(setup):
    c,t=setup
    assert c.post('/api/admin/sessions/1/schedule',headers=t['student'],json=dict(user_ids=[1,2],version=1)).status_code==403
    for ids in [[1,1],[3],[999]]:
        assert c.post('/api/admin/sessions/1/schedule',headers=t['admin'],json=dict(user_ids=ids,version=1)).status_code==422
    r=c.post('/api/admin/sessions/1/schedule',headers=t['admin'],json=dict(user_ids=[1,2],version=1))
    assert r.status_code==200 and r.json()['version']==2
    assert c.post('/api/admin/sessions/1/schedule',headers=t['admin'],json=dict(user_ids=[],version=1)).status_code==409
    assert len(c.get('/api/admin/sessions/1/schedule',headers=t['admin']).json())==2
    assert c.post('/api/emoji',headers=t['student2'],json=dict(session_id=1,emoji='neutral')).status_code==201


def test_user_disable_immediately_blocks_session(setup):
    c,t=setup
    assert c.put('/api/admin/users/1',headers=t['admin'],json=dict(active=False)).status_code==200
    assert c.get('/api/users/me',headers=t['student']).status_code==401
    assert c.post('/api/admin/sessions/1/schedule',headers=t['admin'],json=dict(user_ids=[1],version=1)).status_code==422
    assert c.put('/api/admin/users/5',headers=t['admin'],json=dict(active=False)).status_code==409


def test_admin_create_session_and_date_validation(setup):
    c,t=setup
    data=dict(course_id=1,start_at=iso(now()),end_at=iso(now()+timedelta(hours=1)),class_name='2303',room='G2-B405')
    assert c.post('/api/admin/sessions',headers=t['teacher'],json=data).status_code==403
    r=c.post('/api/admin/sessions',headers=t['admin'],json=data);assert r.status_code==201
    data['end_at']=iso(now()-timedelta(hours=1))
    assert c.post('/api/admin/sessions',headers=t['admin'],json=data).status_code==422
    data['start_at']='2026-11-12T12:00:00'
    assert c.post('/api/admin/sessions',headers=t['admin'],json=data).status_code==422


def test_existing_feedback_preserves_class_identity(setup):
    c,t=setup
    c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy'))
    s=c.get('/api/sessions',headers=t['admin']).json()
    session=next(x for x in s if x['id']==1)
    data={k:session[k] for k in ['course_id','start_at','end_at','class_name','room','version']}
    data['course_id']=2
    assert c.put('/api/admin/sessions/1',headers=t['admin'],json=data).status_code==409


def test_filters_pagination_timezone_source(setup):
    c,t=setup
    for emoji in ['happy','sad','neutral']:c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji=emoji))
    r=c.get('/api/emoji/history?page=2&page_size=2',headers=t['admin']).json();assert r['total']==3 and len(r['items'])==1
    assert c.get('/api/emoji/history?source=AI',headers=t['admin']).json()['total']==0
    assert c.get('/api/emoji/history?class_name=2302',headers=t['admin']).json()['total']==0
    assert c.get('/api/emoji/history?course=2',headers=t['admin']).json()['total']==0
    assert c.get('/api/emoji/history?from=2026-11-12',headers=t['admin']).status_code==422
    assert c.get('/api/emoji/history?source=bad',headers=t['admin']).status_code==422
    r=c.get('/api/emoji/history',params={'from':iso(now()-timedelta(minutes=1)),'to':iso(now()+timedelta(minutes=1))},headers=t['admin'])
    assert r.json()['total']==3
    assert c.get('/api/emoji/history?page_size=101',headers=t['admin']).status_code==422


def test_csv_export_safe_and_same_scope(setup):
    c,t=setup
    with SessionLocal() as db:
        db.get(Course,1).name='=HYPERLINK("bad")';db.commit()
    c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy'))
    assert c.get('/api/admin/emoji/export',headers=t['teacher']).status_code==403
    r=c.get('/api/admin/emoji/export',headers=t['admin']);assert r.status_code==200 and r.content.startswith(b'\xef\xbb\xbf')
    assert "'=HYPERLINK" in r.text
    assert len(c.get('/api/admin/emoji/export?course=2',headers=t['admin']).text.splitlines())==1
    assert any(x['action']=='emoji.export' for x in c.get('/api/admin/audit',headers=t['admin']).json())


@pytest.mark.parametrize('text',['=SUM(1)','+1','-2','@foo',' \t=1','\r\n=1'])
def test_csv_escape_unit(text):assert safe_cell(text).startswith("'")


def test_ai_token_separate_from_user_token(setup):
    c,t=setup;p=ai_payload()
    assert c.post('/api/ai/emoji-results',headers=t['student'],json=p).status_code==401
    assert c.post('/api/ai/emoji-results',json=p).status_code==401
    assert c.post('/api/ai/emoji-results',headers={'Authorization':'Bearer test-service-secret'},json=p).status_code==200


def test_ai_threshold_idempotency_and_anonymity(setup):
    c,t=setup;auth={'Authorization':'Bearer test-service-secret'}
    assert c.post('/api/ai/emoji-results',headers=auth,json=ai_payload(confidence=.2)).json()['accepted'] is False
    p=ai_payload(confidence=.6)
    a=c.post('/api/ai/emoji-results',headers=auth,json=p).json();assert a['accepted'] and a['record']['user_id'] is None
    b=c.post('/api/ai/emoji-results',headers=auth,json=p).json();assert b['duplicate'] and a['record']['id']==b['record']['id']
    assert c.post('/api/ai/emoji-results',headers=auth,json={**p,'emoji':'angry'}).status_code==409
    assert c.get('/api/emoji/history',headers=t['student']).json()['total']==0
    stat=c.get('/api/emoji/statistics',headers=t['teacher']).json();assert stat['total']==1 and stat['ai']==1 and stat['participants']==0


def test_ai_timestamp_user_and_nan_validation(setup):
    c,t=setup;auth={'Authorization':'Bearer test-service-secret'}
    for changes in [dict(timestamp=iso(now()-timedelta(minutes=8))),dict(timestamp=iso(now()+timedelta(minutes=1))),dict(user_id=2),dict(confidence=1.1),dict(timestamp='2026-11-12T10:00:00')]:
        assert c.post('/api/ai/emoji-results',headers=auth,json=ai_payload(**changes)).status_code==422
    assert c.post('/api/ai/emoji-results',headers=auth,json=ai_payload(user_id=1)).json()['accepted']


def test_injection_treated_as_data_and_json_error_shape(setup):
    c,t=setup
    r=c.post('/api/auth/login',headers=H,json={'username':"' OR 1=1 --",'password':'whatever'});assert r.status_code==401
    assert set(r.json())=={'code','message'}
    assert set(c.get('/api/not-a-real-route').json())=={'code','message'}
    assert c.get('/api/emoji/history',params={'class_name':"' OR 1=1 --"},headers=t['admin']).json()['total']==0


def test_frame_memory_limits_and_scope_before_inference(setup):
    c,t=setup
    assert c.post('/api/ai/frame?session_id=1',headers=t['student'],files={'file':('x.jpg',b'test','image/jpeg')}).status_code==403
    assert c.post('/api/ai/frame?session_id=2',headers=t['teacher'],files={'file':('x.jpg',b'test','image/jpeg')}).status_code==404
    assert c.post('/api/ai/frame?session_id=1',headers=t['teacher'],files={'file':('x.jpg',b'x'*(2*1024*1024+1),'image/jpeg')}).status_code==413
    assert c.post('/api/ai/frame?session_id=1',headers=t['teacher'],files={'file':('x.txt',b'hello','text/plain')}).status_code==415


def test_websocket_auth_scope_and_live_statistics(setup):
    c,t=setup
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/dashboard?sessionId=1'):pass
    student_token=t['student']['Authorization'][7:]
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/dashboard?sessionId=1',headers={'cookie':'emoji_session='+student_token}):pass
    token=t['teacher']['Authorization'][7:]
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/dashboard?sessionId=2',headers={'cookie':'emoji_session='+token}):pass
    with c.websocket_connect('/ws/dashboard?sessionId=1',headers={'cookie':'emoji_session='+token}) as ws:
        assert ws.receive_json()['data']['total']==0
        c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy'))
        assert ws.receive_json()['data']['total']==1
        c.put('/api/admin/users/3',headers=t['admin'],json=dict(active=False))
        with pytest.raises(WebSocketDisconnect):ws.receive_json()


def test_expired_websocket_session_rejected(setup):
    c,t=setup
    token=t['teacher']['Authorization'][7:]
    with SessionLocal() as db:
        db.get(LoginSession,hash_token(token)).expires=now()-timedelta(seconds=1);db.commit()
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/dashboard?sessionId=1',headers={'cookie':'emoji_session='+token}):pass


def test_frame_proxy_filters_scores_and_avoids_upload_spool(setup,monkeypatch):
    c,t=setup
    import app.main as main
    import tempfile as temp
    def no_disk(*args,**kwargs):raise AssertionError('Raw frame must never spool to disk')
    monkeypatch.setattr(temp,'SpooledTemporaryFile',no_disk)
    class FakeAIClient:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            assert kwargs['headers']['Authorization']=='Bearer test-service-secret'
            assert len(kwargs['files']['file'][1])>1024*1024
            import httpx
            return httpx.Response(200,json=dict(detected=2,model_version='fixture-model',results=[
                dict(emoji='happy',confidence=.9),dict(emoji='sad',confidence=.3)]))
    monkeypatch.setattr(main.httpx,'AsyncClient',FakeAIClient)
    response=c.post('/api/ai/frame?session_id=1',headers=t['teacher'],files={'file':('test.jpg',b'x'*(1024*1024+10),'image/jpeg')})
    assert response.status_code==200,response.text
    assert response.json()['accepted']==1 and response.json()['rejected']==1
    with SessionLocal() as db:
        rows=list(db.scalars(select(EmojiRecord)))
        assert len(rows)==1 and rows[0].source=='AI' and rows[0].user_id is None


def test_websocket_expiry_during_connection(setup):
    c,t=setup
    token=t['teacher']['Authorization'][7:]
    from starlette.websockets import WebSocketDisconnect
    with c.websocket_connect('/ws/dashboard?sessionId=1',headers={'cookie':'emoji_session='+token}) as ws:
        assert ws.receive_json()['type']=='statistics'
        with SessionLocal() as db:
            db.get(LoginSession,hash_token(token)).expires=now()-timedelta(seconds=1);db.commit()
        with pytest.raises(WebSocketDisconnect):ws.receive_json()


def test_feedback_rejects_concurrent_schedule_change(setup):
    c,t=setup
    from fastapi import HTTPException
    from app.services import lock_session
    with SessionLocal() as db:
        stale=db.get(ClassSession,1)
        assert c.post('/api/admin/sessions/1/schedule',headers=t['admin'],json=dict(user_ids=[],version=1)).status_code==200
        with pytest.raises(HTTPException) as error:lock_session(db,stale)
        assert error.value.status_code==409
    assert c.post('/api/emoji',headers=t['student'],json=dict(session_id=1,emoji='happy')).status_code==404


def test_local_swagger_documentation_contract():
    from html.parser import HTMLParser
    import hashlib
    import json
    class Assets(HTMLParser):
        def __init__(self):
            super().__init__();self.scripts=[];self.styles=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='script':self.scripts.append(attrs.get('src'))
            if tag=='link' and attrs.get('rel')=='stylesheet':self.styles.append(attrs.get('href'))
    with TestClient(app) as client:
        page=client.get('/docs');assert page.status_code==200
        parser=Assets();parser.feed(page.text)
        assert parser.scripts and all(src and src.startswith('/static/vendor/swagger-ui/') for src in parser.scripts)
        assert parser.styles and all(src.startswith('/static/vendor/swagger-ui/') for src in parser.styles)
        script_policy=page.headers['content-security-policy'].split('script-src ',1)[1].split(';',1)[0]
        assert script_policy=="'self'"
        for asset in parser.scripts+parser.styles:assert client.get(asset).status_code==200
        manifest=client.get('/static/vendor/swagger-ui/SOURCE.json').json()
        for entry in manifest['files']:
            payload=client.get('/static/vendor/swagger-ui/'+entry['file']).content
            assert hashlib.sha256(payload).hexdigest()==entry['sha256']
        schema=client.get('/openapi.json').json()
        assert '/api/emoji' in schema['paths'] and 'AIServiceToken' in schema['components']['securitySchemes']
