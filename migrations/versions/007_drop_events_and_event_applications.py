"""drop events and event_applications tables

Revision ID: 007_drop_events_and_event_applications
Revises: <укажи предыдущий revision id>
Create Date: 2024-06-07 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '007_drop_events_and_event_applications'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.drop_table('event_applications')
    op.drop_table('events')

def downgrade():
    # Если потребуется откат, можно восстановить таблицы вручную (структуру можно взять из старых миграций)
    pass 