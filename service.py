from sqlalchemy.orm import Session

from repository import StudentRepository
from exceptions import StudentNotFoundError, InvalidAgeError, EmptyGradeError
from models import Student

AGE_MIN = 0
AGE_MAX = 150

class StudentService:
    def __init__(self, repo: StudentRepository):
        """业务规则层。所有入口都应该走这里，不要直接用 Repository"""
        self.repo = repo

    def register(self, name: str, age: int, grade: str) -> Student:
        """注册学生"""
        self._validate_age(age)
        self._validate_grade(grade)      # 创建时也要校验，否则空格成绩能进库
        return self.repo.add(name, age, grade)

    def batch_register(self, rows: list[tuple[str, int, str]]) -> list[Student]:
        # 先全部校验，再全部写入——避免"存了一半才发现第三个不合法"
        for name, age, grade in rows:
            self._validate_age(age)
            self._validate_grade(grade)
        return self.repo.batch_add(rows)

    def get(self, student_id: int) -> Student:
        return self.repo.get(student_id)   # repo.get 找不到会自己抛 StudentNotFoundError，service 不用重复查

    def list_all(self) -> list[Student]:
        return self.repo.list_all()

    def list_page(self,limit:int,offset:int) -> tuple[list[Student],int]:
        return self.repo.list_all(limit=limit,offset=offset),self.repo.count_all()

    def change_grade(self, student_id: int, new_grade: str) -> Student:
        self._validate_grade(new_grade)
        return self.repo.update_grade(student_id, new_grade)

    def remove(self, student_id: int) -> None:
        self.repo.delete(student_id)

    @staticmethod
    def _validate_grade(grade: str) -> None:
        """成绩不能为空或全空白。

        创建和改分必须用同一条规则——否则会出现"创建时能塞空格、改分时被拒"
        这种前后不一致，脏数据就进来了。
        """
        if not grade or not grade.strip():
            raise EmptyGradeError()

    @staticmethod
    def _validate_age(age: int) -> None:
        if not (AGE_MIN <= age <= AGE_MAX):
            raise InvalidAgeError(age) 
