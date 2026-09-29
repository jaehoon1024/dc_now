"""Register Samsung SDS and Kakao official newsroom sources.

Revision ID: 0016_it_company_sources
Revises: 0015_evidence_review
"""
from __future__ import annotations
from typing import Sequence,Union
from alembic import op

revision:str="0016_it_company_sources"
down_revision:Union[str,None]="0015_evidence_review"
branch_labels:Union[str,Sequence[str],None]=None
depends_on:Union[str,Sequence[str],None]=None

def upgrade()->None:
 op.execute("""
 INSERT INTO source_registry(source_code,source_name,source_type,base_url,default_source_grade,collection_method,collection_interval,terms_review_status,owner_name,active,note,collection_policy,content_storage_policy,robots_review_status,request_interval_seconds,allowed_content_scope,compliance_checked_on,legal_approval_required,compliance_note)
 VALUES
 ('SAMSUNG_SDS_NEWS','삼성SDS 공식 뉴스룸','COMPANY','https://www.samsungsds.com/kr/news/', 'B','MANUAL','WEEKLY','LIMITED','삼성SDS',true,'데이터센터·클라우드 인프라 공식 발표','MANUAL_ONLY','METADATA_ONLY','NOT_REVIEWED',30,'공식 발표 제목·URL·게시일과 공개 시설 정보만 수동 검토',CURRENT_DATE,true,'자동 수집 전 robots·이용조건 별도 검토'),
 ('KAKAO_NEWS','카카오 공식 뉴스룸','COMPANY','https://www.kakaocorp.com/page/service/service/KakaoNews', 'B','MANUAL','WEEKLY','LIMITED','카카오',true,'데이터센터·클라우드 인프라 공식 발표','MANUAL_ONLY','METADATA_ONLY','NOT_REVIEWED',30,'공식 발표 제목·URL·게시일과 공개 시설 정보만 수동 검토',CURRENT_DATE,true,'자동 수집 전 robots·이용조건 별도 검토')
 ON CONFLICT(source_code) DO NOTHING
 """)

def downgrade()->None:
 op.execute("DELETE FROM source_registry WHERE source_code IN ('SAMSUNG_SDS_NEWS','KAKAO_NEWS')")
