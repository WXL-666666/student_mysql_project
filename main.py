from sqlalchemy.orm import Session

from db import engine
from exceptions import StudentError
from models import Base
from repository import StudentRepository
from service import StudentService


def print_students(service: StudentService):
    for s in service.list_all():
        print(f"学号：{s.id} 姓名：{s.name} 年龄：{s.age} 成绩：{s.grade}")


def main():
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = StudentRepository(session)
        service = StudentService(repo)

        # ── 事务 1：注册两个学生 ──
        service.register("张三", 18, "A")
        service.register("李四", 19, "B")
        session.commit()

        print("\n当前所有学生：")
        print_students(service)

        # ── 事务 2：改成绩 ──
        try:
            service.change_grade(1, "A+")
            session.commit()
        except StudentError as e:              # ← 一个 except 接住所有业务异常
            session.rollback()
            print(f"改成绩失败：{e}")

        # ── 事务 3：删除 ──
        try:
            service.remove(4)
            session.commit()
        except StudentError as e:
            session.rollback()
            print(f"删除失败：{e}")

        # ── 事务 4：故意触发年龄校验 ──
        try:
            service.register("非法学生", -5, "C")
            session.commit()
        except StudentError as e:
            session.rollback()
            print(f"注册失败：{e}")

        print("\n操作后的学生：")
        print_students(service)


if __name__ == "__main__":
    main()