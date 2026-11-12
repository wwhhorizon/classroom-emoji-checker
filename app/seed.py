"""Initialize accounts and classroom arrangements without any feedback history."""
import os
from datetime import timedelta
from sqlalchemy import select
import bcrypt
from app.models import Base, engine, SessionLocal, User, Course, ClassSession, ScheduleUser, now


def seed():
    password=os.getenv('DEMO_PASSWORD','')
    if len(password)<10:raise RuntimeError('请先运行 python scripts/dev.py --seed 生成本地配置')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        accounts={}
        for name,role in [('student','student'),('student2','student'),('teacher','teacher'),('teacher2','teacher'),('admin','admin')]:
            u=db.scalar(select(User).where(User.username==name))
            if not u:
                u=User(username=name,role=role,email='',password_hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode())
                db.add(u);db.flush()
            accounts[name]=u
        for i,(name,teacher) in enumerate([('软件工程实践','teacher'),('数据库系统','teacher2')]):
            course=db.scalar(select(Course).where(Course.name==name,Course.teacher_id==accounts[teacher].id))
            if course:continue
            course=Course(name=name,teacher_id=accounts[teacher].id);db.add(course);db.flush()
            s=ClassSession(course_id=course.id,start_at=now()-timedelta(hours=1),end_at=now()+timedelta(hours=3),class_name='计算机2301' if i==0 else '计算机2302',room='G2-B403' if i==0 else 'G2-B404')
            db.add(s);db.flush()
            for username in ['student','student2']:
                db.add(ScheduleUser(session_id=s.id,user_id=accounts[username].id))
        db.commit()
    print('已初始化账号 student / student2 / teacher / teacher2 / admin；密码见本地 .env DEMO_PASSWORD。未生成表情记录。')


if __name__=='__main__':seed()
