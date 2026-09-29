"""Add asset-manager role for data-center ecosystem tracking.

Revision ID: 0018_investor_builder_roles
Revises: 0017_sankun_source
"""
from __future__ import annotations
from typing import Sequence,Union
from alembic import op

revision:str="0018_investor_builder_roles"
down_revision:Union[str,None]="0017_sankun_source"
branch_labels:Union[str,Sequence[str],None]=None
depends_on:Union[str,Sequence[str],None]=None

def upgrade()->None:
 op.execute("""
 INSERT INTO company_role_type(role_code,role_name,description)
 VALUES('ASSET_MANAGER','자산운용사','데이터센터 펀드·리츠·부동산 자산의 투자 및 운용 주체')
 ON CONFLICT(role_code) DO UPDATE SET role_name=EXCLUDED.role_name,description=EXCLUDED.description
 """)

def downgrade()->None:
 op.execute("DELETE FROM company_role_type WHERE role_code='ASSET_MANAGER'")
