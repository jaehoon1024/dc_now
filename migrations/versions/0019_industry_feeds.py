"""Register Data Center News and Data Center Korea RSS sources.

Revision ID: 0019_industry_feeds
Revises: 0018_investor_builder_roles
"""
from __future__ import annotations
from typing import Sequence,Union
from alembic import op

revision:str="0019_industry_feeds"
down_revision:Union[str,None]="0018_investor_builder_roles"
branch_labels:Union[str,Sequence[str],None]=None
depends_on:Union[str,Sequence[str],None]=None

def upgrade()->None:
 op.execute("""
 INSERT INTO source_registry(source_code,source_name,source_type,base_url,default_source_grade,collection_method,collection_interval,terms_review_status,owner_name,active,note,collection_policy,content_storage_policy,robots_url,robots_review_status,request_interval_seconds,allowed_content_scope,compliance_checked_on,legal_approval_required,compliance_note)
 VALUES
 ('DATACENTER_NEWS_MAILY','데이터 센터 및 IT업계 동향','NEWS','https://maily.so/datacenternews','C','RSS','WEEKLY','LIMITED','데이터 센터 및 IT업계 동향',true,'주간 데이터센터·IT 산업 뉴스레터','METADATA_ONLY','METADATA_ONLY','https://maily.so/robots.txt','ALLOWED',30,'공개 RSS의 제목·원문 URL·게시일·발행기관만 저장. 본문과 구독자 정보는 저장하지 않음',CURRENT_DATE,true,'공개 RSS만 사용하고 구독·사용자·백엔드 경로는 요청하지 않음'),
 ('DATACENTER_KOREA','데이터센터코리아','INDUSTRY','https://datacenterkorea.kr/','B','RSS','DAILY','LIMITED','데이터센터코리아',true,'국내 데이터센터 산업·행사·기업 동향','METADATA_ONLY','METADATA_ONLY','https://datacenterkorea.kr/robots.txt','ALLOWED',30,'공개 RSS의 제목·정규 URL·게시일·발행기관만 저장. 본문·이미지는 저장하지 않음',CURRENT_DATE,true,'robots.txt 전면 허용 확인. 외부 공개는 제목과 원문 링크로 제한')
 ON CONFLICT(source_code) DO NOTHING
 """)
 op.execute("""
 INSERT INTO source_feed(source_id,feed_code,feed_name,feed_url,feed_format,filter_mode,filter_keywords,storage_policy,request_interval_seconds,active,note)
 SELECT source_id,'DATACENTER_NEWS_WEEKLY','데이터 센터 및 IT업계 동향 RSS','https://maily.so/datacenternews/feed','RSS','ALL','[]'::jsonb,'METADATA_ONLY',30,true,'메일리 공개 RSS; 본문·구독정보 저장 안 함'
 FROM source_registry WHERE source_code='DATACENTER_NEWS_MAILY'
 ON CONFLICT(feed_url) DO NOTHING
 """)
 op.execute("""
 INSERT INTO source_feed(source_id,feed_code,feed_name,feed_url,feed_format,filter_mode,filter_keywords,storage_policy,request_interval_seconds,active,note)
 SELECT source_id,'DATACENTER_KOREA_ALL','데이터센터코리아 RSS','https://datacenterkorea.kr/feed/','RSS','ALL','[]'::jsonb,'METADATA_ONLY',30,true,'공개 WordPress RSS; 본문·이미지 저장 안 함'
 FROM source_registry WHERE source_code='DATACENTER_KOREA'
 ON CONFLICT(feed_url) DO NOTHING
 """)

def downgrade()->None:
 op.execute("DELETE FROM source_feed WHERE feed_code IN ('DATACENTER_NEWS_WEEKLY','DATACENTER_KOREA_ALL')")
 op.execute("DELETE FROM source_registry WHERE source_code IN ('DATACENTER_NEWS_MAILY','DATACENTER_KOREA')")
