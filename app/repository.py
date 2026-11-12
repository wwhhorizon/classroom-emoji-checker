from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Course, ClassSession, ScheduleUser, EmojiRecord, User


def scoped_sessions(db, user):
    q = select(ClassSession).join(Course)
    if user.role == 'teacher': q = q.where(Course.teacher_id == user.id)
    if user.role == 'student':
        q = q.where(ClassSession.id.in_(select(ScheduleUser.session_id).where(ScheduleUser.user_id==user.id)))
    return q


def visible_session(db,user,session_id):
    session=db.scalar(scoped_sessions(db,user).where(ClassSession.id==session_id))
    if not session: raise HTTPException(404,'课堂不存在或无权访问')
    return session


def parse_time(value):
    if not value: return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None: raise ValueError()
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError: raise HTTPException(422,'筛选时间必须是含时区的 ISO 时间')


def scoped_records(db,user,session_id=None,course=None,class_name=None,from_time=None,to_time=None,source=None):
    start,end=parse_time(from_time),parse_time(to_time)
    if start and end and start>end: raise HTTPException(422,'筛选开始时间不能晚于结束时间')
    if source and source not in ['AI','MANUAL']: raise HTTPException(422,'记录来源无效')
    q=select(EmojiRecord).join(ClassSession).join(Course)
    if user.role=='student': q=q.where(EmojiRecord.user_id==user.id)
    elif user.role=='teacher':q=q.where(Course.teacher_id==user.id)
    if session_id:
        visible_session(db,user,session_id)
        q=q.where(EmojiRecord.session_id==session_id)
    if course: q=q.where(Course.id==course)
    if class_name: q=q.where(ClassSession.class_name==class_name)
    if start:q=q.where(EmojiRecord.timestamp>=start)
    if end:q=q.where(EmojiRecord.timestamp<=end)
    if source:q=q.where(EmojiRecord.source==source)
    return q


def username(db,uid):
    u=db.get(User,uid) if uid else None
    return u.username if u else None
