"""Preserve phase RFS precision and register KT corporate metadata discovery."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = '0032_operator_review'
down_revision: Union[str,None] = '0031_development_completion'
branch_labels: Union[str,Sequence[str],None] = None
depends_on: Union[str,Sequence[str],None] = None

def upgrade():
    op.add_column('project_phase',sa.Column('planned_rfs_period',sa.String(20)))
    op.add_column('project_phase',sa.Column('planned_rfs_precision',sa.String(20)))
    op.create_check_constraint('ck_phase_rfs_precision','project_phase',"planned_rfs_precision IS NULL OR planned_rfs_precision IN ('DAY','MONTH','QUARTER','YEAR','UNKNOWN')")
    op.execute("""INSERT INTO source_registry(source_code,source_name,source_type,base_url,default_source_grade,
        collection_method,collection_interval,terms_review_status,owner_name,collection_policy,content_storage_policy,
        allowed_content_scope,robots_review_status,request_interval_seconds,daily_request_limit,compliance_checked_on,compliance_note)
        VALUES('KT_CORP_NEWS','kt cloud 기업 공식 보도자료','COMPANY','https://www.ktcloud.com/media/press?source=dc',
        'B','API','DAILY','LIMITED','MARKET_RESEARCH','METADATA_ONLY','METADATA_ONLY','공식 DC 분류 목록 제목·게시일·URL만 보관',
        'NOT_APPLICABLE',30,6,'2026-10-13','공개 웹사이트가 이용하는 인증 없는 목록 JSON. robots 경로는404. 본문·이미지·작성자 정보는 폐기. 최대3페이지·30초 간격')
        ON CONFLICT(source_code) DO NOTHING""")
    op.execute("""INSERT INTO source_page(source_id,page_code,page_name,page_url,parser_code,filter_keywords,request_interval_seconds,active,note)
        SELECT source_id,'KT_CORP_DC','KT 공식 DC 보도자료 목록',
        'https://data.ktcloud.com/api/board/list/media/press/kor?curPage=1&pageSize=9&source=dc','KT_CORP_JSON_V1',
        '["데이터센터","데이터 센터","IDC","AIDC","DC"]'::jsonb,30,true,'기술 블로그 RSS를 보완하는 기업 공식 발표 목록. 최대3페이지 확인'
        FROM source_registry WHERE source_code='KT_CORP_NEWS' ON CONFLICT(source_id,page_code) DO NOTHING""")

def downgrade():
    op.execute("UPDATE source_page SET active=false WHERE page_code='KT_CORP_DC'")
    op.execute("UPDATE source_registry SET active=false WHERE source_code='KT_CORP_NEWS'")
    op.drop_constraint('ck_phase_rfs_precision','project_phase',type_='check')
    op.drop_column('project_phase','planned_rfs_precision')
    op.drop_column('project_phase','planned_rfs_period')
