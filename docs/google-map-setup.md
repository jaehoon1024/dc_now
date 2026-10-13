# Google 전국 센터 지도 연결

현재 공개 설정은 비어 있다. 주소 조회 iframe은 별도 프로젝트 설정 없이 동작한다. 전국 센터를 동시에 표시하는 코드는 연결 준비가 되어 있지만 실제 Google Maps 인증은 아직 확인하지 않았다.

## 설정

1. 사용자의 Google Cloud 프로젝트에서 결제 계정과 Maps JavaScript API를 활성화한다.
2. 웹사이트용 키를 만들고 HTTP 리퍼러 제한을 `https://jaehoon1024.github.io/*`로 설정한다. 로컬에서 확인할 경우 필요한 localhost 주소만 추가한다.
3. API 제한은 Maps JavaScript API로 지정한다. 운영용 지도 ID도 만들 수 있다.
4. `dashboard/map-config.json`의 `browser_key`와 `map_id`에 해당 설정을 입력한다. 이 파일은 공개 브라우저 설정이므로 서버용 키, OpenDART 키, 토큰, 비밀번호를 입력하지 않는다. 값은 채팅이나 점검 로그에 출력하지 않는다.
5. 공개 API가 실행 중인 상태에서 `.venv/bin/python src21_build_static_site.py`로 빌드한다. `deploy/map-config.json`과 화면 자산을 함께 게시한다.

브라우저 키는 공개 페이지가 Google에 요청할 때 전달되므로 사용 범위를 리퍼러와 API 제한으로 관리해야 한다. [Google 공식 API 로딩 안내](https://developers.google.com/maps/documentation/javascript/load-maps-js-api)와 [보안 안내](https://developers.google.com/maps/api-security-best-practices)를 따른다.

## 화면 동작

- 초기 전국 보기: 현재 필터에 맞는 센터 좌표를 표시하고 가까운 위치를 묶는다.
- 기본 좌표 범위: 한국 지도 범위에 들어오는 A/B 검증 좌표. 위치를 모르는 센터는 원장에서 계속 표시한다.
- 근사 좌표 포함: C 등급 등 근사 좌표를 점선 테두리로 구분한다.
- 운영·개발·병행·미확인 상태에 다른 색을 사용한다. 표시 크기는 IT Load, 수전용량 또는 센터 수로 선택한다.
- 센터 클릭: 상세 패널을 연다. 묶음 클릭: 확대하거나 같은 위치의 센터 목록을 연다.
- 주소만 있는 센터 선택: Google 주소 조회로 전환한다. 검색 결과를 DB 검증 좌표로 자동 저장하지 않는다.
- 설정 없음, 로드 실패, 인증 실패: 주소 조회 지도와 원장을 유지한다.

## 검증 범위

실제 주소 조회는 PC·모바일 브라우저에서 확인했다. 전국 마커의 좌표 필터, 묶음 계산, 상태 표시와 상세 선택은 모의 Google API로 검증했다. 실제 전국 지도 인증·결제·리퍼러 설정은 사용자 프로젝트 연결 후 확인해야 한다.
