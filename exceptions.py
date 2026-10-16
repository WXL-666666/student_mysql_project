class StudentError(Exception):
    """本项目所有业务异常的基类"""


class StudentNotFoundError(StudentError):
    """按 id 找不到学生"""

    def __init__(self, student_id: int):
        self.student_id = student_id
        super().__init__(f"未找到学生 id={student_id}")


class InvalidAgeError(StudentError):
    """年龄超出合理范围"""

    def __init__(self, age: int):
        self.age = age
        super().__init__(f"年龄不合法：{age}（必须在 0-150 之间）")

class EmptyGradeError(StudentError):
    """成绩为空或只有空白"""
    def __init__(self):
        super().__init__("成绩不能为空")
