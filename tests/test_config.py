"""配置校验的测试。

为什么要测这个：`config.py` 里的两个校验分支不产生业务价值，
但它们产出的**报错信息**是用户唯一能看到的东西 ——
如果哪天有人把 `raise` 改成 `pass`，问题就退回成那个完全看不懂的
`UnicodeEncodeError: 'latin-1' codec can't encode characters`。
"""
import pytest

from config import _validate_password

# 纯函数校验，不碰数据库 → unit
pytestmark = pytest.mark.unit


def test_valid_password_passes():
    """正常密码不报错（不抛异常就算过）"""
    _validate_password("Abc123!@#")


@pytest.mark.parametrize("bad", ["", "   ", None, "改成你的密码", "<your-password>"])
def test_placeholder_password_rejected(bad):
    """空值 / 纯空白 / 各种占位符都要给出「请去改 .env」的提示"""
    with pytest.raises(RuntimeError, match="占位符"):
        _validate_password(bad)


def test_non_ascii_password_rejected():
    """含中文的密码要明确说出「PyMySQL 用 latin1 编码」这个原因"""
    with pytest.raises(RuntimeError, match="非 ASCII"):
        _validate_password("我的密码123")
