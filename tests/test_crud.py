import pytest
from models import Student
from exceptions import StudentNotFoundError
pytestmark = pytest.mark.integration

# ---------- Create ----------

def test_add_returns_object_with_id(student_repo):
    student = student_repo.add("张三", 18, "A")

    assert student.id is not None
    assert student.name == "张三"


# ---------- Read ----------

def test_list_all_returns_empty_when_no_data(student_repo):
    assert student_repo.list_all() == []


def test_list_all_returns_all_rows(student_repo):
    student_repo.add("张三", 18, "A")
    student_repo.add("李四", 19, "B")

    students = student_repo.list_all()

    assert len(students) == 2
    assert {s.name for s in students} == {"张三", "李四"}


# ---------- Update ----------

def test_update_grade_changes_value(student_repo):
    student = student_repo.add("张三", 18, "A")

    updated = student_repo.update_grade(student.id, "A+")

    assert updated.grade == "A+"
    assert student.grade == "A+"


def test_update_grade_raises_when_not_found(student_repo):
    with pytest.raises(StudentNotFoundError):
        student_repo.update_grade(999999, "A+")


# ---------- Delete ----------

def test_delete_removes_row(student_repo, db_session):
    student = student_repo.add("张三", 18, "A")

    student_repo.delete(student.id)

    assert db_session.get(Student, student.id) is None


def test_delete_raises_when_not_found(student_repo):
    with pytest.raises(StudentNotFoundError):
        student_repo.delete(999999)