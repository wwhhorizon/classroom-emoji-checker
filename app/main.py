import asyncio
import hashlib
import hmac
import os
import secrets
import uuid
from email.parser import BytesParser
from email.policy import default as email_policy
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import bcrypt
import httpx
from fastapi import FastAPI, Depends, Request, Response, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.models import Base, engine, SessionLocal, User, LoginSession, Course, ClassSession, ScheduleUser, EmojiRecord, AuditLog, now, iso
from app import schemas as S
from app.repository import scoped_sessions, visible_session, scoped_records, username
from app.services import (fail, audit, public_user, serialize_session, serialize_record,
    active_session, bump_version, lock_session, replace_schedule, accept_ai, statistics, export_csv, ai_config)


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app=FastAPI(title='课间晴雨 课堂表情管理',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None,
    description='学生表情反馈、教师课堂看板、管理员课程排课及独立视频表情识别。所有响应时间使用UTC。')
STATIC=Path(__file__).parent/'static'
app.mount('/static',StaticFiles(directory=STATIC),name='static')


@app.middleware('http')
async def protection(request,call_next):
    if request.url.path.startswith('/api/') and request.method in ['POST','PUT','PATCH','DELETE'] and request.url.path!='/api/ai/emoji-results':
        if request.headers.get('x-requested-with')!='EmojiApp':
            return JSONResponse({'code':'CSRF_REJECTED','message':'请求校验失败，请刷新页面'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            return JSONResponse({'code':'ORIGIN_REJECTED','message':'请求来源不合法'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request,exc):
    return JSONResponse({'code':f'HTTP_{exc.status_code}','message':str(exc.detail)},status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    messages=['.'.join(map(str,e['loc'][1:]))+': '+e['msg'] for e in exc.errors()]
    return JSONResponse({'code':'VALIDATION_ERROR','message':'；'.join(messages)},status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_error(request,exc):
    return JSONResponse({'code':'CONFLICT','message':'数据已存在或关联数据无效'},status_code=409)


def db_session():
    with SessionLocal() as db:yield db


def hash_token(token):return hashlib.sha256(token.encode()).hexdigest()


def resolve_user(db,token):
    session=db.get(LoginSession,hash_token(token)) if token else None
    if not session or session.expires<=now():return None
    u=db.get(User,session.user_id)
    return u if u and u.active else None


def current_user(request:Request,db=Depends(db_session)):
    auth=request.headers.get('authorization','')
    token=auth[7:] if auth.startswith('Bearer ') else request.cookies.get('emoji_session')
    user=resolve_user(db,token)
    if not user:fail(401,'请先登录，或登录已失效')
    return user


def admin(user=Depends(current_user)):
    if user.role!='admin':fail(403,'需要管理员权限')
    return user


def teacher_or_admin(user=Depends(current_user)):
    if user.role not in ['teacher','admin']:fail(403,'需要教师或管理员权限')
    return user


def ai_auth(request:Request):
    expected=os.getenv('AI_SERVICE_TOKEN','')
    provided=request.headers.get('authorization','')
    if not expected or not hmac.compare_digest(provided.encode('utf-8'),('Bearer '+expected).encode('utf-8')):fail(401,'AI服务令牌无效')


@app.get('/',include_in_schema=False)
def index():return FileResponse(STATIC/'index.html')


@app.get('/docs',include_in_schema=False)
def documentation():
    return FileResponse(STATIC/'vendor'/'swagger-ui'/'index.html')


@app.get('/health')
def health(db=Depends(db_session)):
    db.execute(select(1));return {'status':'ok','service':'emoji-backend','version':'1.0.0'}


@app.post('/api/auth/register',status_code=201)
def register(data:S.Register,db=Depends(db_session)):
    if data.role!='student':
        expected=os.getenv('ADMIN_INVITE_CODE' if data.role=='admin' else 'TEACHER_INVITE_CODE','')
        if not expected or not hmac.compare_digest(expected.encode('utf-8'),data.invite_code.encode('utf-8')):fail(403,'该角色需要有效邀请码')
    if db.scalar(select(User.id).where(User.username==data.username)):fail(409,'用户名已存在')
    u=User(username=data.username,password_hash=bcrypt.hashpw(data.password.encode(),bcrypt.gensalt()).decode(),role=data.role,email=data.email)
    db.add(u);db.flush();audit(db,u.id,'auth.register');db.commit()
    return public_user(u)


@app.post('/api/auth/login')
def login(data:S.Credentials,request:Request,response:Response,db=Depends(db_session)):
    key=hash_token((request.client.host if request.client else 'unknown')+'|'+data.username)
    count=db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action=='auth.failed',AuditLog.detail==key,AuditLog.created_at>now()-timedelta(minutes=5)))
    if count>=10:fail(429,'登录失败次数过多，请5分钟后重试')
    u=db.scalar(select(User).where(User.username==data.username))
    if not u or not u.active or not bcrypt.checkpw(data.password.encode(),u.password_hash.encode()):
        audit(db,None,'auth.failed',key);db.commit();fail(401,'用户名或密码错误')
    token=secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hash_token(token),user_id=u.id,expires=now()+timedelta(hours=8)))
    audit(db,u.id,'auth.login');db.commit()
    response.set_cookie('emoji_session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='1',max_age=28800)
    return dict(user=public_user(u),access_token=token,token_type='bearer')


@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(db_session)):
    auth=request.headers.get('authorization','')
    token=auth[7:] if auth.startswith('Bearer ') else request.cookies.get('emoji_session','')
    db.execute(delete(LoginSession).where(LoginSession.token_hash==hash_token(token)));db.commit()
    response.delete_cookie('emoji_session');return {'message':'已退出登录'}


@app.put('/api/auth/password')
def password(data:S.Password,user=Depends(current_user),db=Depends(db_session)):
    if not bcrypt.checkpw(data.old_password.encode(),user.password_hash.encode()):fail(400,'原密码错误')
    user.password_hash=bcrypt.hashpw(data.new_password.encode(),bcrypt.gensalt()).decode()
    db.execute(delete(LoginSession).where(LoginSession.user_id==user.id));audit(db,user.id,'auth.password');db.commit()
    return {'message':'密码已修改，请重新登录'}


@app.get('/api/users/me')
def me(user=Depends(current_user)):return public_user(user)


@app.get('/api/admin/users')
def users(user=Depends(admin),db=Depends(db_session)):
    return [public_user(u) for u in db.scalars(select(User).order_by(User.id))]


@app.put('/api/admin/users/{uid}')
def update_user(uid:int,data:S.UserStatus,user=Depends(admin),db=Depends(db_session)):
    u=db.get(User,uid)
    if not u:fail(404,'用户不存在')
    if u.role=='admin':fail(409,'管理员账号状态不可在此修改')
    u.active=int(data.active)
    if not data.active:db.execute(delete(LoginSession).where(LoginSession.user_id==u.id))
    audit(db,user.id,'user.status',str(uid));db.commit();return public_user(u)


@app.get('/api/courses')
def courses(user=Depends(current_user),db=Depends(db_session)):
    q=select(Course)
    if user.role=='teacher':q=q.where(Course.teacher_id==user.id)
    elif user.role=='student':q=q.where(Course.id.in_(select(ClassSession.course_id).where(ClassSession.id.in_(select(ScheduleUser.session_id).where(ScheduleUser.user_id==user.id)))))
    return [dict(id=c.id,name=c.name,teacher_id=c.teacher_id,teacher=username(db,c.teacher_id)) for c in db.scalars(q.order_by(Course.id))]


@app.post('/api/admin/courses',status_code=201)
def create_course(data:S.NewCourse,user=Depends(admin),db=Depends(db_session)):
    t=db.get(User,data.teacher_id)
    if not t or not t.active or t.role!='teacher':fail(422,'请选择有效教师')
    c=Course(**data.model_dump());db.add(c);db.flush();audit(db,user.id,'course.create',str(c.id));db.commit()
    return dict(id=c.id,name=c.name,teacher_id=c.teacher_id,teacher=t.username)


@app.get('/api/sessions')
def sessions(user=Depends(current_user),db=Depends(db_session)):
    return [serialize_session(db,s,user) for s in db.scalars(scoped_sessions(db,user).order_by(ClassSession.start_at.desc(),ClassSession.id.desc()))]


@app.post('/api/admin/sessions',status_code=201)
def create_session(data:S.NewSession,user=Depends(admin),db=Depends(db_session)):
    if not db.get(Course,data.course_id):fail(422,'课程不存在')
    s=ClassSession(**data.model_dump());db.add(s);db.flush();audit(db,user.id,'session.create',str(s.id));db.commit()
    return serialize_session(db,s,user)


@app.put('/api/admin/sessions/{sid}')
def update_session(sid:int,data:S.UpdateSession,user=Depends(admin),db=Depends(db_session)):
    s=visible_session(db,user,sid)
    if not db.get(Course,data.course_id):fail(422,'课程不存在')
    # Existing observations must retain the course, class and original observation window.
    has_records=db.scalar(select(EmojiRecord.id).where(EmojiRecord.session_id==sid).limit(1))
    if has_records and any(getattr(s,k)!=getattr(data,k) for k in ['course_id','class_name','start_at','end_at']):
        fail(409,'已有反馈的课堂不能修改课程、班级及起止时间')
    bump_version(db,s,data.version,data.model_dump(exclude={'version'}));audit(db,user.id,'session.update',str(sid));db.commit();db.refresh(s)
    return serialize_session(db,s,user)


@app.get('/api/admin/sessions/{sid}/schedule')
def schedule(sid:int,user=Depends(admin),db=Depends(db_session)):
    visible_session(db,user,sid)
    q=select(User).join(ScheduleUser,User.id==ScheduleUser.user_id).where(ScheduleUser.session_id==sid).order_by(User.id)
    return [public_user(u) for u in db.scalars(q)]


@app.post('/api/admin/sessions/{sid}/schedule')
def set_schedule(sid:int,data:S.Schedule,user=Depends(admin),db=Depends(db_session)):
    s=visible_session(db,user,sid);return replace_schedule(db,s,data,user)


@app.post('/api/emoji',status_code=201)
def manual(data:S.ManualEmoji,user=Depends(current_user),db=Depends(db_session)):
    if user.role!='student':fail(403,'请使用学生账号提交表情')
    s=visible_session(db,user,data.session_id);active_session(s)
    lock_session(db,s)
    r=EmojiRecord(user_id=user.id,session_id=s.id,emoji=data.emoji,source='MANUAL',device_id='browser')
    db.add(r);db.flush();audit(db,user.id,'emoji.manual',str(r.id));db.commit();return serialize_record(db,r)


def filters(session_id:int|None=None,course:int|None=None,class_name:str|None=None,
    from_time:str|None=Query(None,alias='from'),to_time:str|None=Query(None,alias='to'),source:str|None=None,
    class_alias:str|None=Query(None,alias='class')):
    if class_name and class_alias and class_name!=class_alias:fail(422,'班级筛选条件冲突')
    return dict(session_id=session_id,course=course,class_name=class_name or class_alias,from_time=from_time,to_time=to_time,source=source)


@app.get('/api/emoji/history')
def history(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    f=Depends(filters),user=Depends(current_user),db=Depends(db_session)):
    q=scoped_records(db,user,**f)
    total=db.scalar(select(func.count()).select_from(q.subquery()))
    rows=db.scalars(q.order_by(EmojiRecord.timestamp.desc(),EmojiRecord.id.desc()).offset((page-1)*page_size).limit(page_size))
    return dict(items=[serialize_record(db,r) for r in rows],total=total,page=page,page_size=page_size)


@app.get('/api/emoji/statistics')
def get_statistics(f=Depends(filters),user=Depends(current_user),db=Depends(db_session)):
    return statistics(db,list(db.scalars(scoped_records(db,user,**f))))


@app.get('/api/admin/statistics')
def admin_statistics(f=Depends(filters),user=Depends(teacher_or_admin),db=Depends(db_session)):
    return statistics(db,list(db.scalars(scoped_records(db,user,**f))))


@app.get('/api/admin/dashboard/realtime')
def realtime(sessionId:int,user=Depends(teacher_or_admin),db=Depends(db_session)):
    visible_session(db,user,sessionId)
    return statistics(db,list(db.scalars(scoped_records(db,user,session_id=sessionId))))


@app.get('/api/admin/emoji/export')
def export(f=Depends(filters),user=Depends(admin),db=Depends(db_session)):
    data=export_csv(db,list(db.scalars(scoped_records(db,user,**f).order_by(EmojiRecord.timestamp,EmojiRecord.id))))
    audit(db,user.id,'emoji.export');db.commit()
    return Response(data,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="emoji-records.csv"'})


@app.get('/api/admin/audit')
def audits(user=Depends(admin),db=Depends(db_session)):
    return [dict(id=a.id,actor=username(db,a.actor_id),action=a.action,detail=a.detail,created_at=iso(a.created_at))
        for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100))]


@app.get('/api/ai/config')
def config(user=Depends(teacher_or_admin)):
    return {**ai_config(),'model_version':'emotion-ferplus-8'}


@app.post('/api/ai/emoji-results')
def ai_result(data:S.AIResult,_=Depends(ai_auth),db=Depends(db_session)):
    return accept_ai(db,data)


@app.post('/api/ai/frame',openapi_extra={'requestBody':{'required':True,'content':{'multipart/form-data':{'schema':{'type':'object','required':['file'],'properties':{'file':{'type':'string','format':'binary'}}}}}}})
async def frame(request:Request,session_id:int,user=Depends(teacher_or_admin),db=Depends(db_session)):
    s=visible_session(db,user,session_id);active_session(s)
    # Parse a bounded request entirely in RAM. UploadFile normally spools frames
    # larger than 1 MB to a temporary file, which this endpoint must never do.
    ctype=request.headers.get('content-type','')
    if not ctype.lower().startswith('multipart/form-data') or '\r' in ctype or '\n' in ctype:
        fail(415,'请使用 multipart/form-data 上传图像')
    buffer=bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer)>2*1024*1024+65536:fail(413,'图像不能超过2MB')
    try:
        message=BytesParser(policy=email_policy).parsebytes(b'Content-Type: '+ctype.encode('ascii')+b'\r\nMIME-Version: 1.0\r\n\r\n'+bytes(buffer))
        parts=list(message.iter_parts())
        if len(parts)!=1 or parts[0].get_param('name',header='content-disposition')!='file':raise ValueError()
        content=parts[0].get_payload(decode=True)
        mime=parts[0].get_content_type()
    except (ValueError,UnicodeError,TypeError):fail(422,'图像上传格式无效')
    if not content:fail(422,'图像为空')
    if len(content)>2*1024*1024:fail(413,'图像不能超过2MB')
    if mime not in ['image/jpeg','image/png']:fail(415,'请使用JPEG或PNG图像')
    token=os.getenv('AI_SERVICE_TOKEN','')
    if not token:fail(503,'AI服务尚未配置')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result=await client.post(os.getenv('AI_URL','http://127.0.0.1:8011')+'/infer',
                headers={'Authorization':'Bearer '+token},files={'file':('frame.jpg',content,mime)})
    except httpx.HTTPError:fail(503,'AI服务暂时无法连接，请稍后重试')
    if result.status_code!=200:
        if result.status_code in [413,415,422]:fail(result.status_code,'图像无法识别，请重新采样')
        fail(503,'AI模型尚未就绪，请检查AI服务')
    try:
        inferred=result.json();results=inferred['results'];detected=int(inferred['detected'])
        if not isinstance(results,list) or len(results)>100 or detected<0:raise ValueError()
        payloads=[S.AIResult(session_id=session_id,emoji=r['emoji'],confidence=r['confidence'],timestamp=iso(now()),
            device_id='classroom-browser',event_id=str(uuid.uuid4()),model_version=r.get('model_version',inferred.get('model_version','emotion-ferplus-8'))) for r in results]
    except (ValueError,KeyError,TypeError):fail(502,'AI服务返回格式不正确')
    accepted=[];output=[]
    for payload in payloads:
        saved=accept_ai(db,payload)
        output.append(dict(emoji=payload.emoji,confidence=payload.confidence,accepted=saved['accepted'],model_version=payload.model_version))
        if saved['accepted']:accepted.append(saved['record'])
    return dict(detected=detected,accepted=len(accepted),rejected=len(output)-len(accepted),results=output,
        message='未检测到人脸，请调整摄像头位置' if detected==0 else f'已记录{len(accepted)}条课堂表情')


@app.websocket('/ws/dashboard')
async def dashboard(websocket:WebSocket,sessionId:int):
    origin=websocket.headers.get('origin')
    if origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc!=websocket.headers.get('host'):
            await websocket.close(code=1008);return
    token=websocket.cookies.get('emoji_session','')
    with SessionLocal() as db:
        u=resolve_user(db,token)
        if not u or u.role not in ['teacher','admin']:
            await websocket.close(code=1008);return
        try:visible_session(db,u,sessionId)
        except HTTPException:
            await websocket.close(code=1008);return
    await websocket.accept()
    try:
        while True:
            with SessionLocal() as db:
                u=resolve_user(db,token)
                if not u or u.role not in ['teacher','admin']:
                    await websocket.close(code=1008);return
                try:visible_session(db,u,sessionId)
                except HTTPException:
                    await websocket.close(code=1008);return
                data=statistics(db,list(db.scalars(scoped_records(db,u,session_id=sessionId))))
                await websocket.send_json(dict(type='statistics',data=data))
            await asyncio.sleep(2)
    except (WebSocketDisconnect,RuntimeError):pass


_framework_openapi=app.openapi


def documented_openapi():
    schema=_framework_openapi()
    schemes=schema.setdefault('components',{}).setdefault('securitySchemes',{})
    schemes.update({
        'SessionCookie':{'type':'apiKey','in':'cookie','name':'emoji_session'},
        'UserBearer':{'type':'http','scheme':'bearer','description':'用户登录返回的access_token'},
        'AIServiceToken':{'type':'http','scheme':'bearer','description':'独立AI_SERVICE_TOKEN，不接受用户令牌'}})
    for path,methods in schema['paths'].items():
        if not path.startswith('/api/'):continue
        for method,operation in methods.items():
            if not isinstance(operation,dict):continue
            if path=='/api/ai/emoji-results':operation['security']=[{'AIServiceToken':[]}]
            elif path not in ['/api/auth/register','/api/auth/login']:
                operation['security']=[{'SessionCookie':[]},{'UserBearer':[]}]
            if method in ['post','put','patch','delete'] and path!='/api/ai/emoji-results':
                parameters=operation.setdefault('parameters',[])
                if not any(p.get('name')=='X-Requested-With' for p in parameters):
                    parameters.append({'name':'X-Requested-With','in':'header','required':True,
                        'schema':{'type':'string','const':'EmojiApp','default':'EmojiApp'},'description':'浏览器写请求校验头'})
    return schema


app.openapi=documented_openapi
