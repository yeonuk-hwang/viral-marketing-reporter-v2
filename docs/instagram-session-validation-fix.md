# Instagram 저장 세션 오탐 수정

## 증상

사용자가 이미 로그인되어 있고 저장된 세션 쿠키도 유효하지만 검색을 시작할 때마다 간헐적으로 headful Chrome 창이 열렸다. 사용자가 아무 작업을 하지 않아도 창이 열린 직후 로그인 완료로 처리됐다.

## 원인

저장 세션 검증과 로그인 완료 감지가 서로 다른 기준을 사용했다.

- 저장 세션 검증: 화면에서 `Profile` 텍스트 검색
- 로그인 완료 감지: 로그인 사용자에게 표시되는 `New post` SVG 아이콘 검색

Instagram UI에서는 로그인 상태여도 `Profile` 텍스트가 항상 노출되지 않는다. 그 결과 저장 세션 검증은 실패했지만, 같은 쿠키를 headful 브라우저에 넣으면 `New post` 아이콘이 즉시 나타나 로그인 성공으로 판정됐다. 실제 세션 만료가 아니라 검증 셀렉터의 오탐이었다.

## 해결

두 인증 경로가 동일한 `AUTHENTICATED_UI_SELECTOR`와 `_wait_for_authenticated_ui()`를 사용하도록 통합했다.

```text
svg[aria-label="New post"]
```

저장 세션 검증은 다음 순서로 동작한다.

1. 앱 전용 `instagram_session.json`으로 격리된 BrowserContext 생성
2. Instagram 홈 페이지 이동
3. 로그인 사용자 전용 UI가 최대 10초 내 표시되는지 확인
4. 성공 시 검증 과정에서 갱신된 쿠키를 같은 세션 파일에 다시 저장
5. 실패한 경우에만 별도의 headful 로그인 Chrome 표시

페이지는 성공과 실패 여부에 관계없이 `finally` 블록에서 닫힌다.

## 프로필 격리

앱은 설치된 Google Chrome 실행 파일을 사용하지만 사용자의 기존 Chrome 프로필 디렉터리를 열지 않는다. Playwright의 별도 BrowserContext와 다음 앱 전용 세션 파일만 사용한다.

```text
~/Downloads/viral-reporter/instagram_session.json
```

따라서 사용자의 일반 Chrome 쿠키, 방문 기록, 확장 프로그램 및 다른 로그인 계정과 분리된다.

## 검증 결과

실제 저장 세션을 사용한 headless 네트워크 진단 결과:

```text
세션 유효성 검증 성공 - 인증 UI 확인됨
검증 시간: 4.541초
saved_session_valid=True
```

headful 로그인 창을 띄우지 않고 기존 세션을 정상적으로 재사용했다.
