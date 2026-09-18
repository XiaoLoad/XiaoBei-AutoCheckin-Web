"""add push_groups.image_group_id

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a3
Create Date: 2026-09-18 12:50:00.000000

给分组挂图库归属：配置套图片策略选「按分组取图」时，组内账号按本字段取图。
ondelete=SET NULL —— 图库分组被删时自动解绑，不阻塞图库分组的删除。
NULL 表示未绑定，运行时回退到配置套默认图库（再回退全部图库）。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d0e1f2a3b5'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('push_groups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_group_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_push_groups_image_group_id'), ['image_group_id'], unique=False)
        batch_op.create_foreign_key('fk_push_groups_image_group_id', 'image_groups',
                                    ['image_group_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('push_groups', schema=None) as batch_op:
        batch_op.drop_constraint('fk_push_groups_image_group_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_push_groups_image_group_id'))
        batch_op.drop_column('image_group_id')
