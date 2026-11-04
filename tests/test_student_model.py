import pytest
from sqlalchemy import select
from factories import StudentFactory
from models import Student

# 真 MySQL：db_session 直接建连接 → integration
pytestmark = pytest.mark.integration


def test_insert_and_read(db_session):
    # Arrange
    student = StudentFactory.build(age=18, name="张三", grade="A")

    # Act
    db_session.add(student)
    db_session.commit()

    # Assert
    got = db_session.get(Student, student.id)
    assert got.name == "张三"
    assert got.age == 18

def test_build_batch_makes_many(db_session):
    # Arrange
    students = StudentFactory.build_batch(5)
    for i in students:
        db_session.add(i)
    db_session.commit()

    rows = db_session.execute(select(Student)).scalars().all()
    assert len(rows) == 5
    assert all(0 <= s.age <= 150 for s in rows)

