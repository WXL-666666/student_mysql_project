from sqlalchemy import select,func
from sqlalchemy.orm import Session

from exceptions import StudentNotFoundError
from models import Student

class StudentRepository:
    #"""只管数据存取。不认识任何业务规则——给它什么就存什么"""
    def __init__(self, session: Session):
        self.session = session

    def add(self, name: str, age: int, grade: str) -> Student:
        student = Student(name=name, age=age, grade=grade)
        self.session.add(student)
        self.session.flush()
        return student

    def get(self, student_id: int) -> Student:
        student = self.session.get(Student, student_id)
        if student is None:
            raise StudentNotFoundError(student_id)
        return student

    def list_all(self,limit:int | None = None,offset:int | None = None) -> list[Student]:
        stmt = select(Student).order_by(Student.id).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def count_all(self) ->int:
        return self.session.execute(
            select(func.count()).select_from(Student)
        ).scalar()

    def update_grade(self, student_id: int, new_grade: str) -> Student:
        student = self.get(student_id)
        student.grade = new_grade
        self.session.flush()
        return student

    def delete(self, student_id: int) -> None:
        student = self.get(student_id)
        self.session.delete(student)
        self.session.flush()

    def batch_add(self, rows: list[tuple[str, int, str]]) -> list[Student]:
        return [self.add(name, age, grade) for name, age, grade in rows]