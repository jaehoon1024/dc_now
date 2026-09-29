"""Seed the initial data-center source registry.

Revision ID: 0008_seed_sources
Revises: 0007_dashboard_views
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_seed_sources"
down_revision: Union[str, None] = "0007_dashboard_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOURCES = (
    (
        "OPENDART",
        "금융감독원 OpenDART",
        "REGULATOR",
        "https://opendart.fss.or.kr/",
        "A",
        "API",
        "DAILY",
        "공시·사업보고서·주요사항보고서와 원문 파일",
    ),
    (
        "DATA_GO_KR_BUILDING",
        "공공데이터포털 건축물·건축인허가",
        "GOVERNMENT",
        "https://www.data.go.kr/",
        "A",
        "API",
        "WEEKLY",
        "건축물대장·건축인허가·착공·사용승인 공개데이터",
    ),
    (
        "EAIS",
        "건축행정시스템 세움터",
        "GOVERNMENT",
        "https://www.eais.go.kr/",
        "A",
        "MANUAL",
        "WEEKLY",
        "건축 인허가·착공·준공·사용승인 확인",
    ),
    (
        "LOCALDATA",
        "지방행정인허가데이터개방",
        "GOVERNMENT",
        "https://www.localdata.go.kr/",
        "A",
        "API",
        "DAILY",
        "지자체 인허가와 영업 상태 데이터",
    ),
    (
        "LAW_GO_KR",
        "국가법령정보센터",
        "GOVERNMENT",
        "https://www.law.go.kr/",
        "A",
        "HTML",
        "WEEKLY",
        "데이터센터·전력·건축·산업입지 관련 법령 변경",
    ),
    (
        "MOTIE_PRESS",
        "산업통상자원부 보도자료",
        "GOVERNMENT",
        "https://www.motie.go.kr/",
        "A",
        "HTML",
        "DAILY",
        "전력정책·전력망·에너지 정책 발표",
    ),
    (
        "MOLIT_PRESS",
        "국토교통부 보도자료",
        "GOVERNMENT",
        "https://www.molit.go.kr/",
        "A",
        "HTML",
        "DAILY",
        "건축·국토계획·산업입지 관련 발표",
    ),
    (
        "MSIT_PRESS",
        "과학기술정보통신부 보도자료",
        "GOVERNMENT",
        "https://www.msit.go.kr/",
        "A",
        "HTML",
        "DAILY",
        "클라우드·AI 인프라·데이터센터 정책 발표",
    ),
    (
        "KEPCO_OPEN_DATA",
        "한국전력 전력데이터 개방포털",
        "REGULATOR",
        "https://bigdata.kepco.co.kr/",
        "A",
        "API",
        "WEEKLY",
        "지역·계약종별 전력 데이터와 개방 데이터셋",
    ),
    (
        "KPX_EPSIS",
        "전력거래소 전력통계정보시스템 EPSIS",
        "REGULATOR",
        "https://epsis.kpx.or.kr/",
        "A",
        "HTML",
        "DAILY",
        "전력수급·설비·송배전·판매 통계",
    ),
    (
        "EUM",
        "토지이음",
        "GOVERNMENT",
        "https://www.eum.go.kr/",
        "A",
        "MANUAL",
        "WEEKLY",
        "토지이용계획·용도지역·지구 확인",
    ),
    (
        "LGU_IDC",
        "LG유플러스 IDC 센터 안내",
        "COMPANY",
        "https://www.lguplus.com/biz/all/telecom/idc/center/B000000031",
        "B",
        "HTML",
        "WEEKLY",
        "센터명·주소·수전용량·시설 정보",
    ),
    (
        "LGU_NEWS",
        "LG유플러스 뉴스룸",
        "COMPANY",
        "https://news.lguplus.com/latest/",
        "B",
        "HTML",
        "DAILY",
        "AIDC 개발계획·전력·준공 목표·기술 발표",
    ),
    (
        "LGCNS_NEWS",
        "LG CNS 뉴스룸",
        "COMPANY",
        "https://connect.lgcns.com/kr/newsroom/press",
        "B",
        "HTML",
        "DAILY",
        "데이터센터 개발·DBO·운영·AI 인프라 발표",
    ),
    (
        "SKB_IDC",
        "SK브로드밴드 IDC 센터 안내",
        "COMPANY",
        "https://biz.skbroadband.com/page.do?menu_id=P06010100",
        "B",
        "HTML",
        "WEEKLY",
        "센터명·주소·규모·서비스·설비 정보",
    ),
    (
        "KT_CLOUD_PRESS",
        "kt cloud 공식 보도자료",
        "COMPANY",
        "https://tech.ktcloud.com/category/News/Press%20Release",
        "B",
        "HTML",
        "DAILY",
        "IDC·AI 데이터센터·클라우드 인프라 발표",
    ),
    (
        "NAVER_CLOUD",
        "NAVER Cloud 회사·데이터센터 정보",
        "COMPANY",
        "https://www.navercloudcorp.com/ko/info/",
        "B",
        "HTML",
        "WEEKLY",
        "데이터센터 각·클라우드 인프라 공식 정보",
    ),
    (
        "NHN_INSIDE",
        "NHN 공식 뉴스",
        "COMPANY",
        "https://inside.nhn.com/news",
        "B",
        "HTML",
        "DAILY",
        "NHN Cloud·AI 데이터센터·지역센터 발표",
    ),
    (
        "KINX",
        "KINX 공식 사이트",
        "COMPANY",
        "https://www.kinx.net/",
        "B",
        "HTML",
        "WEEKLY",
        "IDC·IX·네트워크 서비스와 센터 정보",
    ),
    (
        "EQUINIX_NEWS",
        "Equinix Korea 뉴스룸",
        "COMPANY",
        "https://www.equinix.com/kr/ko/newsroom",
        "B",
        "HTML",
        "WEEKLY",
        "국내 센터 개장·확장·투자 발표",
    ),
    (
        "DIGITAL_REALTY_NEWS",
        "Digital Realty 뉴스룸",
        "COMPANY",
        "https://www.digitalrealty.com/resources/news",
        "B",
        "HTML",
        "WEEKLY",
        "데이터센터 개장·확장·서비스 발표",
    ),
    (
        "KDCC",
        "한국데이터센터연합회",
        "INDUSTRY",
        "https://kdcc.or.kr/kdcc/",
        "B",
        "HTML",
        "WEEKLY",
        "국내 데이터센터 산업정책·시장자료·행사·회원사 동향",
    ),
    (
        "UPTIME_INSTITUTE",
        "Uptime Institute",
        "INDUSTRY",
        "https://uptimeinstitute.com/resources",
        "B",
        "HTML",
        "WEEKLY",
        "Tier·가용성·운영·효율 관련 산업자료",
    ),
    (
        "DCD",
        "Data Center Dynamics",
        "NEWS",
        "https://www.datacenterdynamics.com/",
        "C",
        "HTML",
        "DAILY",
        "글로벌·한국 데이터센터 투자와 개발 보도",
    ),
    (
        "ETNEWS",
        "전자신문",
        "NEWS",
        "https://www.etnews.com/",
        "C",
        "HTML",
        "DAILY",
        "국내 AI·클라우드·데이터센터 산업 보도",
    ),
    (
        "YONHAP",
        "연합뉴스",
        "NEWS",
        "https://www.yna.co.kr/",
        "C",
        "HTML",
        "DAILY",
        "기업·정부의 데이터센터·전력·투자 관련 보도",
    ),
)


def upgrade() -> None:
    source_table = sa.table(
        "source_registry",
        sa.column("source_code", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("base_url", sa.Text()),
        sa.column("default_source_grade", sa.CHAR()),
        sa.column("collection_method", sa.String()),
        sa.column("collection_interval", sa.String()),
        sa.column("terms_review_status", sa.String()),
        sa.column("owner_name", sa.String()),
        sa.column("active", sa.Boolean()),
        sa.column("note", sa.Text()),
    )

    op.bulk_insert(
        source_table,
        [
            {
                "source_code": source_code,
                "source_name": source_name,
                "source_type": source_type,
                "base_url": base_url,
                "default_source_grade": source_grade,
                "collection_method": collection_method,
                "collection_interval": collection_interval,
                "terms_review_status": "PENDING",
                "owner_name": "DATA_ENGINEERING",
                "active": False,
                "note": note,
            }
            for (
                source_code,
                source_name,
                source_type,
                base_url,
                source_grade,
                collection_method,
                collection_interval,
                note,
            ) in SOURCES
        ],
    )


def downgrade() -> None:
    source_codes = ", ".join(
        "'" + source_code.replace("'", "''") + "'"
        for source_code, *_ in SOURCES
    )
    op.execute(
        f"DELETE FROM source_registry WHERE source_code IN ({source_codes})"
    )
