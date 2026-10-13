"""Editable planning values with provenance, ranges and optimistic versions."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str = '0033_planning_values'
down_revision: Union[str,None] = '0032_operator_review'
branch_labels: Union[str,Sequence[str],None] = None
depends_on: Union[str,Sequence[str],None] = None

def upgrade():
    op.create_table('planning_value',
        sa.Column('planning_id',postgresql.UUID(as_uuid=True),primary_key=True,server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('dc_site.site_id'),nullable=False),
        sa.Column('scope_type',sa.String(10),nullable=False),sa.Column('scope_code',sa.String(30),nullable=False),
        sa.Column('field_name',sa.String(40),nullable=False),sa.Column('bucket',sa.String(20),nullable=False,server_default='GENERAL'),
        sa.Column('value',postgresql.JSONB,nullable=False),sa.Column('low_value',sa.Numeric(14,3)),sa.Column('high_value',sa.Numeric(14,3)),
        sa.Column('basis',sa.String(25),nullable=False),sa.Column('method',sa.Text,nullable=False),sa.Column('source_url',sa.Text),
        sa.Column('public_visible',sa.Boolean,nullable=False,server_default='false'),sa.Column('active',sa.Boolean,nullable=False,server_default='true'),
        sa.Column('version',sa.Integer,nullable=False,server_default='1'),sa.Column('updated_by',sa.String(100),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('site_id','scope_type','scope_code','field_name','bucket',name='uq_planning_target'),
        sa.CheckConstraint("scope_type IN ('SITE','PROJECT','PHASE')",name='ck_planning_scope'),
        sa.CheckConstraint("basis IN ('ANNOUNCED','ESTIMATED','MANUAL','MANUAL_CONFIRMED')",name='ck_planning_basis'),
        sa.CheckConstraint("bucket IN ('GENERAL','OPERATING','DEVELOPMENT')",name='ck_planning_bucket'),
        sa.CheckConstraint('version>0 AND (low_value IS NULL OR high_value IS NULL OR low_value<=high_value)',name='ck_planning_range'))
    op.create_index('idx_planning_site','planning_value',['site_id'])

def downgrade():
    op.drop_table('planning_value')
