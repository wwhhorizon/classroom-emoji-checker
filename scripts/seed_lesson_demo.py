"""Create fictional lesson accounts only; courses and feedback arise on screen."""
import os
import bcrypt
from app.models import Base, engine, SessionLocal, User

ACCOUNTS = {'student': '林予安', 'student2': '陈知远', 'teacher': '周老师', 'admin': '教学管理员'}


def main():
    password = os.environ['DEMO_PASSWORD']
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for role, name in ACCOUNTS.items():
            db.add(User(username=name, role='student' if role == 'student2' else role,
                email='', password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()))
        db.commit()
    print('已创建四个虚构课堂演示账号；课程、课堂和表情记录均为空。')


if __name__ == '__main__':
    main()
