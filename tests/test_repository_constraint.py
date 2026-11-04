import pytest
from sqlalchemy.exc import OperationalError
from models import Student

# 真 MySQL：测的是数据库 CHECK 约束，必须连真库 → integration
pytestmark = pytest.mark.integration


def  test_database_rejects_negative_age(db_session):
    """最后一道防线：绕过 Service 直接写库，数据库也会拦"""
    db_session.add(Student(name="绕过校验", age=-5, grade="A"))

    with pytest.raises(OperationalError):
        db_session.commit()

    db_session.rollback()
