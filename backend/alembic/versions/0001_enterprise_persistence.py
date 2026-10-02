"""enterprise persistence baseline"""
from alembic import op
import sqlalchemy as sa
revision='0001_enterprise_persistence'; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('users',sa.Column('username',sa.String(50),primary_key=True),sa.Column('display_name',sa.String(80),nullable=False),sa.Column('password_hash',sa.Text(),nullable=False),sa.Column('role',sa.String(20),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False))
    op.create_table('work_orders',sa.Column('id',sa.String(40),primary_key=True),sa.Column('asset_id',sa.String(80),nullable=False,index=True),sa.Column('title',sa.String(140),nullable=False),sa.Column('priority',sa.String(20),nullable=False),sa.Column('assignee',sa.String(100),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True)))
    op.create_table('incidents',sa.Column('id',sa.String(40),primary_key=True),sa.Column('asset_id',sa.String(80),nullable=False,index=True),sa.Column('title',sa.String(140),nullable=False),sa.Column('severity',sa.String(20),nullable=False),sa.Column('description',sa.Text(),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('owner',sa.String(50),nullable=False),sa.Column('opened_at',sa.DateTime(timezone=True),nullable=False),sa.Column('resolved_at',sa.DateTime(timezone=True)))
    op.create_table('api_keys',sa.Column('id',sa.String(40),primary_key=True),sa.Column('name',sa.String(80),nullable=False),sa.Column('prefix',sa.String(20),nullable=False),sa.Column('key_hash',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False))
    op.create_table('platform_settings',sa.Column('key',sa.String(80),primary_key=True),sa.Column('value',sa.Text(),nullable=False))
    op.create_table('audit_events',sa.Column('id',sa.String(40),primary_key=True),sa.Column('actor',sa.String(50),nullable=False),sa.Column('action',sa.String(80),nullable=False),sa.Column('resource',sa.String(140),nullable=False),sa.Column('timestamp',sa.DateTime(timezone=True),nullable=False,index=True))
def downgrade():
    for table in ['audit_events','platform_settings','api_keys','incidents','work_orders','users']: op.drop_table(table)
