"""Add review workflow fields to evidence documents.

Revision ID: 0015_evidence_review
Revises: 0014_block_lgcns_automation
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0015_evidence_review"
down_revision: Union[str, None] = "0014_block_lgcns_automation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column("evidence_document", sa.Column("review_status", sa.String(20), nullable=False, server_default="CANDIDATE"))
    op.add_column("evidence_document", sa.Column("reviewed_by", sa.String(150)))
    op.add_column("evidence_document", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("evidence_document", sa.Column("review_note", sa.Text()))
    op.create_check_constraint("ck_evidence_document_review_status", "evidence_document", "review_status IN ('CANDIDATE','CONFIRMED','CONFLICT','REJECTED')")
    op.create_index("idx_evidence_document_review", "evidence_document", ["review_status", "published_at"])

def downgrade():
    op.drop_index("idx_evidence_document_review", table_name="evidence_document")
    op.drop_constraint("ck_evidence_document_review_status", "evidence_document", type_="check")
    for name in ("review_note", "reviewed_at", "reviewed_by", "review_status"):
        op.drop_column("evidence_document", name)
