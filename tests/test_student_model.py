from sqlalchemy import select

from models import Student


def test_insert_and_read(db_session):
    # Arrange
    student = Student(name="张三", age=18, grade="A")

    # Act
    db_session.add(student)

    # 🔮 这里先别 commit，看下面的预测题
    print("commit 前的 id：", student.id)

    db_session.commit()
    print("commit 后的 id：", student.id)

    # Assert
    got = db_session.get(Student, student.id)
    assert got.name == "张三"
    assert got.age == 18


def test_table_starts_empty(db_session):
    """验证 fixture 真的把表清空了"""
    rows = db_session.execute(select(Student)).scalars().all()
    assert rows == []