"""baseline: create students table

基线迁移（baseline）。

说明：本文件最初是 autogenerate 出来的「增量同步」迁移，内容为
`drop_table('courses')` + 若干 `alter_column('students', ...)`——
它只对「开发机上那个由 init_db.sql 手写的旧库」成立。
换到全新空库执行时，`courses` 与 `students` 都不存在，迁移直接报
`1051 Unknown table 'student_db.courses'`，即不可重放。

2026-11-02 重写为真正的基线：从零创建 `students` 表，
与 models.py 完全对齐（含 CHECK 约束与 id 索引）。
MySQL 下 autogenerate 不会生成 CHECK 约束，故此处手写 create_check_constraint 的等价物。

Revision ID: 95cfb7f73f7e
Revises:
Create Date: 2026-10-14 10:44:52.412283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '95cfb7f73f7e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级：从零创建 students 表。"""
    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('grade', sa.String(length=10), nullable=False),
        # 与 models.py 的 CheckConstraint 保持一致；MySQL autogenerate 不会带出来，必须手写
        sa.CheckConstraint('age >= 0 AND age <= 150', name='ck_students_age_range'),
        sa.PrimaryKeyConstraint('id'),
        mysql_engine='InnoDB',
        mysql_default_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index(op.f('ix_students_id'), 'students', ['id'], unique=False)


def downgrade() -> None:
    """回滚：删掉 students 表。"""
    op.drop_index(op.f('ix_students_id'), table_name='students')
    op.drop_table('students')
