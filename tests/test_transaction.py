import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from models import Student

# 真 MySQL：验证事务与 savepoint 行为 → integration
pytestmark = pytest.mark.integration


def count_students(session) -> int:
    return session.execute(select(func.count()).select_from(Student)).scalar()


def test_batch_add_persists_all(student_repo, db_session):
    rows = [("甲", 18, "A"), ("乙", 19, "B"), ("丙", 20, "C")]

    students = student_repo.batch_add(rows)
    db_session.commit()                      # ← commit 仍然由调用方管

    assert len(students) == 3
    assert count_students(db_session) == 3


def test_rollback_undoes_everything(student_repo, db_session):
    student_repo.batch_add([("甲", 18, "A"), ("乙", 19, "B")])
    db_session.rollback()

    assert count_students(db_session) == 0


def test_failed_batch_leaves_no_partial_data(student_repo, db_session):
    first = student_repo.add("甲", 18, "A")
    db_session.commit()

    students = student_repo.batch_add([("乙", 19, "B"), ("丙", 20, "C")])
    students[1].id = first.id                # ← 强行主键冲突

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert count_students(db_session) == 1