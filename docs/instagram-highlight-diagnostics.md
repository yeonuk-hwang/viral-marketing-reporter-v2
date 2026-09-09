# Instagram 테두리 누락 진단

## 가능한 원인

Instagram 검색 카드의 빨간 테두리가 일부 빠지는 현상은 최종 PNG만으로 원인을
구분하기 어렵다. 계정이나 고객 PC에서만 발생한다면 다음 가능성이 있다.

- 최초 매칭 뒤 스크롤 또는 미디어 로딩 중 카드 DOM이 교체됨
- viewport 변경 전후 상위 10개 링크 순서가 달라짐
- Instagram A/B UI에서 카드 링크의 크기나 stacking context가 달라짐
- 강조 overlay가 생성됐지만 부모 요소의 overflow 또는 다른 레이어에 가려짐
- 최종 캡처 직전에 카드가 다시 렌더링됨
- 앱, Chrome, 로그인 세션 또는 네트워크 응답 차이

## 자동 생성되는 진단 파일

Instagram 결과 PNG가 생성될 때 같은 폴더에 다음 파일도 생성한다.

```text
<번호>_<키워드>_instagram_diagnostic.json
```

이 파일은 다음 다섯 단계를 기록한다.

1. 최초 상위 10개 수집 직후
2. 스크롤 및 미디어 로딩 후
3. 캡처용 viewport 적용 후
4. 빨간 테두리 적용 직후
5. PNG 캡처 직후

각 단계에는 게시물 ID와 순서, 좌표, 표시 여부, 미디어 준비 개수, 강조 overlay의
존재 여부·좌표·가시성·z-index가 들어간다. 브라우저 언어, 플랫폼, DPR과 오류
누적 수도 기록한다.

전체 HTML, 쿠키, 인증 헤더, 요청·응답 본문 및 Instagram 로그인 세션은 기록하지
않는다.

## 고객 자료 수집 절차

1. 문제가 발생한 검색을 완료한다.
2. 메인 화면에서 `Instagram 진단 ZIP 만들기`를 누른다.
3. 생성 완료 창에 표시된 ZIP 파일을 담당자에게 전달한다.

ZIP에는 가장 최근 Instagram 작업의 결과 PNG와 진단 JSON, 현재 `debug.log` 및
간단한 안내 파일만 들어간다. `instagram_session.json`은 포함하지 않는다.

## 분석 기준

- 단계 사이에 대상 게시물 ID가 사라짐: DOM 교체 또는 결과 순서 변경
- 요청 ID가 `after_highlight`에 없음: 재조회 시 상위 10개에서 이탈
- overlay `present=false`: 강조 대상 탐색 또는 적용 실패
- overlay는 존재하지만 크기가 0: 카드 레이아웃/locator 문제
- overlay가 visible이고 좌표도 정상인데 PNG에서 안 보임: stacking context,
  overflow 또는 캡처 직전 재렌더링 가능성
- 미디어 `ready`가 부족함: 네트워크, 디코딩 또는 lazy loading 문제
