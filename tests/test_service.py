import pytest
from models import Student
from exceptions import InvalidAgeError, StudentNotFoundError, EmptyGradeError   

pytestmark = pytest.mark.unit

# ---------- 业务规则测试：全程没有数据库 ----------

@pytest.mark.parametrize("bad_age", [-1, -5, 151, 999])
def test_register_rejects_invalid_age(service, bad_age):
    with pytest.raises(InvalidAgeError):
        service.register("张三", bad_age, "A")


@pytest.mark.parametrize("good_age", [0, 1, 18, 120, 150])
def test_register_accepts_valid_age(service, good_age):
    student = service.register("张三", good_age, "A")
    assert student.age == good_age


def test_batch_register_validates_all_before_writing(service, fake_repo):
    """批次里有一个非法，整批都不该写入"""
    with pytest.raises(InvalidAgeError):
        service.batch_register([("甲", 18, "A"), ("乙", -1, "B")])

    assert fake_repo.rows == []          # ← 一条都没写进去


def test_change_grade_rejects_empty(service):
    service.register("张三", 18, "A")
    with pytest.raises(EmptyGradeError):
        service.change_grade(1, "   ")


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t"])
def test_register_rejects_blank_grade(service, blank):
    """创建时也要拦空白成绩。

    以前 register 只校验 age，于是 POST grade=" " 能建成功（201），
    而改分时同样的值被拒（422）——同一条规则两个入口不一致，
    空格成绩就这样混进了库。
    """
    with pytest.raises(EmptyGradeError):
        service.register("张三", 18, blank)


def test_batch_register_rejects_blank_grade(service, fake_repo):
    """批量创建走的是另一条路径，同样要拦"""
    with pytest.raises(EmptyGradeError):
        service.batch_register([("甲", 18, "A"), ("乙", 18, "  ")])
    assert fake_repo.rows == []


def test_get_raises_when_not_found(service):
    with pytest.raises(StudentNotFoundError):
        service.get(999)