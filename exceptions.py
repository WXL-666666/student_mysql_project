class StudentError(Exception):
    """本项目所有业务异常的基类。

    子类用 `status_code` 声明自己对应的 HTTP 状态码，由 api 层的
    exception_handler 统一读取 —— 这样"找不到资源"和"参数不合法"
    能返回不同的状态码，不会再一律变成 404。
    """

    status_code: int = 400


class StudentNotFoundError(StudentError):
    """按 id 找不到学生 —— 资源不存在 → 404"""

    status_code = 404

    def __init__(self, student_id: int):
        self.student_id = student_id
        super().__init__(f"未找到学生 id={student_id}")


class InvalidAgeError(StudentError):
    """年龄超出合理范围 —— 输入不合法 → 422

    这里用 422 而不是 400，是为了跟 API 边界上 Pydantic 的校验失败保持一致：
    同一个"年龄不合法"，无论被哪一层拦下，对外都是 422。
    """

    status_code = 422

    def __init__(self, age: int):
        self.age = age
        super().__init__(f"年龄不合法：{age}（必须在 0-150 之间）")


class EmptyGradeError(StudentError):
    """成绩为空或只有空白 —— 输入不合法 → 422"""

    status_code = 422

    def __init__(self):
        super().__init__("成绩不能为空")
