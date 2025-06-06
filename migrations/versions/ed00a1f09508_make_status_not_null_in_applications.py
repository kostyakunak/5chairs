"""make status not null in applications

Revision ID: ed00a1f09508
Revises: ca961e6b0522
Create Date: 2025-05-12 13:03:17.737194

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed00a1f09508'
down_revision = 'ca961e6b0522'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('applications', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    # Очистка "битых" участников (user_id которых нет в users)
    op.execute('DELETE FROM meeting_members WHERE user_id NOT IN (SELECT id FROM users);')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('applications', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    # ### end Alembic commands ###