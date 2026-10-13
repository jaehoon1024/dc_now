"""Keep phase completion forecasts separate from RFS and collect archive lists."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = '0031_development_completion'
down_revision: Union[str,None] = '0030_capacity_hierarchy'
branch_labels: Union[str,Sequence[str],None] = None
depends_on: Union[str,Sequence[str],None] = None

ARCHIVE = 'https://news.lguplus.com/category/%ED%94%84%EB%A0%88%EC%8A%A4%EC%84%BC%ED%84%B0/%EB%B3%B4%EB%8F%84%EC%9E%90%EB%A3%8C/'

def upgrade():
    op.add_column('project_phase',sa.Column('planned_completion_period',sa.String(20)))
    op.add_column('project_phase',sa.Column('planned_completion_precision',sa.String(20)))
    op.create_check_constraint('ck_phase_completion_precision','project_phase',"planned_completion_precision IS NULL OR planned_completion_precision IN ('DAY','MONTH','QUARTER','YEAR','UNKNOWN')")
    op.execute(sa.text("UPDATE source_page SET page_url=:url,parser_code='LGUPLUS_ARCHIVE_V1',note='공식 보도자료 아카이브 목록: 제목·게시일·URL만 저장. 매일 최근 3페이지 확인; 수동 backfill은 범위·페이지 수 제한' WHERE page_code='LGU_PRESS'").bindparams(url=ARCHIVE))

def downgrade():
    op.execute("UPDATE source_page SET page_url='https://news.lguplus.com/',parser_code='LGUPLUS_PRESS_V1',note='공식 뉴스룸 첫 화면만 수집' WHERE page_code='LGU_PRESS'")
    op.drop_constraint('ck_phase_completion_precision','project_phase',type_='check')
    op.drop_column('project_phase','planned_completion_precision')
    op.drop_column('project_phase','planned_completion_period')
