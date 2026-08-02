# Instagram 검색 결과 스크린샷 및 릴스 렌더링 개선

## 개요

Instagram 키워드 검색 결과의 데스크톱 레이아웃이 한 줄당 3개에서 5개로 변경되었다. 기존 구현은 상위 9개(3열 × 3행)를 대상으로 검색·매칭·강조·스크린샷을 수행했기 때문에 새로운 레이아웃의 표시 범위와 맞지 않았다.

동시에 검색 결과에 릴스 비중이 늘어나면서 일반 이미지는 정상적으로 표시되지만 일부 릴스 영역은 흰색으로 캡처되는 문제가 발생했다. 이 문서는 해당 문제의 원인 분석, 구현 변경 및 실제 검증 결과를 기록한다.

## 사용자 증상

- 검색 결과가 5열 레이아웃인데도 코드가 상위 9개만 처리했다.
- 릴스 링크, 재생 아이콘 및 매칭된 게시물의 빨간 테두리는 표시됐다.
- 릴스 카드 내부의 영상 프레임만 흰색으로 캡처됐다.
- 대기 시간을 늘려도 특정 릴스는 계속 흰색이었다.

재현에 사용한 데이터:

- 검색어: `코스트코`
- 대상 게시물: `https://www.instagram.com/p/DMzlYdFBhqP/`

## 기존 구현의 문제

### 1. 처리 범위가 9개로 고정됨

`get_top_9_posts()`가 게시물과 릴스 링크를 9개로 잘랐고 서비스의 매칭 및 강조 로직도 동일한 목록을 사용했다. 스크린샷 높이 역시 9번째 게시물을 마지막 항목으로 계산했다.

### 2. 이미지 로딩만 확인함

스크린샷 직전 대기 코드는 페이지의 `img` 요소만 검사했다.

- `img.complete`
- `img.naturalWidth > 0`

`video` 요소의 네트워크 상태, 디코딩 상태 또는 첫 프레임 렌더링 여부는 확인하지 않았다. 따라서 페이지 DOM이 준비됐더라도 비디오 픽셀이 아직 없는 상태로 촬영할 수 있었다.

### 3. Playwright 번들 Chromium의 미디어 코덱 제약

단순히 비디오 대기를 추가한 뒤에도 대상 릴스는 렌더링되지 않았다. 별도 진단 스크립트로 실제 DOM 미디어 상태를 수집한 결과 대상 영상은 다음 상태였다.

```text
readyState: 0
networkState: 3
videoWidth: 0
MediaError.code: 4 (MEDIA_ERR_SRC_NOT_SUPPORTED)
```

이는 느린 로딩이 아니라 브라우저가 MP4 비디오 스트림을 지원하지 못한 상태다. Playwright가 내려받은 번들 Chromium에서는 해당 Instagram 영상의 H.264 디코딩이 실패했다. 따라서 대기 시간을 늘리는 방식으로는 해결할 수 없다.

## 해결 방법

### 1. 상위 10개로 처리 범위 통일

새 레이아웃의 두 행을 처리하도록 기준을 10개로 변경했다.

- 게시물 조회: 상위 10개
- URL 매칭: 상위 10개
- 빨간 테두리 강조: 상위 10개 내 매칭 결과
- 스크린샷 영역: 10번째 게시물의 하단까지
- 성능 로그 체크포인트: `top_10_posts_retrieved`

그리드 너비는 첫 번째 행의 실제 bounding box를 사용하므로 5열 전체 너비를 동적으로 포함한다.

### 2. 선택한 게시물의 이미지와 비디오를 함께 대기

페이지 전체가 아니라 상위 10개 게시물 카드 내부의 `img, video`만 대상으로 준비 상태를 확인한다.

이미지는 다음 조건을 사용한다.

- 로드 또는 오류 이벤트 대기
- `complete` 및 `naturalWidth` 확인
- 지원되는 경우 `img.decode()` 완료 대기

비디오는 다음 절차를 사용한다.

- `muted`, `playsInline`, `preload=auto` 설정
- `loadeddata` 또는 `canplay` 이벤트 대기
- `readyState >= HAVE_CURRENT_DATA` 확인
- `videoWidth > 0` 확인
- 비디오 재생을 시작한 뒤 `requestVideoFrameCallback()`으로 실제 첫 프레임 제출을 대기
- 프레임이 준비되면 일시 정지한 상태로 스크린샷 촬영

미디어별 최대 대기 시간은 15초이며 모든 미디어를 병렬로 기다린다. 로그에는 `total`, `videos`, `ready`가 기록되어 향후 실패 항목을 확인할 수 있다.

### 3. 설치된 Google Chrome 사용

Instagram 영상 디코딩을 보장하기 위해 Playwright 번들 Chromium을 사용하지 않고 설치된 Google Chrome 실행 파일을 사용한다.

Windows에서는 다음 위치를 탐색한다.

- `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe`
- `%PROGRAMFILES%\Google\Chrome\Application\chrome.exe`
- `%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe`

`VIRAL_REPORTER_BROWSER_PATH` 환경 변수로 명시적인 실행 파일을 지정할 수도 있다. Chrome을 찾지 못하면 번들 Chromium으로 되돌아가지 않고 Chrome 설치 안내 메시지를 표시한다.

Chrome 실행 파일만 사용하며 사용자의 개인 Chrome 프로필은 열지 않는다. 앱은 별도의 Playwright BrowserContext와 별도의 Instagram 세션 파일을 사용한다.

## 진단 도구

`scripts/diagnose_instagram_video.py`는 실제 Instagram 검색 페이지에서 다음 정보를 수집한다.

- 상위 10개 게시물 URL 및 bounding box
- 게시물별 이미지/비디오 소스와 크기
- 비디오 `readyState`, `networkState`, 해상도 및 오류 코드
- 실패한 MP4 요청
- 전체 페이지, 게시물별 및 실제 앱 방식 스크린샷

진단 산출물은 `.diagnostics/instagram-video/`에 생성되며 Git 추적 대상에서 제외된다.

## 검증 결과

설치된 시스템 Chrome 계열 브라우저로 동일한 검색어와 대상 게시물을 다시 실행한 결과:

```text
대상 게시물: /p/DMzlYdFBhqP/
readyState: 4 (HAVE_ENOUGH_DATA)
videoWidth: 720
videoHeight: 1280
MediaError: 없음
```

최종 애플리케이션 실행 로그에서는 다음 결과가 확인됐다.

```text
상위 포스트: 10개
전체 미디어: 10개
비디오: 8개
준비 완료: 10개
스크린샷 파일 크기: 1,630,883 bytes
```

대상 게시물 매칭과 빨간 테두리가 유지되면서 릴스 첫 프레임이 정상적으로 스크린샷에 포함됐다.

## 테스트

단위 테스트는 다음을 검증한다.

- 12개의 검색 결과 중 정확히 상위 10개만 반환
- 비디오 첫 프레임 대기 스크립트와 옵션 전달
- 환경 변수로 지정한 Chrome 우선 사용
- PATH에 설치된 Chrome 탐색
- Windows 기본 설치 경로 탐색
- Chrome 미설치 시 사용자용 예외 발생

실제 네트워크 진단은 저장된 Instagram 앱 전용 세션을 이용해 별도 진단 스크립트로 수행한다.
