"""Expand the commercial data-center source catalog.

Revision ID: 0025_commercial_source_catalog
Revises: 0024_commercial_scope
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0025_commercial_source_catalog"
down_revision: Union[str, None] = "0024_commercial_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Official public systems. API collectors are implemented separately; these
    # records make the approved evidence sources and their storage policy explicit.
    op.execute("""
        INSERT INTO source_registry (
            source_code, source_name, source_type, base_url,
            default_source_grade, collection_method, collection_interval,
            terms_review_status, owner_name, active, note,
            collection_policy, content_storage_policy, terms_url,
            api_documentation_url, robots_url, robots_review_status,
            request_interval_seconds, daily_request_limit,
            allowed_content_scope, compliance_checked_on,
            legal_approval_required, compliance_note
        ) VALUES
        ('BUILDING_HUB_PERMIT','건축HUB 건축인허가정보','GOVERNMENT',
         'https://www.data.go.kr/data/15136267/openapi.do','A','API','MONTHLY',
         'ALLOWED','DATA_ENGINEERING',true,'허가·착공·사용승인, 대지위치, 연면적과 용도 확인',
         'OFFICIAL_API','API_RESPONSE','https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do',
         'https://www.data.go.kr/data/15136267/openapi.do',NULL,'NOT_APPLICABLE',5,10000,
         '활용신청한 공식 API 응답과 응답 식별자만 저장',CURRENT_DATE,false,
         '공공데이터포털 인증키는 환경변수로만 관리하고 공개 산출물에 포함하지 않음'),
        ('BUILDING_HUB_LEDGER','건축HUB 건축물대장정보','GOVERNMENT',
         'https://www.data.go.kr/data/15134735/openapi.do','A','API','MONTHLY',
         'ALLOWED','DATA_ENGINEERING',true,'사용승인일·건물명·구조·층수·연면적·주용도 확인',
         'OFFICIAL_API','API_RESPONSE','https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do',
         'https://www.data.go.kr/data/15134735/openapi.do',NULL,'NOT_APPLICABLE',5,10000,
         '활용신청한 공식 API 응답과 응답 식별자만 저장',CURRENT_DATE,false,
         '공공데이터포털 인증키는 환경변수로만 관리하고 공개 산출물에 포함하지 않음'),
        ('EIASS','환경영향평가정보지원시스템','GOVERNMENT',
         'https://www.eiass.go.kr/','A','MANUAL','WEEKLY','ALLOWED','MARKET_RESEARCH',true,
         '사업명·사업자·위치·규모·접수일·완료일·진행상황과 공개 평가서 확인',
         'MANUAL_ONLY','URL_ONLY',NULL,'https://www.eiass.go.kr/',
         'https://www.eiass.go.kr/robots.txt','NOT_REVIEWED',30,NULL,
         '공개 사업조회 결과의 사실값·문서 URL·확인일만 기록',CURRENT_DATE,true,
         '오픈API 이용조건 확인 전에는 화면 기반 수동 검토만 허용'),
        ('MOLIT_REITS_API','국토교통부 리츠정보 API','GOVERNMENT',
         'https://www.data.go.kr/data/15139797/openapi.do','A','API','WEEKLY',
         'ALLOWED','DATA_ENGINEERING',true,'데이터센터 리츠·AMC·투자대상·공시자료 확인',
         'OFFICIAL_API','API_RESPONSE','https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do',
         'https://www.data.go.kr/data/15139797/openapi.do',NULL,'NOT_APPLICABLE',5,NULL,
         '공식 API의 리츠 기본현황·공시 URL·수탁정보',CURRENT_DATE,false,
         '활용신청 후 서비스 키는 환경변수로 관리'),
        ('MOLIT_LAND_TRANSACTION','국토교통부 토지 매매 실거래가 API','GOVERNMENT',
         'https://www.data.go.kr/data/15126466/openapi.do','A','API','MONTHLY',
         'ALLOWED','DATA_ENGINEERING',true,'후보 부지 거래시점·면적·가격 교차검증',
         'OFFICIAL_API','API_RESPONSE','https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do',
         'https://www.data.go.kr/data/15126466/openapi.do',NULL,'NOT_APPLICABLE',5,NULL,
         '공개 토지거래 API 응답. 비공개 개인정보를 수집하지 않음',CURRENT_DATE,false,
         '지번 일부 비공개 한계를 기록하고 다른 출처와 결합해 개인을 식별하지 않음'),
        ('G2B_DC','나라장터 데이터센터 사업·공사 공고','GOVERNMENT',
         'https://www.g2b.go.kr/','A','MANUAL','DAILY','LIMITED','MARKET_RESEARCH',true,
         '공공·민간 연계 데이터센터의 설계·시공·장비·운영 발주와 낙찰자 확인',
         'MANUAL_ONLY','URL_ONLY',NULL,NULL,'https://www.g2b.go.kr/robots.txt','NOT_REVIEWED',30,NULL,
         '공개 공고명·발주기관·일정·낙찰자·원문 URL만 기록',CURRENT_DATE,true,
         '세부 API·재사용 조건 검토 전에는 수동 검색만 허용'),
        ('KRX_KIND','한국거래소 KIND 공시','REGULATOR','https://kind.krx.co.kr/','A','MANUAL','DAILY',
         'ALLOWED','MARKET_RESEARCH',true,'상장사 투자·수주·자산취득·매각·IR 자료 확인',
         'MANUAL_ONLY','URL_ONLY',NULL,NULL,'https://kind.krx.co.kr/robots.txt','NOT_REVIEWED',30,NULL,
         '공시 제목·제출인·제출일·원문 URL과 확인한 사실값만 기록',CURRENT_DATE,true,
         'OpenDART와 중복되는 공시는 접수번호로 중복 제거'),
        ('SEC_EDGAR','미국 SEC EDGAR','REGULATOR','https://www.sec.gov/edgar/','A','API','DAILY',
         'ALLOWED','DATA_ENGINEERING',true,'미국 상장 글로벌 DC 운영사 10-K·10-Q·8-K·실적자료',
         'OFFICIAL_API','API_RESPONSE','https://www.sec.gov/privacy.htm',
         'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',NULL,
         'NOT_APPLICABLE',1,NULL,'공개 제출이력·XBRL·원문 URL과 한국 사업 관련 사실값',CURRENT_DATE,false,
         'SEC 자동접근 정책에 맞는 식별 User-Agent와 호출 간격 적용')
        ON CONFLICT (source_code) DO NOTHING
    """)

    # Official operator, developer and investor pages. Keep collection manual
    # until each site's robots and terms have been reviewed for automation.
    op.execute("""
        INSERT INTO source_registry (
            source_code, source_name, source_type, base_url,
            default_source_grade, collection_method, collection_interval,
            terms_review_status, owner_name, active, note,
            collection_policy, content_storage_policy, robots_url,
            robots_review_status, request_interval_seconds,
            allowed_content_scope, compliance_checked_on,
            legal_approval_required, compliance_note
        ) VALUES
        ('DIGITAL_EDGE','Digital Edge 한국 데이터센터','COMPANY','https://www.digitaledgedc.com/',
         'B','MANUAL','WEEKLY','LIMITED','MARKET_RESEARCH',true,'SEL1·SEL2·SEL3·SEL5·PUS1 시설·용량·RFS·상용 서비스',
         'MANUAL_ONLY','URL_ONLY','https://www.digitaledgedc.com/robots.txt','NOT_REVIEWED',30,
         '공식 시설 페이지·팩트시트의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('STT_GDC_KR','STT GDC Korea','COMPANY','https://www.sttgdc.com/kr-en/locations/seoul',
         'B','MANUAL','WEEKLY','LIMITED','MARKET_RESEARCH',true,'STT Seoul 1 용량·시설·인증·운영 상태',
         'MANUAL_ONLY','URL_ONLY','https://www.sttgdc.com/robots.txt','NOT_REVIEWED',30,
         '공식 시설 페이지·팩트시트·뉴스의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('EMPYRION_DIGITAL','Empyrion Digital Korea','COMPANY','https://empyriondigital.com/south-korea/',
         'B','MANUAL','WEEKLY','LIMITED','MARKET_RESEARCH',true,'KR1 Gangnam 운영·IT Load·시설 사양',
         'MANUAL_ONLY','URL_ONLY','https://empyriondigital.com/robots.txt','NOT_REVIEWED',30,
         '공식 시설 페이지·팩트시트·뉴스의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('PDG_KR','Princeton Digital Group Korea','COMPANY','https://princetondg.com/where-we-operate/',
         'B','MANUAL','WEEKLY','LIMITED','MARKET_RESEARCH',true,'SE1 인천 캠퍼스 용량·RFS·전력계약·개발 상태',
         'MANUAL_ONLY','URL_ONLY','https://princetondg.com/robots.txt','NOT_REVIEWED',30,
         '공식 포트폴리오·보도자료의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('ESR_DC_KR','ESR 한국 데이터센터','COMPANY','https://www.esr.com/our-properties/data-centres/',
         'B','MANUAL','WEEKLY','LIMITED','MARKET_RESEARCH',true,'Bupyeong KR1 개발·투자자·임차인·Facility Load·일정',
         'MANUAL_ONLY','URL_ONLY','https://www.esr.com/robots.txt','NOT_REVIEWED',30,
         '공식 자산 페이지·보도자료·보고서의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('ACTIS_EPOCH','Actis·Epoch Digital','COMPANY','https://www.act.is/2024/06/20/actis-launches-new-asian-data-centre-platform-epoch-digital/',
         'B','MANUAL','MONTHLY','LIMITED','MARKET_RESEARCH',true,'수도권 하이퍼스케일 개발·투자·임차 프로젝트',
         'MANUAL_ONLY','URL_ONLY','https://www.act.is/robots.txt','NOT_REVIEWED',30,
         '공식 보도자료·보고서의 사실값과 URL만 기록',CURRENT_DATE,true,'프로젝트명이 비공개면 후보로만 유지'),
        ('DREAMMARK1','드림마크원','COMPANY','https://dream-mark1.co.kr/ko/dataCenter/incheon',
         'B','MANUAL','MONTHLY','LIMITED','MARKET_RESEARCH',true,'구로·인천·죽전 상용 IDC와 임차·운영 모델',
         'MANUAL_ONLY','URL_ONLY','https://dream-mark1.co.kr/robots.txt','NOT_REVIEWED',30,
         '공식 시설 페이지·회사소개서의 사실값과 URL만 기록',CURRENT_DATE,true,'자동수집 승인 전 수동 확인'),
        ('HOSTWAY_IDC','호스트웨이 IDC','COMPANY','https://www.hostway.co.kr/',
         'B','MANUAL','MONTHLY','LIMITED','MARKET_RESEARCH',true,'분당 자가센터와 도곡·가산·상암 임차형 코로케이션',
         'MANUAL_ONLY','URL_ONLY','https://www.hostway.co.kr/robots.txt','NOT_REVIEWED',30,
         '공식 시설·코로케이션 페이지의 사실값과 URL만 기록',CURRENT_DATE,true,'자가·임차 센터 관계를 분리 기록'),
        ('GABIA_IDC','가비아 IDC','COMPANY','https://idc.gabiacloud.com/server/idc',
         'B','MANUAL','MONTHLY','LIMITED','MARKET_RESEARCH',true,'과천 및 임차 운영 센터의 코로케이션·GPU 대응 정보',
         'MANUAL_ONLY','URL_ONLY','https://idc.gabiacloud.com/robots.txt','NOT_REVIEWED',30,
         '공식 시설 페이지·소개서의 사실값과 URL만 기록',CURRENT_DATE,true,'자가·임차 센터 관계를 분리 기록')
        ON CONFLICT (source_code) DO NOTHING
    """)

    # Market, certification and candidate discovery sources. They can discover
    # candidates or validate a dimension, but never confirm a site by themselves.
    op.execute("""
        INSERT INTO source_registry (
            source_code, source_name, source_type, base_url,
            default_source_grade, collection_method, collection_interval,
            terms_review_status, owner_name, active, note,
            collection_policy, content_storage_policy, robots_url,
            robots_review_status, request_interval_seconds,
            allowed_content_scope, compliance_checked_on,
            legal_approval_required, compliance_note
        ) VALUES
        ('CUSHMAN_DC_KR','Cushman & Wakefield 서울 데이터센터 MarketBeat','INDUSTRY',
         'https://www.cushmanwakefield.com/en/south-korea/insights/seoul-data-center-marketbeat-report',
         'B','MANUAL','SEMIANNUAL','LIMITED','MARKET_RESEARCH',true,'상용·통신사 센터 운영/건설/계획 MW와 프로젝트 표',
         'MANUAL_ONLY','URL_ONLY','https://www.cushmanwakefield.com/robots.txt','NOT_REVIEWED',30,
         '공개 보고서의 자체 요약·지표·원문 URL만 기록',CURRENT_DATE,true,'개별 센터는 공식 출처로 재확인'),
        ('CBRE_DC_KR','CBRE Korea 데이터센터 리서치','INDUSTRY','https://www.cbrekorea.com/insights',
         'B','MANUAL','QUARTERLY','LIMITED','MARKET_RESEARCH',true,'전력승인·투자·임대료·공급 전망',
         'MANUAL_ONLY','URL_ONLY','https://www.cbrekorea.com/robots.txt','NOT_REVIEWED',30,
         '공개 보고서의 자체 요약·지표·원문 URL만 기록',CURRENT_DATE,true,'개별 센터는 공식 출처로 재확인'),
        ('JLL_DC_KR','JLL Korea 데이터센터 리서치','INDUSTRY','https://www.jll.co.kr/ko/trends-and-insights',
         'B','MANUAL','QUARTERLY','LIMITED','MARKET_RESEARCH',true,'운영사·임차·투자·개발시장 동향',
         'MANUAL_ONLY','URL_ONLY','https://www.jll.co.kr/robots.txt','NOT_REVIEWED',30,
         '공개 보고서의 자체 요약·지표·원문 URL만 기록',CURRENT_DATE,true,'개별 센터는 공식 출처로 재확인'),
        ('NVIDIA_DGX_COLO','NVIDIA DGX-Ready Colocation Partners','INDUSTRY',
         'https://www.nvidia.com/ko-kr/data-center/colocation-partners/','B','MANUAL','MONTHLY','LIMITED',
         'MARKET_RESEARCH',true,'GPU·액체냉각 대응 코로케이션 사업자 검증',
         'MANUAL_ONLY','URL_ONLY','https://www.nvidia.com/robots.txt','NOT_REVIEWED',30,
         '파트너명·대상 지역·공식 URL과 확인일만 기록',CURRENT_DATE,true,'시설 단위 지원 여부는 사업자 자료로 재확인'),
        ('CLOUDSCENE_KR','Cloudscene South Korea 디렉터리','INDUSTRY',
         'https://cloudscene.com/region/datacenters-in-asia-pacific','C','MANUAL','MONTHLY','LIMITED',
         'MARKET_RESEARCH',true,'상용 시설·운영사·통신사 후보 발굴',
         'MANUAL_ONLY','URL_ONLY','https://cloudscene.com/robots.txt','NOT_REVIEWED',60,
         '시설명·운영사·도시·원문 URL만 후보로 기록',CURRENT_DATE,true,'공식 출처 확인 전 공개·확정 금지'),
        ('COLOMAP_KR','ColoMap South Korea 디렉터리','INDUSTRY',
         'https://colomap.com/datacenters/country/kr/','C','MANUAL','MONTHLY','LIMITED',
         'MARKET_RESEARCH',true,'코로케이션 시설·주소 후보 발굴',
         'MANUAL_ONLY','URL_ONLY','https://colomap.com/robots.txt','NOT_REVIEWED',60,
         '시설명·운영사·도시·원문 URL만 후보로 기록',CURRENT_DATE,true,'공식 출처 확인 전 공개·확정 금지'),
        ('DC_ATLAS_KR','DC Atlas South Korea 시설·파이프라인','INDUSTRY',
         'https://dcatlas.io/en/explore/facilities/country/south-korea','C','MANUAL','MONTHLY','LIMITED',
         'MARKET_RESEARCH',true,'운영·건설·계획 시설과 MW 후보 발굴',
         'MANUAL_ONLY','URL_ONLY','https://dcatlas.io/robots.txt','NOT_REVIEWED',60,
         '집계·시설명·운영사·원문 URL만 후보로 기록',CURRENT_DATE,true,'라이선스 확인 전 데이터 복제·재배포 금지'),
        ('PEERINGDB','PeeringDB 시설 디렉터리','INDUSTRY','https://www.peeringdb.com/','C','API',NULL,
         'PROHIBITED','DATA_GOVERNANCE',false,'상용 활용 제한 때문에 자동수집 및 DB 복제 금지',
         'BLOCKED','NO_STORAGE','https://www.peeringdb.com/robots.txt','NOT_APPLICABLE',60,
         '자동수집·저장·재배포 금지',CURRENT_DATE,true,
         'Acceptable Use Policy가 상업적 활용을 제한하므로 서면 허가 전까지 사용 금지')
        ON CONFLICT (source_code) DO NOTHING
    """)

    # Existing official pages are useful as manual evidence even when no
    # unattended crawler is approved for them.
    op.execute("""
        UPDATE source_registry
        SET active = true,
            collection_method = 'MANUAL',
            collection_policy = 'MANUAL_ONLY',
            content_storage_policy = 'URL_ONLY',
            allowed_content_scope = '공개 화면에서 확인한 사실값·원문 URL·확인일만 기록',
            legal_approval_required = true,
            compliance_note = '자동수집 승인 전 수동 확인 소스로 사용',
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code IN (
            'DATA_GO_KR_BUILDING','EAIS','EUM','KPX_EPSIS',
            'LGU_IDC','KINX','EQUINIX_NEWS','DIGITAL_REALTY_NEWS',
            'KDCC','UPTIME_INSTITUTE'
        )
    """)

    # Commercial-market search feeds complement the broad discovery feeds.
    op.execute("""
        INSERT INTO source_feed (
            source_id, feed_code, feed_name, feed_url, feed_format,
            filter_mode, filter_keywords, storage_policy,
            request_interval_seconds, active, note
        )
        SELECT source_id, feed_code, feed_name, feed_url, 'RSS', 'ALL',
               '[]'::jsonb, 'METADATA_ONLY', 15, true,
               '상용 데이터센터 후보 탐색용 제목·URL·게시일·발행기관 메타데이터'
        FROM source_registry
        CROSS JOIN (VALUES
            ('GNEWS_DC_COMMERCIAL','코로케이션·임대·마스터리스',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%BD%94%EB%A1%9C%EC%BC%80%EC%9D%B4%EC%85%98+OR+%EC%83%81%EB%A9%B4+OR+%EC%9E%84%EB%8C%80+OR+%EC%9E%84%EC%B0%A8+OR+%EB%A7%88%EC%8A%A4%ED%84%B0%EB%A6%AC%EC%8A%A4%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_DEVELOPMENT','인허가·착공·준공·부지',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EA%B1%B4%EC%B6%95%ED%97%88%EA%B0%80+OR+%EC%B0%A9%EA%B3%B5+OR+%EC%A4%80%EA%B3%B5+OR+RFS+OR+%EB%B6%80%EC%A7%80+OR+%ED%86%A0%EC%A7%80%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_LEASE_DEAL','임차·선임대·매각·투자',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%84%A0%EC%9E%84%EB%8C%80+OR+%EC%9E%84%EC%B0%A8%EC%9D%B8+OR+%EB%A7%A4%EA%B0%81+OR+%EC%9D%B8%EC%88%98+OR+%ED%8E%80%EB%93%9C+OR+%EB%A6%AC%EC%B8%A0+OR+PF%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_OPERATOR','상용 DC 운영사',
             'https://news.google.com/rss/search?q=%28%22Digital+Edge%22+OR+Equinix+OR+%22Digital+Realty%22+OR+%22STT+GDC%22+OR+Empyrion+OR+KINX+OR+%22kt+cloud%22+OR+%22LG%EC%9C%A0%ED%94%8C%EB%9F%AC%EC%8A%A4%22+OR+%22SK%EB%B8%8C%EB%A1%9C%EB%93%9C%EB%B0%B4%EB%93%9C%22%29+%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_SUPPLY_CHAIN','개발사·AMC·시공사·DBO',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EA%B0%9C%EB%B0%9C%EC%82%AC+OR+%EC%9E%90%EC%82%B0%EC%9A%B4%EC%9A%A9%EC%82%AC+OR+AMC+OR+%EC%8B%9C%EA%B3%B5%EC%82%AC+OR+DBO%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako')
        ) AS feeds(feed_code, feed_name, feed_url)
        WHERE source_code='GOOGLE_NEWS_DC'
        ON CONFLICT (feed_url) DO UPDATE SET
            active=true, note=EXCLUDED.note, updated_at=CURRENT_TIMESTAMP
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM source_feed WHERE feed_code IN (
            'GNEWS_DC_COMMERCIAL','GNEWS_DC_DEVELOPMENT','GNEWS_DC_LEASE_DEAL',
            'GNEWS_DC_OPERATOR','GNEWS_DC_SUPPLY_CHAIN'
        )
    """)
    op.execute("""
        DELETE FROM source_registry WHERE source_code IN (
            'BUILDING_HUB_PERMIT','BUILDING_HUB_LEDGER','EIASS','MOLIT_REITS_API',
            'MOLIT_LAND_TRANSACTION','G2B_DC','KRX_KIND','SEC_EDGAR',
            'DIGITAL_EDGE','STT_GDC_KR','EMPYRION_DIGITAL','PDG_KR','ESR_DC_KR',
            'ACTIS_EPOCH','DREAMMARK1','HOSTWAY_IDC','GABIA_IDC',
            'CUSHMAN_DC_KR','CBRE_DC_KR','JLL_DC_KR','NVIDIA_DGX_COLO',
            'CLOUDSCENE_KR','COLOMAP_KR','DC_ATLAS_KR','PEERINGDB'
        )
    """)
