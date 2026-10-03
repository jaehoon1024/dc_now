"""Define the commercial data-center market scope.

Revision ID: 0024_commercial_scope
Revises: 0023_news_discovery_feeds
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0024_commercial_scope"
down_revision: Union[str, None] = "0023_news_discovery_feeds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMMERCIAL_SCOPE_CHECK = (
    "commercial_scope_status IN ('IN_SCOPE','OUT_OF_SCOPE','REVIEW_REQUIRED')"
)
COMMERCIAL_MODEL_CHECK = (
    "commercial_model IN ('COLOCATION','WHOLESALE','MASTER_LEASE','LEASED',"
    "'BUILD_TO_SUIT','MANAGED_SERVICE','MULTI_MODEL','UNKNOWN')"
)
COMMERCIAL_REVIEW_CHECK = (
    "commercial_review_status IN ('CONFIRMED','NEEDS_EVIDENCE')"
)


def upgrade() -> None:
    op.add_column(
        "dc_site",
        sa.Column(
            "commercial_scope_status", sa.String(length=30), nullable=False,
            server_default=sa.text("'REVIEW_REQUIRED'"),
        ),
    )
    op.add_column(
        "dc_site",
        sa.Column(
            "commercial_model", sa.String(length=30), nullable=False,
            server_default=sa.text("'UNKNOWN'"),
        ),
    )
    op.add_column(
        "dc_site",
        sa.Column(
            "commercial_review_status", sa.String(length=30), nullable=False,
            server_default=sa.text("'NEEDS_EVIDENCE'"),
        ),
    )
    op.add_column("dc_site", sa.Column("commercial_scope_note", sa.Text(), nullable=True))
    op.add_column(
        "dc_site", sa.Column("commercial_source_url", sa.String(length=2000), nullable=True)
    )
    op.create_check_constraint(
        "ck_dc_site_commercial_scope", "dc_site", COMMERCIAL_SCOPE_CHECK
    )
    op.create_check_constraint(
        "ck_dc_site_commercial_model", "dc_site", COMMERCIAL_MODEL_CHECK
    )
    op.create_check_constraint(
        "ck_dc_site_commercial_review", "dc_site", COMMERCIAL_REVIEW_CHECK
    )
    op.create_index(
        "idx_dc_site_commercial_scope", "dc_site",
        ["commercial_scope_status", "commercial_review_status"],
    )

    # Official colocation service pages already stored as A-grade evidence.
    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='IN_SCOPE',
            commercial_model='COLOCATION',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='사업자 공식 코로케이션·IDC 센터 목록 확인',
            commercial_source_url=CASE
                WHEN site_code LIKE 'LGU_%%' THEN 'https://www.lguplus.com/biz/all/telecom/idc/center/B000000031'
                WHEN site_code LIKE 'SKB_%%' THEN 'https://biz.skbroadband.com/page.do?menu_id=P06010100'
                WHEN site_code='KINX_GWACHEON' THEN 'https://www.kinx.net/'
                WHEN site_code='EQUINIX_SL1' THEN 'https://www.equinix.com/data-centers/asia-pacific-colocation/south-korea-colocation/seoul-data-centers'
                WHEN site_code='DLR_ICN10' THEN 'https://www.digitalrealty.com/data-centers/asia-pacific/seoul/icn10'
            END,
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN (
            'LGU_ANYANG','LGU_BUSAN_AMI','LGU_DAEGU','LGU_DAEJEON',
            'LGU_GASAN','LGU_GWANGJU','LGU_NONHYEON','LGU_PYEONGCHON',
            'LGU_SANGAM','LGU_SEOCHO1','LGU_SEOCHO2',
            'SKB_BUNDANG','SKB_GASAN','SKB_ILSAN','SKB_SEOCHO',
            'KINX_GWACHEON','EQUINIX_SL1','DLR_ICN10'
        )
    """)

    # Obvious captive/public computing facilities and abstract cloud regions are
    # retained for audit, but excluded from the commercial supply universe.
    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='OUT_OF_SCOPE',
            commercial_model='UNKNOWN',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='자가사용·공공 전산/HPC 시설 또는 물리 센터가 특정되지 않은 클라우드 리전',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code LIKE '%%\\_IT' ESCAPE '\\'
           OR site_code IN (
               'BUSAN_CITY_DC','CHUNGBUK_PROVINCE_DC','CHUNGNAM_PROVINCE_DC',
               'GANGWON_PROVINCE_DC','GYEONGBUK_PROVINCE_DC','GYEONGGI_PROVINCE_DC',
               'GYEONGNAM_PROVINCE_DC','JEONBUK_PROVINCE_DC','JEONNAM_PROVINCE_DC',
               'SEOUL_CITY_DC','NIRS_DAEGU','NIRS_DAEJEON','NIRS_GONGJU','NIRS_GWANGJU',
               'DGIST_HPC','GIST_HPC','KAIST_HPC','POSTECH_HPC','SNU_HPC','UNIST_HPC',
               'KAKAO_ANSAN','NAVER_GAK_CHUNCHEON','NAVER_GAK_SEJONG'
           )
           OR site_name LIKE '%% 클라우드 리전 %%'
           OR site_name LIKE '%% 가용영역 %%'
    """)


def downgrade() -> None:
    op.drop_index("idx_dc_site_commercial_scope", table_name="dc_site")
    op.drop_constraint("ck_dc_site_commercial_review", "dc_site", type_="check")
    op.drop_constraint("ck_dc_site_commercial_model", "dc_site", type_="check")
    op.drop_constraint("ck_dc_site_commercial_scope", "dc_site", type_="check")
    op.drop_column("dc_site", "commercial_source_url")
    op.drop_column("dc_site", "commercial_scope_note")
    op.drop_column("dc_site", "commercial_review_status")
    op.drop_column("dc_site", "commercial_model")
    op.drop_column("dc_site", "commercial_scope_status")
