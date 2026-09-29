"""Register Sankun construction intelligence as a manual source.

Revision ID: 0017_sankun_source
Revises: 0016_it_company_sources
"""
from __future__ import annotations
from typing import Sequence,Union
from alembic import op

revision:str="0017_sankun_source"
down_revision:Union[str,None]="0016_it_company_sources"
branch_labels:Union[str,Sequence[str],None]=None
depends_on:Union[str,Sequence[str],None]=None

def upgrade()->None:
 op.execute("""
 INSERT INTO source_registry(
  source_code,source_name,source_type,base_url,default_source_grade,
  collection_method,collection_interval,terms_review_status,owner_name,
  active,note,collection_policy,content_storage_policy,robots_url,
  robots_review_status,request_interval_seconds,allowed_content_scope,
  compliance_checked_on,legal_approval_required,compliance_note
 ) VALUES (
  'SANKUN','산군 건설 빅데이터 플랫폼','INDUSTRY','https://www.sankun.com/',
  'C','MANUAL','WEEKLY','LIMITED','산군',true,
  '건설 기업·현장·공사·입찰·수주·건축 인허가 보조 검증',
  'MANUAL_ONLY','URL_ONLY','https://www.sankun.com/robots.txt','PARTIAL',30,
  '로그인 없이 공개된 첫 화면과 허용된 공개 URL의 제목·원문 URL만 수동 확인. 검색·현장·입찰·뉴스·사용자 영역은 수집 제외',
  CURRENT_DATE,true,
  'robots.txt의 /search/, /site/, /bid/, /news/, /user/ 제한을 준수. 유료·로그인 데이터와 상세 본문은 저장하거나 재배포하지 않음'
 ) ON CONFLICT(source_code) DO UPDATE SET
  source_name=EXCLUDED.source_name,base_url=EXCLUDED.base_url,
  collection_method=EXCLUDED.collection_method,collection_interval=EXCLUDED.collection_interval,
  terms_review_status=EXCLUDED.terms_review_status,active=EXCLUDED.active,
  note=EXCLUDED.note,collection_policy=EXCLUDED.collection_policy,
  content_storage_policy=EXCLUDED.content_storage_policy,robots_url=EXCLUDED.robots_url,
  robots_review_status=EXCLUDED.robots_review_status,
  allowed_content_scope=EXCLUDED.allowed_content_scope,
  compliance_checked_on=EXCLUDED.compliance_checked_on,
  legal_approval_required=EXCLUDED.legal_approval_required,
  compliance_note=EXCLUDED.compliance_note,updated_at=CURRENT_TIMESTAMP
 """)

def downgrade()->None:
 op.execute("DELETE FROM source_registry WHERE source_code='SANKUN'")
