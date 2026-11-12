import csv
import io
import math
import os
from collections import Counter
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from app.models import (User, Course, ClassSession, ScheduleUser, EmojiRecord, AuditLog, EMOJIS, now, iso)
from app.repository import username


def fail(code,message): raise HTTPException(code,message)


def audit(db,uid,action,detail=''):
    db.add(AuditLog(actor_id=uid,action=action,detail=detail))


def public_user(u):
    return dict(id=u.id,username=u.username,role=u.role,email=u.email,active=bool(u.active))


def serialize_session(db,s,user):
    c=db.get(Course,s.course_id)
    scheduled=list(db.scalars(select(ScheduleUser.user_id).where(ScheduleUser.session_id==s.id)))
    return dict(id=s.id,course_id=c.id,course=c.name,teacher_id=c.teacher_id,teacher=username(db,c.teacher_id),
        start_at=iso(s.start_at),end_at=iso(s.end_at),class_name=s.class_name,room=s.room,
        scheduled_count=len(scheduled),enrolled=user.id in scheduled,version=s.version)


def serialize_record(db,r):
    s=db.get(ClassSession,r.session_id);c=db.get(Course,s.course_id)
    return dict(id=r.id,user_id=r.user_id,username=username(db,r.user_id),session_id=r.session_id,
        course_id=c.id,course=c.name,class_name=s.class_name,emoji=r.emoji,source=r.source,
        confidence=r.confidence,device_id=r.device_id,model_version=r.model_version,timestamp=iso(r.timestamp))


def active_session(s, timestamp=None):
    current=now()
    if not s.start_at<=current<=s.end_at:fail(409,'当前不在课堂时间内')
    if timestamp is not None:
        if not s.start_at<=timestamp<=s.end_at:fail(422,'采样时间不在课堂时间内')
        if timestamp>current+timedelta(seconds=30) or timestamp<current-timedelta(minutes=5):
            fail(422,'采样时间已过期或超前，请检查设备时间')


def bump_version(db,s,version,values=None):
    if s.version!=version:fail(409,'课堂已更新，请刷新后重试')
    values={**(values or {}),'version':version+1}
    changed=db.execute(update(ClassSession).where(ClassSession.id==s.id,ClassSession.version==version).values(**values))
    if changed.rowcount!=1:
        db.rollback();fail(409,'课堂已更新，请刷新后重试')


def lock_session(db,s):
    """Serialize feedback insertion against concurrent roster/time changes.

    A matched no-op UPDATE obtains a write lock without changing the visible
    scheduling version. If an administrator changed the roster after our read,
    the version predicate fails instead of accepting a stale enrollment.
    """
    matched=db.execute(update(ClassSession).where(ClassSession.id==s.id,ClassSession.version==s.version).values(version=s.version))
    if matched.rowcount!=1:
        db.rollback();fail(409,'课堂安排已更新，请刷新后重新提交')


def replace_schedule(db,s,payload,user):
    if payload.user_ids:
        valid=list(db.scalars(select(User.id).where(User.id.in_(payload.user_ids),User.role=='student',User.active==1)))
        if len(valid)!=len(payload.user_ids):fail(422,'名单只能包含有效的学生账号')
    bump_version(db,s,payload.version)
    db.execute(delete(ScheduleUser).where(ScheduleUser.session_id==s.id))
    db.add_all(ScheduleUser(session_id=s.id,user_id=uid) for uid in payload.user_ids)
    audit(db,user.id,'session.schedule',str(s.id));db.commit();db.refresh(s)
    return serialize_session(db,s,user)


def ai_config():
    try:
        threshold=float(os.getenv('AI_CONFIDENCE_THRESHOLD','0.6'))
        sample=float(os.getenv('AI_SAMPLE_SECONDS','3'))
        if not math.isfinite(threshold) or not 0<=threshold<=1 or not math.isfinite(sample) or not 0.5<=sample<=60:raise ValueError()
    except ValueError:fail(503,'AI采样配置无效')
    return dict(threshold=threshold,sample_seconds=sample)


def accept_ai(db,data):
    # MySQL DATETIME and the public API use seconds; normalize before comparing
    # a retry so both supported databases resolve the same event identically.
    data=data.model_copy(update={'timestamp':data.timestamp.replace(microsecond=0)})
    old=db.scalar(select(EmojiRecord).where(EmojiRecord.event_id==data.event_id))
    if old:
        same=(old.session_id==data.session_id and old.user_id==data.user_id and old.emoji==data.emoji
            and old.device_id==data.device_id and old.model_version==data.model_version
            and old.timestamp==data.timestamp and math.isclose(old.confidence,data.confidence,rel_tol=0,abs_tol=1e-6))
        if not same:fail(409,'事件编号已用于其他结果')
        return dict(accepted=True,duplicate=True,record=serialize_record(db,old))
    s=db.get(ClassSession,data.session_id)
    if not s:fail(404,'课堂不存在')
    active_session(s,data.timestamp)
    lock_session(db,s)
    if data.user_id:
        u=db.get(User,data.user_id)
        if not u or not u.active or u.role!='student' or not db.scalar(select(ScheduleUser.id).where(ScheduleUser.session_id==s.id,ScheduleUser.user_id==u.id)):
            fail(422,'关联学生不在课堂名单中')
    if data.confidence<ai_config()['threshold']:return dict(accepted=False,reason='below_threshold')
    r=EmojiRecord(**data.model_dump(),source='AI')
    db.add(r)
    try:
        db.flush();audit(db,None,'emoji.ai',f'session={s.id}');db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent delivery of the same event is resolved by the unique index.
        return accept_ai(db,data)
    return dict(accepted=True,record=serialize_record(db,r))


def statistics(db,records):
    distribution={k:0 for k in EMOJIS}
    minutes={};courses=Counter();classes=Counter()
    for r in records:
        distribution[r.emoji]+=1
        minute=iso(r.timestamp.replace(second=0,microsecond=0))
        if minute not in minutes:minutes[minute]=dict(minute=minute,total=0,**{k:0 for k in EMOJIS})
        minutes[minute]['total']+=1;minutes[minute][r.emoji]+=1
        s=db.get(ClassSession,r.session_id);c=db.get(Course,s.course_id)
        courses[c.name]+=1;classes[s.class_name]+=1
    return dict(total=len(records),manual=sum(r.source=='MANUAL' for r in records),
        ai=sum(r.source=='AI' for r in records),participants=len({r.user_id for r in records if r.user_id}),
        distribution=distribution,trend=[minutes[k] for k in sorted(minutes)],
        courses=[dict(name=k,total=v) for k,v in courses.items()],classes=[dict(name=k,total=v) for k,v in classes.items()])


def safe_cell(v):
    text='' if v is None else str(v)
    return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else text


def export_csv(db,records):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['记录编号','用户','课堂编号','课程','班级','表情','来源','置信度','设备','模型版本','采样时间UTC'])
    for r in records:
        d=serialize_record(db,r)
        writer.writerow([safe_cell(d[k]) for k in ['id','username','session_id','course','class_name','emoji','source','confidence','device_id','model_version','timestamp']])
    return '\ufeff'+out.getvalue()
