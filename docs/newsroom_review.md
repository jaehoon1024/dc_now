# 기업 뉴스룸 수집 검토

검토일: 2026-09-28. 공유 대화의 RSS 이후 단계에 따라 공식 페이지와 robots, RSS 제공 여부를 확인했다.

| 출처 | 공식 페이지 | 확인 결과 | 다음 조치 |
|---|---|---|---|
| LG유플러스 | https://news.lguplus.com/ | HTTP 200. RSS 없음. 콘텐츠 이용 안내에 비영리·출처표시·변경금지 및 외부 필진 자료 제한 명시 | 0012에서 LIMITED 최소 메타데이터 HTML 수집 활성화 |
| LG CNS | https://www.lgcns.com/kr/newsroom/press | RSS 없음. 화면 목록 API는 `/bin/cf/fetch`이며 robots가 `/bin/`을 명시적으로 차단 | 0014에서 BLOCKED/DISALLOWED로 기록. 자동수집과 우회 크롤링 금지 |
| KT Cloud | https://tech.ktcloud.com/ | 공식 페이지에서 https://ktcloudplatform.tistory.com/rss 제공 확인. RSS HTTP 200, 15항목 파싱 확인 | 최소 메타데이터만 수집하는 LIMITED 정책으로 0011 마이그레이션에 등록 |
| SK브로드밴드 | https://www.skbroadband.com/kor/pr/press_list.do?menu_id=K05010000 | HTTP 200. RSS 없음. 목록 HTML에 제목·게시일·상세 식별자가 있으며 robots가 목록 경로를 제한하지 않음 | 0013에서 LIMITED 최소 메타데이터 HTML 수집 활성화. 상세 본문은 요청하지 않음 |

RSS 링크 없음은 확인한 페이지의 자동발견 링크 기준이며, 전체 사이트에 RSS가 없다는 뜻은 아니다.
robots의 허용은 콘텐츠 재사용 허가를 의미하지 않는다. KT Cloud는 `LIMITED`로 등록하고 외부 재배포 전 별도 검토가 필요하도록 유지했다. 다른 신규 출처는 `PENDING`에서 승격하지 않았다.

## KT Cloud 적용 범위

- 공식 기술 블로그가 선언한 RSS 주소만 호출한다.
- 제목, 정규 URL, 게시일, 발행기관만 저장한다.
- 본문, RSS 요약문, 이미지, 첨부파일은 저장하지 않는다.
- 데이터센터 키워드가 있는 항목만 저장한다.
- robots 정책의 관리·검색 경로 제한을 준수한다.

## LG유플러스 정책 근거

- [콘텐츠 이용 안내](https://news.lguplus.com/뉴스룸-콘텐츠-이용-안내)
- [뉴스룸 운영정책](https://news.lguplus.com/뉴스룸-운영정책)

자체 제작 콘텐츠의 연구·학습 등 이용 안내와 상업 이용 금지, 변경금지, 제3자 콘텐츠 제한을 함께 적용했다. 공식 첫 화면의 보도자료 제목·URL·게시일만 저장하고 본문·이미지·영상은 저장하지 않는다. 외부 재배포 전에는 별도 검토가 필요하다.

기술 조회 결과: `newsroom_discovery.json`. 기사 본문과 이미지는 보관하지 않았다.

## SK브로드밴드 적용 범위

- 공식 보도자료 목록 첫 페이지만 하루 한 번 호출한다.
- 목록에 표시된 제목, 상세 URL, 게시일, 발행기관만 저장한다.
- 상세 기사 본문, 이미지, 첨부파일은 요청하거나 저장하지 않는다.
- 데이터센터 키워드가 있는 항목만 저장한다.
- 저작권자가 표시된 콘텐츠이므로 외부 재배포 전 별도 검토가 필요하다.

## LG CNS 보류 사유

- 공개 목록에서 상세 URL은 확인되지만 제목과 게시일은 `/bin/cf/fetch` API로 불러온다.
- 공식 robots 정책이 `/bin/` 경로를 차단한다.
- `0014_block_lgcns_automation`에서 출처를 BLOCKED/DISALLOWED로 기록했다.
- 상세 페이지를 반복 호출하는 우회 수집도 하지 않는다.
- 필요한 항목은 담당자가 공식 페이지에서 확인한 뒤 출처 URL만 수동 등록한다.
