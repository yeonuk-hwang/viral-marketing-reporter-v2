# 네이버 통합검색 AI 브리핑·강조 박스 경계 수정 증거

- 확인 일시: 2026-09-23 (Australia/Adelaide)
- 확인 키워드: `무료사료체험`
- 확인 대상: 요청받은 네이버 블로그 URL 39개
- 사용자 제보 이미지: `/home/yeonuk/Downloads/Screenshot_20260923-133416.png`

## 수정 전 확인

실제 네이버 검색을 기존 코드로 실행한 결과입니다.

- AI 브리핑 섹션 1개가 노출됐습니다. 당시 응답에는 대상 URL로 연결되는 출처
  링크가 없어 실검색에서 AI 오탐이 바로 발생하지는 않았습니다.
- 대상 게시물 2개(`djsvh123/224368808876`,
  `lauren0303/224369778788`)가 검색 결과에서 발견됐습니다.
- 검색 결과는 수시로 변하기 때문에, 제보 이미지의
  `dooboo_19/224363875594`와 로얄캐닌 클럽 조합은 확인 시점의 실검색에서는
  다시 노출되지 않았습니다.
- 그러나 기존 판정 코드는 `#main_pack`의 모든 링크를 검사해 AI 브리핑을
  제외하는 조건이 없었습니다. 또한 박스 선택 시 블로그·카페·인플루언서
  게시물 URL만 서로 다른 목적지로 계산해, 공식 사이트와 대상 게시물이 같은
  컨테이너에 있으면 둘을 한 박스로 선택하는 구조였습니다.

자료:

- [수정 전 실검색 전체 캡처](before/1_무료사료체험.png)
- [수정 전 경계 로직 재현 캡처](before/synthetic-boundary-check.png)

재현용 DOM에서 기존 로직의 결과는 다음과 같았습니다.

```text
old_ai_primary = true
old_selected_card = SECTION.sc_new.mixed
containsOfficial = true
```

즉 AI 브리핑의 대상 링크를 일반 노출로 인정했고, 아래 블로그 게시물이
일치했을 때 위의 로얄캐닌 공식 사이트까지 같은 빨간 박스에 포함했습니다.

## 수정 내용

`NaverIntegratedSearchPage`의 두 판정 기준을 변경했습니다.

1. 링크의 조상에 네이버 AI 브리핑 의미 클래스(`fds-aib-*`)가 있거나,
   해당 검색 섹션 제목이 `AI 브리핑`이면 일반 노출에서 제외합니다.
2. 강조 박스는 네이버의 게시물 단위 의미 표식
   (`data-template-id="ugcItem"`)을 최우선으로 선택합니다.
3. 의미 표식이 없는 구형 레이아웃에서는 외부 공식 사이트도 별도 목적지로
   계산해, 서로 다른 결과가 합쳐지는 조상 컨테이너까지 박스가 커지지 않게
   했습니다.

## 수정 후 검증

동일 키워드와 동일한 39개 URL로 다시 실행했습니다.

```text
found_count = 2
found = djsvh123/224368808876, lauren0303/224369778788
aiSectionCount = 1
aiHighlightedCount = 0
selected boxes = ugcItem 632x226, ugcItem 632x140
```

재현용 DOM에서도 실제 Playwright 메서드를 실행해 다음을 확인했습니다.

```text
ai_primary = false
selected_card = data-template-id="ugcItem"
containsOfficial = false
```

`ugcItem` 의미 표식을 제거한 구형 레이아웃 재현에서도 선택 결과가 대상
게시물 컨테이너(`.target`)였고 `containsOfficial = false`임을 확인했습니다.

자료:

- [수정 후 실검색 전체 캡처](after/1_무료사료체험.png)
- [수정 후 경계 검증 캡처](after/synthetic-boundary-check.png)

## 테스트 결과

- 통합검색 전용 단위 테스트: `15 passed`
- 전체 단위 테스트: `48 passed, 3 failed`
- 전체 테스트의 실패 3개는 이번 변경 파일과 무관한 기존 의존성 주입 API
  불일치입니다(`bootstrap(uow=...)` 2건, `SearchJobCreatedHandler(uow=...)`
  1건).
