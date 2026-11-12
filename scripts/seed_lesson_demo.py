"""Create classroom accounts for the course demonstration."""
import os
import bcrypt
from app.models import Base, engine, SessionLocal, User

ACCOUNTS = {'student': '袁谦朗', 'student2': '吴卫昊', 'student3': '李阳', 'student4': '吕祖灿',
            'teacher': '丁老师', 'admin': '教学管理员'}


def main():
    password = os.environ['DEMO_PASSWORD']
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for role, name in ACCOUNTS.items():
            if role=='student4':continue
            db.add(User(username=name, role='student' if role.startswith('student') else role,
                email='', password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()))
        db.commit()
    print('已创建课堂账号，吕祖灿通过注册页面加入课堂。')


if __name__ == '__main__':
    main()
