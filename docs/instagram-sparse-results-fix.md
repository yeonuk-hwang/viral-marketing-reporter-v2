# Instagram 희소 검색 결과 처리 개선

## 배경

Instagram 키워드 검색 결과가 상위 10개보다 적은 경우에도 검색·매칭·스크린샷 처리가 정상적으로 끝나야 한다. 다음 실제 데이터에서 게시물이 2개뿐인 검색어가 보고됐다.

```text
검색어: 블루드래곤팟타이누들키트
대상 1: https://www.instagram.com/reel/DbLMnqkypHo
대상 2: https://www.instagram.com/reel/DbK6-2_Jqq8
```

사용자는 이 검색어를 포함한 15개 키워드를 한 번에 검사할 때 오류를 경험했다.

## 실제 재현 결과

앱과 동일한 저장 세션, 1920×1080 검색 컨텍스트, `PlaywrightInstagramService` 전체 경로로 15개 키워드를 실행했다.

희소 검색어 결과:

```text
검색 결과 게시물: 2개
대상 릴스 매칭: 2개
미디어 준비: 성공
bounding box: 2개
스크린샷: 성공
```

생성된 스크린샷에는 두 릴스가 한 행에 표시되고 각각 빨간색 매칭 테두리가 적용됐다. 즉, 현재 페이지 배치 자체는 2개 게시물도 렌더링할 수 있었다.

전체 배치에서는 대상 게시물이 없는 검색어도 다수 확인됐다. 이 경로를 조사하면서 희소 결과 및 빈 결과에서 오류로 이어질 수 있는 세 가지 결함을 확인했다.

## 확인된 문제

### 1. 스크린샷이 없어도 `Screenshot(None)` 반환

대상 게시물이 상위 결과에 없고 `모든 게시물 스크린샷` 옵션도 꺼져 있으면 캡처를 생략한다. 기존 코드는 `screenshot_path=None`인 상태에서도 다음과 같은 객체를 만들었다.

```python
Screenshot(file_path=None)
```

도메인 모델에서 `file_path`는 `Path`여야 한다. 이 잘못된 객체가 결과 UI로 전달되면 문자열 `"None"`을 파일 경로처럼 다루거나 후속 파일 처리에서 오류를 일으킬 수 있다.

### 2. 결과가 0개일 때 게시물만 대기

검색 페이지 이동 후 코드는 첫 게시물 링크가 나타날 때까지 최대 60초 기다렸다. Instagram이 `No results found`를 이미 표시했더라도 게시물이 없다는 정상 상태를 인식하지 못하고 Playwright timeout으로 작업을 오류 처리할 수 있었다.

### 3. 스크린샷 영역이 목록 순서에 의존

기존 높이 계산은 수집된 bounding box 목록의 마지막 항목이 화면에서 가장 아래 게시물이라고 가정했다. 일부 locator의 box가 일시적으로 누락되거나 DOM 순서와 시각적 배치가 다르면 잘못된 높이가 계산될 수 있었다.

## 해결 방법

### 검색 결과 준비 조건 통합

페이지 이동 후 다음 중 하나가 보이면 검색 결과가 준비된 것으로 처리한다.

- 첫 게시물 또는 릴스 링크
- `No results found`

따라서 결과 없음은 timeout 오류가 아니라 정상적인 빈 `SearchResult`가 된다.

### 실제 box 범위 기반 동적 clip

1개부터 10개까지 동일한 계산 함수를 사용한다.

- 첫 행: 가장 작은 y 좌표 기준
- 왼쪽: 첫 행 box의 최소 x
- 오른쪽: 첫 행 box의 최대 `x + width`
- 아래쪽: 모든 box의 최대 `y + height`
- clip x: 음수가 되지 않도록 0으로 제한
- 좌우 20px 여백 적용

게시물 개수나 DOM 목록의 마지막 항목에 의존하지 않는다.

### 캡처 없음 표현 수정

실제 파일이 생성된 경우에만 `Screenshot`을 만든다.

```python
screenshot = Screenshot(file_path=screenshot_path) if screenshot_path else None
```

## 테스트

자동 테스트에서 다음 경우를 검증한다.

- 1개 게시물 clip
- 2개 게시물 clip
- 3개 게시물 clip
- 10개 게시물 clip
- 2개의 희소 검색 결과에 대상 매칭이 없을 때 `screenshot is None`
- 캡처 함수가 불필요하게 호출되지 않음

실제 네트워크 진단은 다음 명령으로 재현할 수 있다.

```bash
# 보고된 2개 결과 검색어만 검사
uv run python scripts/diagnose_instagram_sparse_results.py

# 제공된 15개 키워드 전체 검사
uv run python scripts/diagnose_instagram_sparse_results.py --all-keywords
```

진단 결과는 `.diagnostics/instagram-sparse-results/`에 저장되며 Git에는 포함되지 않는다.

## 최종 검증

수정 후 실제 희소 검색어를 다시 실행한 결과:

```text
상위 포스트 2개 발견
포스트 매칭 완료: 2개
포스트 위치 정보 수집 완료: 2개
스크린샷 촬영 완료
```

두 대상 릴스 URL이 모두 반환됐으며 스크린샷 파일도 정상 생성됐다.
