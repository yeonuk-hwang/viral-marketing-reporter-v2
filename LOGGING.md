# 로깅 시스템 문서

## 목차
1. [개요](#개요)
2. [로깅 유틸리티](#로깅-유틸리티)
3. [로깅 아키텍처](#로깅-아키텍처)
4. [컴포넌트별 로깅](#컴포넌트별-로깅)
5. [이벤트 타입 및 필드](#이벤트-타입-및-필드)
6. [로그 분석 및 활용](#로그-분석-및-활용)
7. [예제 로그 출력](#예제-로그-출력)

---

## 개요

Viral Marketing Reporter는 **구조화된 로깅(Structured Logging)**과 **성능 추적(Performance Tracking)**을 통해 전체 작업 흐름을 상세하게 기록합니다. [Loguru](https://github.com/Delgan/loguru) 라이브러리를 사용하여 다음과 같은 특징을 제공합니다:

### 주요 특징

- **이벤트 기반 로깅**: 모든 주요 작업에 고유한 `event_name` 부여
- **구조화된 데이터**: JSON 직렬화 가능한 메타데이터 포함
- **성능 추적**: 각 작업의 실행 시간 및 체크포인트 기록
- **컨텍스트 인식**: 플랫폼, 키워드, Task ID 등 컨텍스트 정보 자동 추가
- **다층 로깅**: DEBUG, INFO, WARNING, ERROR 레벨 구분
- **파일 및 콘솔 출력**: 동시에 파일(`debug.log`)과 콘솔에 출력

### 로그 저장 위치

```
~/Downloads/viral-reporter/debug.log
```

- **Rotation**: 10 MB마다 새 파일 생성
- **Retention**: 7일간 보관
- **Format**: JSON 직렬화 (`serialize=True`)

---

## 로깅 유틸리티

로깅 유틸리티는 `src/viral_marketing_reporter/infrastructure/logging_utils.py`에 정의되어 있습니다.

### 1. `@log_function_call` 데코레이터

함수의 진입, 종료, 실행 시간을 자동으로 로깅합니다.

#### 기능
- 함수 시작 시 `→ module.function(args)` 로깅
- 함수 종료 시 `← module.function completed in X.XXXs` 로깅
- 예외 발생 시 `✗ module.function failed after X.XXXs: ErrorType: message` 로깅
- async/sync 함수 모두 지원

#### 사용 예제

```python
from viral_marketing_reporter.infrastructure.logging_utils import log_function_call

@log_function_call
async def _get_authenticated_context(self) -> BrowserContext:
    # 함수 로직
    return context
```

#### 로그 출력 예제

```
→ viral_marketing_reporter.infrastructure.platforms.instagram.auth_service.InstagramAuthService._get_authenticated_context()
← viral_marketing_reporter.infrastructure.platforms.instagram.auth_service.InstagramAuthService._get_authenticated_context completed in 2.345s
```

---

### 2. `log_step()` 컨텍스트 매니저

특정 작업 단계를 시작과 종료로 감싸서 로깅합니다.

#### 기능
- 작업 시작 시 `▶ step_name` 로깅 (INFO 레벨)
- 작업 완료 시 `✓ step_name completed in X.XXXs` 로깅 (INFO 레벨)
- 예외 발생 시 `✗ step_name failed after X.XXXs: ErrorType: message` 로깅 (ERROR 레벨)
- 추가 컨텍스트 정보를 키워드 인자로 전달 가능

#### 사용 예제

```python
from viral_marketing_reporter.infrastructure.logging_utils import log_step

with log_step("플랫폼 사전 준비", platforms=["instagram", "naver_blog"], platform_count=2):
    # 작업 수행
    pass
```

#### 로그 출력 예제

```
▶ 플랫폼 사전 준비 | platforms=['instagram', 'naver_blog'] platform_count=2
✓ 플랫폼 사전 준비 completed in 3.456s | duration=3.456s platforms=['instagram', 'naver_blog'] platform_count=2
```

---

### 3. `PerformanceTracker` 클래스

복잡한 작업의 성능을 체크포인트 단위로 추적합니다.

#### 기능
- `start()`: 추적 시작
- `checkpoint(name)`: 중간 지점 기록 (시작 시점부터 경과 시간)
- `end()`: 추적 종료 및 전체 메트릭 로깅

#### 사용 예제

```python
from viral_marketing_reporter.infrastructure.logging_utils import PerformanceTracker

tracker = PerformanceTracker("instagram_search_이천데이트")
tracker.start()

# 작업 1
await search_page.goto(keyword)
tracker.checkpoint("page_loaded")

# 작업 2
posts = await search_page.get_top_9_posts()
tracker.checkpoint("posts_retrieved")

# 작업 3
screenshot = await search_page.take_screenshot()
tracker.checkpoint("screenshot_taken")

tracker.end()
```

#### 로그 출력 예제

```
Performance tracking started: instagram_search_이천데이트
Checkpoint 'page_loaded' reached | tracker=instagram_search_이천데이트 elapsed=1.234s
Checkpoint 'posts_retrieved' reached | tracker=instagram_search_이천데이트 elapsed=2.456s
Checkpoint 'screenshot_taken' reached | tracker=instagram_search_이천데이트 elapsed=5.789s
Performance metrics for instagram_search_이천데이트 | page_loaded=1.234s posts_retrieved=2.456s screenshot_taken=5.789s total=5.789s
```

---

### 4. `@log_with_context()` 데코레이터

함수 실행 중 모든 로그에 특정 컨텍스트를 추가합니다.

#### 기능
- loguru의 `contextualize()` 기능 활용
- 함수 내 모든 logger 호출에 자동으로 컨텍스트 추가
- async/sync 함수 모두 지원

#### 사용 예제

```python
from viral_marketing_reporter.infrastructure.logging_utils import log_with_context

@log_with_context(platform="instagram")
async def search_and_find_posts(self, ...):
    logger.info("검색 시작")  # 자동으로 platform="instagram" 추가됨
    # ...
```

#### 로그 출력 예제

```
검색 시작 | platform=instagram
```

---

## 로깅 아키텍처

### 로깅 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│              Application Layer                          │
│  - Job/Task 실행 흐름                                    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│            Infrastructure Layer                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Factory (factory.py)                            │    │
│  │ - prepare_platforms(): 인증 준비                │    │
│  │ - get_service(): 서비스 생성                    │    │
│  │ - cleanup(): 리소스 정리                        │    │
│  └─────────────────────────────────────────────────┘    │
│                        ↓                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Auth Service (auth_service.py)                  │    │
│  │ - authenticate(): 인증 수행                     │    │
│  │ - _is_session_valid(): 세션 검증                │    │
│  │ - _show_login_dialog(): 로그인 다이얼로그       │    │
│  └─────────────────────────────────────────────────┘    │
│                        ↓                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Platform Service (service.py)                   │    │
│  │ - search_and_find_posts(): 검색 및 매칭         │    │
│  │ - _get_matching_post_if_found(): 포스트 매칭    │    │
│  └─────────────────────────────────────────────────┘    │
│                        ↓                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Page Objects (page_objects.py)                  │    │
│  │ - goto(): 페이지 이동                           │    │
│  │ - get_top_N_posts(): 포스트 수집                │    │
│  │ - take_screenshot_of_results(): 스크린샷        │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│           Logging Infrastructure                         │
│  - Loguru (파일 + 콘솔 출력)                             │
│  - JSON 직렬화                                           │
│  - Rotation & Retention                                  │
└─────────────────────────────────────────────────────────┘
```

### 로깅 흐름

1. **Factory 레벨**: 플랫폼 준비 및 서비스 생성 로깅
2. **Auth Service 레벨**: 인증 흐름 상세 로깅
3. **Platform Service 레벨**: 검색 및 매칭 로직 로깅
4. **Page Objects 레벨**: 브라우저 조작 및 스크린샷 로깅

각 레벨은 독립적으로 로깅하며, 상위 레벨은 하위 레벨의 요약 정보를 로깅합니다.

---

## 컴포넌트별 로깅

### 1. Factory (`factory.py`)

#### `prepare_platforms()`
플랫폼 인증 사전 준비 과정을 추적합니다.

**로깅 내용:**
- 준비할 플랫폼 목록
- 각 플랫폼의 인증 상태 (이미 인증됨 / 새로 인증 / 인증 불필요)
- 인증 완료 시간 (체크포인트)
- 전체 준비 시간

**주요 이벤트:**
- `auth_start`: 플랫폼 인증 시작
- `auth_skip`: 이미 인증된 플랫폼
- `auth_not_required`: 인증이 필요 없는 플랫폼

**예제 로그:**
```
▶ 플랫폼 사전 준비 | platforms=['instagram', 'naver_blog'] platform_count=2
instagram 인증 시작 | platform=instagram event_name=auth_start
✓ 플랫폼 사전 준비 completed in 2.345s
Performance metrics for prepare_platforms | instagram_authenticated=2.123s total=2.345s
```

---

#### `get_service()`
플랫폼 서비스 생성 과정을 로깅합니다.

**로깅 내용:**
- 요청한 플랫폼
- 사용할 컨텍스트 타입 (인증 / 기본)
- 생성된 서비스 클래스명

**주요 이벤트:**
- `service_creation_start`: 서비스 생성 시작
- `using_authenticated_context`: 인증된 컨텍스트 사용
- `using_default_context`: 기본 컨텍스트 사용
- `service_created`: 서비스 생성 완료
- `unsupported_platform`: 지원하지 않는 플랫폼 (에러)

**예제 로그:**
```
플랫폼 서비스 생성 시작 | platform=instagram event_name=service_creation_start
인증된 컨텍스트 사용 | platform=instagram event_name=using_authenticated_context
플랫폼 서비스 생성 완료 | platform=instagram service_class=PlaywrightInstagramService event_name=service_created
```

---

#### `cleanup()`
리소스 정리 과정을 추적합니다.

**로깅 내용:**
- 정리할 인증 서비스 개수
- 각 플랫폼의 정리 성공/실패 여부
- 정리 중 발생한 에러

**주요 이벤트:**
- `cleanup_start`: 정리 시작
- `cleanup_success`: 정리 성공
- `cleanup_error`: 정리 중 오류 발생

**예제 로그:**
```
▶ 팩토리 리소스 정리 | auth_service_count=1
instagram 인증 서비스 정리 시작 | platform=instagram event_name=cleanup_start
instagram 인증 서비스 정리 완료 | platform=instagram event_name=cleanup_success
✓ 팩토리 리소스 정리 completed in 0.123s
```

---

### 2. Instagram Auth Service (`auth_service.py`)

#### `authenticate()`
Instagram 인증 수행 및 컨텍스트 반환을 로깅합니다.

**로깅 내용:**
- 캐시된 컨텍스트 재사용 여부
- 새 인증 수행 시작/완료

**예제 로그:**
```
Instagram 인증을 시작합니다...
캐시된 Instagram Context를 재사용합니다.
Instagram 인증이 완료되었습니다.
```

---

#### `_get_authenticated_context()`
인증된 브라우저 컨텍스트 생성 전체 과정을 추적합니다.

**로깅 내용:**
- 세션 로드 여부
- 세션 유효성 검증 결과
- 로그인 다이얼로그 실행 여부
- 성능 체크포인트

**주요 이벤트:**
- `session_load`: 저장된 세션 로드
- `authenticated_context_ready`: 인증 완료
- `session_expired`: 세션 만료
- `login_required`: 로그인 필요
- `login_failed`: 로그인 실패

**성능 체크포인트:**
- `context_created_with_session`: 세션으로 컨텍스트 생성
- `session_validated`: 세션 검증 완료
- `session_invalid_closed`: 유효하지 않은 세션 정리
- `login_dialog_completed`: 로그인 다이얼로그 완료
- `context_created_with_new_session`: 새 세션으로 컨텍스트 생성

**예제 로그:**
```
→ _get_authenticated_context()
저장된 Instagram 세션 로드 | storage_path=/Users/.../instagram_session.json event_name=session_load
세션 유효성 검증 성공 - 로그인 상태 확인됨 | event_name=session_valid
Instagram 인증된 컨텍스트 사용 | event_name=authenticated_context_ready
← _get_authenticated_context() completed in 2.345s
Performance metrics for instagram_authentication | context_created_with_session=0.123s session_validated=2.234s total=2.345s
```

---

#### `_is_session_valid()`
세션 유효성을 검증합니다.

**로깅 내용:**
- 검증 시작
- Profile 텍스트 감지 여부
- 검증 결과

**주요 이벤트:**
- `session_validation_start`: 검증 시작
- `session_valid`: 세션 유효
- `session_invalid`: 세션 무효
- `session_validation_error`: 검증 중 오류

**예제 로그:**
```
▶ Instagram 세션 유효성 검증
Instagram 홈페이지로 이동하여 세션 검증 시작 | event_name=session_validation_start
세션 유효성 검증 성공 - 로그인 상태 확인됨 | event_name=session_valid
✓ Instagram 세션 유효성 검증 completed in 1.234s
```

---

#### `_show_login_dialog()`
Headful 브라우저 로그인 창을 표시합니다.

**로깅 내용:**
- 브라우저 실행
- 로그인 페이지 이동
- 기존 세션 쿠키 로드 시도
- 로그인 완료 대기
- 세션 저장

**주요 이벤트:**
- `login_dialog_open`: 로그인 창 열기
- `headful_context_created`: Headful 컨텍스트 생성
- `existing_cookies_loaded`: 기존 쿠키 로드 성공
- `existing_cookies_load_failed`: 기존 쿠키 로드 실패
- `login_page_loaded`: 로그인 페이지 로드
- `session_saved`: 세션 저장 완료
- `login_incomplete`: 로그인 미완료
- `headful_browser_closed`: 브라우저 닫기

**예제 로그:**
```
▶ Instagram 로그인 다이얼로그 표시
Headful 브라우저로 로그인 창 열기 | event_name=login_dialog_open
Headful 브라우저 컨텍스트 생성 완료 | event_name=headful_context_created
Instagram 로그인 페이지 이동 완료 | event_name=login_page_loaded
============================================================
브라우저에서 Instagram에 로그인해주세요.
로그인이 완료되면 자동으로 감지하여 진행합니다.
============================================================
로그인 세션 저장 완료 | storage_path=/Users/.../instagram_session.json event_name=session_saved
Headful 브라우저 닫기 완료 | event_name=headful_browser_closed
✓ Instagram 로그인 다이얼로그 표시 completed in 45.678s
```

---

#### `_wait_for_login_completion()`
로그인 완료를 감지합니다.

**로깅 내용:**
- 로그인 대기 시작
- 로그인 페이지 벗어남 감지
- Profile 텍스트 감지
- 팝업 닫기
- 로그인 완료

**주요 이벤트:**
- `login_wait_start`: 대기 시작
- `login_page_exited`: 로그인 페이지 벗어남
- `profile_element_detected`: Profile 요소 감지
- `profile_element_not_found`: Profile 요소 미발견
- `login_completed`: 로그인 완료
- `login_wait_error`: 대기 중 오류

**예제 로그:**
```
▶ 로그인 완료 대기 | timeout_seconds=300
로그인 완료 대기 시작 | timeout=300 event_name=login_wait_start
로그인 페이지 벗어남 감지 | current_url=https://www.instagram.com/ event_name=login_page_exited
프로필 요소 감지 - 로그인 성공 | event_name=profile_element_detected
로그인 완료 감지 성공 | event_name=login_completed
✓ 로그인 완료 대기 completed in 12.345s
```

---

### 3. Instagram Service (`service.py`)

#### `search_and_find_posts()`
Instagram 검색 및 포스트 매칭 전체 과정을 추적합니다.

**로깅 내용:**
- 검색 키워드 및 찾을 포스트 개수
- 페이지 이동 및 로드
- 상위 포스트 발견
- 포스트 매칭 결과
- 하이라이트 적용
- 스크린샷 촬영
- 페이지 정리

**주요 이벤트:**
- `navigate_to_search`: 검색 페이지 이동
- `result_not_found`: 검색 결과 없음
- `posts_retrieved`: 포스트 발견
- `posts_not_found`: 포스트 요소 없음
- `matching_start`: 매칭 시작
- `matching_completed`: 매칭 완료
- `highlight_start`: 하이라이트 시작
- `screenshot_start`: 스크린샷 시작
- `screenshot_completed`: 스크린샷 완료
- `page_load_timeout`: 페이지 로드 시간 초과
- `page_cleanup`: 페이지 정리

**성능 체크포인트:**
- `page_loaded`: 페이지 로드 완료
- `top_9_posts_retrieved`: 상위 9개 포스트 수집
- `posts_matched`: 포스트 매칭 완료
- `posts_highlighted`: 하이라이트 적용 완료
- `screenshot_taken`: 스크린샷 촬영 완료

**예제 로그:**
```
▶ Instagram 검색 및 포스트 매칭 | keyword=이천데이트 index=1 posts_to_find_count=2 platform=instagram
Instagram 검색 페이지로 이동 | keyword=이천데이트 event_name=navigate_to_search platform=instagram
상위 포스트 9개 발견 | keyword=이천데이트 post_count=9 event_name=posts_retrieved platform=instagram
포스트 매칭 시작 | keyword=이천데이트 event_name=matching_start platform=instagram
포스트 매칭 완료 | keyword=이천데이트 found_count=2 target_count=2 event_name=matching_completed platform=instagram
매칭된 포스트 하이라이트 적용 | keyword=이천데이트 highlight_count=2 event_name=highlight_start platform=instagram
스크린샷 촬영 시작 | keyword=이천데이트 event_name=screenshot_start platform=instagram
스크린샷 촬영 완료 | keyword=이천데이트 screenshot_path=/Users/.../1_이천데이트.png event_name=screenshot_completed platform=instagram
Instagram 페이지 정리 | keyword=이천데이트 event_name=page_cleanup platform=instagram
✓ Instagram 검색 및 포스트 매칭 completed in 8.456s
Performance metrics for instagram_search_이천데이트 | page_loaded=2.123s top_9_posts_retrieved=3.456s posts_matched=4.567s posts_highlighted=5.678s screenshot_taken=8.234s total=8.456s
```

---

### 4. Instagram Page Objects (`page_objects.py`)

#### `goto()`
검색 페이지로 이동합니다.

**로깅 내용:**
- 검색 URL
- 페이지 로드 완료
- 포스트 요소 대기
- 포스트 로드 완료

**주요 이벤트:**
- `page_navigate`: 페이지 이동
- `page_loaded`: 페이지 로드 완료
- `wait_for_posts`: 포스트 대기
- `posts_visible`: 포스트 표시됨

**예제 로그:**
```
→ goto(keyword='이천데이트')
Instagram 검색 페이지로 이동 | keyword=이천데이트 url=https://www.instagram.com/explore/search/keyword/?q=%EC%9D%B4%EC%B2%9C%EB%8D%B0%EC%9D%B4%ED%8A%B8 event_name=page_navigate
페이지 로드 완료 | keyword=이천데이트 event_name=page_loaded
포스트 요소 대기 중 | keyword=이천데이트 event_name=wait_for_posts
포스트 요소 로드 완료 | keyword=이천데이트 event_name=posts_visible
← goto() completed in 2.123s
```

---

#### `take_screenshot_of_results()`
상위 9개 포스트 영역의 스크린샷을 촬영합니다. **가장 상세한 로깅이 적용된 메서드입니다.**

**로깅 내용:**
- 포스트 발견
- 스크롤 동작 (최하단 → 최상단)
- 이미지 로딩 대기
- Bounding box 수집
- 스크린샷 영역 계산 (너비, 높이)
- Viewport 조정
- 스크린샷 촬영
- 파일 크기 및 경로

**주요 이벤트:**
- `posts_found_for_screenshot`: 포스트 발견
- `screenshot_failed_no_posts`: 포스트 없어 실패
- `scroll_to_last_post`: 마지막 포스트로 스크롤
- `scroll_to_top`: 최상단으로 스크롤
- `wait_for_images`: 이미지 로딩 대기
- `images_loaded`: 이미지 로딩 완료
- `collect_bounding_boxes`: Bounding box 수집
- `boxes_collected`: Box 수집 완료
- `screenshot_failed_no_boxes`: Box 없어 실패
- `screenshot_dimensions_calculated`: 영역 계산 완료
- `viewport_resized`: Viewport 크기 조정
- `screenshot_capture_start`: 촬영 시작
- `viewport_restored`: Viewport 복구
- `screenshot_saved`: 스크린샷 저장 완료

**성능 체크포인트:**
- `scrolled_to_bottom`: 하단 스크롤 완료
- `scrolled_to_top`: 상단 스크롤 완료
- `images_loaded`: 이미지 로딩 완료
- `viewport_adjusted`: Viewport 조정 완료
- `screenshot_captured`: 스크린샷 촬영 완료

**예제 로그:**
```
→ take_screenshot_of_results(index=1, keyword='이천데이트', output_dir=...)
▶ Instagram 스크린샷 촬영 | keyword=이천데이트 index=1
상위 9개 포스트 발견 | keyword=이천데이트 post_count=9 event_name=posts_found_for_screenshot
마지막 포스트로 스크롤 (lazy loading) | keyword=이천데이트 event_name=scroll_to_last_post
페이지 최상단으로 스크롤 | keyword=이천데이트 event_name=scroll_to_top
이미지 로딩 대기 중 | keyword=이천데이트 event_name=wait_for_images
이미지 로딩 완료 | keyword=이천데이트 event_name=images_loaded
포스트 위치 정보 수집 중 | keyword=이천데이트 event_name=collect_bounding_boxes
9개 포스트의 위치 정보 수집 완료 | keyword=이천데이트 box_count=9 event_name=boxes_collected
스크린샷 영역 계산 완료 | keyword=이천데이트 total_width=1200 clip_height=800 viewport_height=900 event_name=screenshot_dimensions_calculated
Viewport 높이 조정 | keyword=이천데이트 original_height=1080 new_height=900 event_name=viewport_resized
스크린샷 촬영 중 | keyword=이천데이트 output_path=/Users/.../1_이천데이트.png event_name=screenshot_capture_start
Viewport 원상복구 | keyword=이천데이트 event_name=viewport_restored
스크린샷 촬영 완료 | keyword=이천데이트 screenshot_path=/Users/.../1_이천데이트.png file_size_bytes=345678 event_name=screenshot_saved
✓ Instagram 스크린샷 촬영 completed in 6.789s
← take_screenshot_of_results() completed in 6.789s
Performance metrics for instagram_screenshot_이천데이트 | scrolled_to_bottom=2.123s scrolled_to_top=4.234s images_loaded=5.345s viewport_adjusted=5.456s screenshot_captured=6.567s total=6.789s
```

---

### 5. Naver Blog Service (`service.py`)

Instagram과 동일한 수준의 로깅을 제공하며, `platform="naver_blog"` 컨텍스트로 필터링 가능합니다.

**주요 차이점:**
- 상위 10개 포스트 추적 (`top_10_posts`)
- URL 리다이렉트 처리 로깅 (`ad_redirect_failed`)
- 매칭된 포스트가 있을 때만 스크린샷 촬영

**예제 로그:**
```
▶ 네이버 블로그 검색 및 포스트 매칭 | keyword=이천데이트 index=1 posts_to_find_count=2 platform=naver_blog
네이버 블로그 검색 페이지로 이동 | keyword=이천데이트 event_name=navigate_to_search platform=naver_blog
상위 포스트 10개 발견 | keyword=이천데이트 post_count=10 event_name=posts_retrieved platform=naver_blog
포스트 매칭 완료 | keyword=이천데이트 found_count=1 target_count=2 event_name=matching_completed platform=naver_blog
스크린샷 촬영 완료 | keyword=이천데이트 screenshot_path=/Users/.../1_이천데이트.png event_name=screenshot_completed platform=naver_blog
✓ 네이버 블로그 검색 및 포스트 매칭 completed in 7.890s
Performance metrics for naver_blog_search_이천데이트 | page_loaded=2.345s top_10_posts_retrieved=3.456s posts_matched=4.567s posts_highlighted=5.678s screenshot_taken=7.789s total=7.890s
```

---

## 이벤트 타입 및 필드

### 공통 필드

모든 로그 레코드는 다음 필드를 포함합니다:

| 필드 | 설명 | 예시 |
|------|------|------|
| `time` | 로그 발생 시간 | `2025-11-13 02:34:56.789` |
| `level` | 로그 레벨 | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `name` | 모듈 이름 | `viral_marketing_reporter.infrastructure.platforms.instagram.service` |
| `function` | 함수 이름 | `search_and_find_posts` |
| `line` | 소스 코드 라인 번호 | `123` |
| `message` | 로그 메시지 | `Instagram 검색 페이지로 이동` |

### 이벤트별 추가 필드

#### 인증 관련 이벤트

| event_name | 추가 필드 | 설명 |
|------------|-----------|------|
| `auth_start` | `platform` | 인증 시작 |
| `auth_skip` | `platform` | 이미 인증됨 |
| `session_load` | `storage_path` | 세션 파일 로드 |
| `session_valid` | - | 세션 유효 |
| `session_expired` | `storage_path` | 세션 만료 |
| `login_required` | - | 로그인 필요 |
| `login_completed` | - | 로그인 완료 |
| `session_saved` | `storage_path` | 세션 저장 |

#### 서비스 생성 관련 이벤트

| event_name | 추가 필드 | 설명 |
|------------|-----------|------|
| `service_creation_start` | `platform` | 서비스 생성 시작 |
| `using_authenticated_context` | `platform` | 인증된 컨텍스트 사용 |
| `using_default_context` | `platform` | 기본 컨텍스트 사용 |
| `service_created` | `platform`, `service_class` | 서비스 생성 완료 |

#### 검색 및 매칭 관련 이벤트

| event_name | 추가 필드 | 설명 |
|------------|-----------|------|
| `navigate_to_search` | `keyword`, `platform` | 검색 페이지 이동 |
| `result_not_found` | `keyword`, `platform` | 검색 결과 없음 |
| `posts_retrieved` | `keyword`, `post_count`, `platform` | 포스트 발견 |
| `posts_not_found` | `keyword`, `platform` | 포스트 요소 없음 |
| `matching_start` | `keyword`, `platform` | 매칭 시작 |
| `matching_completed` | `keyword`, `found_count`, `target_count`, `platform` | 매칭 완료 |

#### 스크린샷 관련 이벤트

| event_name | 추가 필드 | 설명 |
|------------|-----------|------|
| `screenshot_start` | `keyword`, `platform` | 스크린샷 시작 |
| `scroll_to_last_post` | `keyword` | 마지막 포스트로 스크롤 |
| `scroll_to_top` | `keyword` | 최상단으로 스크롤 |
| `wait_for_images` | `keyword` | 이미지 로딩 대기 |
| `images_loaded` | `keyword` | 이미지 로딩 완료 |
| `screenshot_dimensions_calculated` | `keyword`, `total_width`, `clip_height`, `viewport_height` | 영역 계산 |
| `viewport_resized` | `keyword`, `original_height`, `new_height` | Viewport 조정 |
| `screenshot_saved` | `keyword`, `screenshot_path`, `file_size_bytes` | 저장 완료 |
| `screenshot_completed` | `keyword`, `screenshot_path`, `platform` | 스크린샷 완료 |

#### 에러 관련 이벤트

| event_name | 추가 필드 | 설명 |
|------------|-----------|------|
| `page_load_timeout` | `keyword`, `platform`, `error`, `error_type` | 페이지 로드 시간 초과 |
| `cleanup_error` | `platform`, `error`, `error_type` | 정리 중 오류 |
| `screenshot_failed_no_posts` | `keyword` | 포스트 없어 스크린샷 실패 |
| `screenshot_failed_no_boxes` | `keyword` | Box 없어 스크린샷 실패 |

---

## 로그 분석 및 활용

### 1. 로그 필터링

#### 플랫폼별 필터링

로그 파일에서 특정 플랫폼의 로그만 추출:

```bash
# Instagram 관련 로그만 추출
grep '"platform":"instagram"' ~/Downloads/viral-reporter/debug.log

# Naver Blog 관련 로그만 추출
grep '"platform":"naver_blog"' ~/Downloads/viral-reporter/debug.log
```

#### 이벤트별 필터링

특정 이벤트만 추출:

```bash
# 인증 시작 이벤트
grep '"event_name":"auth_start"' ~/Downloads/viral-reporter/debug.log

# 스크린샷 완료 이벤트
grep '"event_name":"screenshot_completed"' ~/Downloads/viral-reporter/debug.log

# 에러 이벤트
grep '"event_name":".*_error"' ~/Downloads/viral-reporter/debug.log
```

#### 키워드별 필터링

특정 키워드 검색 로그만 추출:

```bash
grep '"keyword":"이천데이트"' ~/Downloads/viral-reporter/debug.log
```

---

### 2. 성능 분석

#### 작업별 실행 시간 확인

```bash
# Instagram 검색 성능 메트릭
grep 'Performance metrics for instagram_search' ~/Downloads/viral-reporter/debug.log

# 스크린샷 촬영 성능 메트릭
grep 'Performance metrics for instagram_screenshot' ~/Downloads/viral-reporter/debug.log
```

**예제 출력:**
```json
{
  "time": "2025-11-13 02:34:56.789",
  "level": "INFO",
  "message": "Performance metrics for instagram_search_이천데이트",
  "page_loaded": "2.123s",
  "top_9_posts_retrieved": "3.456s",
  "posts_matched": "4.567s",
  "posts_highlighted": "5.678s",
  "screenshot_taken": "8.234s",
  "total": "8.456s"
}
```

#### 체크포인트별 시간 분석

각 체크포인트의 시간을 분석하여 병목 지점을 파악할 수 있습니다:

- `page_loaded`: 페이지 로드 시간 (네트워크 속도, 서버 응답)
- `posts_matched`: 매칭 로직 실행 시간 (URL 비교)
- `screenshot_taken`: 스크린샷 촬영 시간 (이미지 로딩, 렌더링)

---

### 3. 에러 추적

#### 에러 로그 추출

```bash
# 모든 에러 로그
grep '"level":"ERROR"' ~/Downloads/viral-reporter/debug.log

# 특정 에러 타입
grep '"error_type":"TimeoutError"' ~/Downloads/viral-reporter/debug.log
```

#### 에러 컨텍스트 확인

에러 발생 시 다음 정보가 자동으로 로깅됩니다:
- `error`: 에러 메시지
- `error_type`: 에러 클래스명 (`TimeoutError`, `Exception` 등)
- `keyword`: 작업 중이던 키워드
- `platform`: 플랫폼 이름

---

### 4. 디버깅 워크플로우

#### 문제 발생 시 디버깅 절차

1. **에러 로그 확인**
   ```bash
   grep '"level":"ERROR"' ~/Downloads/viral-reporter/debug.log | tail -n 10
   ```

2. **해당 키워드의 전체 로그 추출**
   ```bash
   grep '"keyword":"문제키워드"' ~/Downloads/viral-reporter/debug.log
   ```

3. **이벤트 순서 확인**
   - 마지막으로 완료된 이벤트 확인
   - 다음 이벤트가 시작되었는지 확인
   - 어느 단계에서 멈췄는지 파악

4. **성능 메트릭 확인**
   - 체크포인트별 시간 확인
   - 비정상적으로 긴 시간이 걸린 단계 파악

---

### 5. JSON 파싱 및 분석

로그는 JSON 형식으로 직렬화되므로 `jq` 등의 도구로 분석 가능합니다.

#### jq를 사용한 로그 분석

```bash
# 모든 스크린샷 완료 이벤트의 파일 경로 추출
cat ~/Downloads/viral-reporter/debug.log | jq -r 'select(.event_name=="screenshot_completed") | .screenshot_path'

# Instagram 검색의 평균 실행 시간 계산
cat ~/Downloads/viral-reporter/debug.log | jq -r 'select(.message | startswith("Performance metrics for instagram_search")) | .total' | sed 's/s//' | awk '{sum+=$1; count++} END {print sum/count}'

# 매칭된 포스트 수 통계
cat ~/Downloads/viral-reporter/debug.log | jq -r 'select(.event_name=="matching_completed") | "\(.keyword): \(.found_count)/\(.target_count)"'
```

---

## 예제 로그 출력

### 완전한 Instagram 검색 작업 로그

다음은 Instagram에서 "이천데이트" 키워드로 검색하고 2개의 포스트를 찾아 스크린샷을 촬영하는 전체 과정의 로그 예제입니다.

```
2025-11-13 02:34:50.123 | INFO     | viral_marketing_reporter.infrastructure.platforms.factory:prepare_platforms:49 - ▶ 플랫폼 사전 준비 | platforms=['instagram'] platform_count=1
2025-11-13 02:34:50.124 | INFO     | viral_marketing_reporter.infrastructure.platforms.factory:prepare_platforms:58 - instagram 인증 시작 | platform=instagram event_name=auth_start
2025-11-13 02:34:50.125 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:authenticate:54 - Instagram 인증을 시작합니다...
2025-11-13 02:34:50.126 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:25 - → viral_marketing_reporter.infrastructure.platforms.instagram.auth_service.InstagramAuthService._get_authenticated_context()
2025-11-13 02:34:50.127 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:__enter__:80 - Performance tracking started: instagram_authentication
2025-11-13 02:34:50.128 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:_get_authenticated_context:109 - 저장된 Instagram 세션 로드 | storage_path=/Users/yeonuk/Downloads/viral-reporter/instagram_session.json event_name=session_load
2025-11-13 02:34:50.234 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'context_created_with_session' reached | tracker=instagram_authentication elapsed=0.107s
2025-11-13 02:34:51.456 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:_is_session_valid:179 - 세션 유효성 검증 성공 - 로그인 상태 확인됨 | event_name=session_valid
2025-11-13 02:34:51.457 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:_get_authenticated_context:121 - Instagram 인증된 컨텍스트 사용 | event_name=authenticated_context_ready
2025-11-13 02:34:51.458 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'session_validated' reached | tracker=instagram_authentication elapsed=1.330s
2025-11-13 02:34:51.459 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:end:132 - Performance metrics for instagram_authentication | context_created_with_session=0.107s session_validated=1.330s total=1.331s
2025-11-13 02:34:51.460 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:31 - ← viral_marketing_reporter.infrastructure.platforms.instagram.auth_service.InstagramAuthService._get_authenticated_context completed in 1.334s
2025-11-13 02:34:51.461 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:authenticate:56 - Instagram 인증이 완료되었습니다.
2025-11-13 02:34:51.462 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'instagram_authenticated' reached | tracker=prepare_platforms elapsed=1.339s
2025-11-13 02:34:51.463 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:__exit__:86 - ✓ 플랫폼 사전 준비 completed in 1.340s | duration=1.340s platforms=['instagram'] platform_count=1
2025-11-13 02:34:51.464 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:end:132 - Performance metrics for prepare_platforms | instagram_authenticated=1.339s total=1.340s

2025-11-13 02:34:51.500 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.factory:get_service:92 - 플랫폼 서비스 생성 시작 | platform=instagram event_name=service_creation_start
2025-11-13 02:34:51.501 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.factory:get_service:109 - 인증된 컨텍스트 사용 | platform=instagram event_name=using_authenticated_context
2025-11-13 02:34:51.502 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.auth_service:authenticate:58 - 캐시된 Instagram Context를 재사용합니다.
2025-11-13 02:34:51.612 | INFO     | viral_marketing_reporter.infrastructure.platforms.factory:get_service:126 - 플랫폼 서비스 생성 완료 | platform=instagram service_class=PlaywrightInstagramService event_name=service_created

2025-11-13 02:34:51.700 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:__enter__:80 - Performance tracking started: instagram_search_이천데이트
2025-11-13 02:34:51.701 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:__enter__:80 - ▶ Instagram 검색 및 포스트 매칭 | keyword=이천데이트 index=1 posts_to_find_count=2 platform=instagram
2025-11-13 02:34:51.702 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:90 - Instagram 검색 페이지로 이동 | keyword=이천데이트 event_name=navigate_to_search platform=instagram
2025-11-13 02:34:51.703 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:25 - → viral_marketing_reporter.infrastructure.platforms.instagram.page_objects.InstagramSearchPage.goto(keyword='이천데이트')
2025-11-13 02:34:51.704 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:goto:33 - Instagram 검색 페이지로 이동 | keyword=이천데이트 url=https://www.instagram.com/explore/search/keyword/?q=%EC%9D%B4%EC%B2%9C%EB%8D%B0%EC%9D%B4%ED%8A%B8 event_name=page_navigate
2025-11-13 02:34:53.234 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:goto:41 - 페이지 로드 완료 | keyword=이천데이트 event_name=page_loaded
2025-11-13 02:34:53.235 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:goto:48 - 포스트 요소 대기 중 | keyword=이천데이트 event_name=wait_for_posts
2025-11-13 02:34:53.456 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:goto:56 - 포스트 요소 로드 완료 | keyword=이천데이트 event_name=posts_visible
2025-11-13 02:34:53.457 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:31 - ← viral_marketing_reporter.infrastructure.platforms.instagram.page_objects.InstagramSearchPage.goto completed in 1.753s
2025-11-13 02:34:53.458 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'page_loaded' reached | tracker=instagram_search_이천데이트 elapsed=1.757s

2025-11-13 02:34:53.567 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:109 - 상위 포스트 9개 발견 | keyword=이천데이트 post_count=9 event_name=posts_retrieved platform=instagram
2025-11-13 02:34:53.568 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'top_9_posts_retrieved' reached | tracker=instagram_search_이천데이트 elapsed=1.867s

2025-11-13 02:34:53.569 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:130 - 포스트 매칭 시작 | keyword=이천데이트 event_name=matching_start platform=instagram
2025-11-13 02:34:53.789 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:149 - 포스트 매칭 완료 | keyword=이천데이트 found_count=2 target_count=2 event_name=matching_completed platform=instagram
2025-11-13 02:34:53.790 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'posts_matched' reached | tracker=instagram_search_이천데이트 elapsed=2.089s

2025-11-13 02:34:53.791 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:159 - 매칭된 포스트 하이라이트 적용 | keyword=이천데이트 highlight_count=2 event_name=highlight_start platform=instagram
2025-11-13 02:34:53.912 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'posts_highlighted' reached | tracker=instagram_search_이천데이트 elapsed=2.211s

2025-11-13 02:34:53.913 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:173 - 스크린샷 촬영 시작 | keyword=이천데이트 event_name=screenshot_start platform=instagram
2025-11-13 02:34:53.914 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:25 - → viral_marketing_reporter.infrastructure.platforms.instagram.page_objects.InstagramSearchPage.take_screenshot_of_results(index=1, keyword='이천데이트', output_dir=PosixPath('/Users/yeonuk/Downloads/viral-reporter/instagram/test'))
2025-11-13 02:34:53.915 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:__enter__:80 - Performance tracking started: instagram_screenshot_이천데이트
2025-11-13 02:34:53.916 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:__enter__:80 - ▶ Instagram 스크린샷 촬영 | keyword=이천데이트 index=1
2025-11-13 02:34:53.917 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:105 - 상위 9개 포스트 발견 | keyword=이천데이트 post_count=9 event_name=posts_found_for_screenshot
2025-11-13 02:34:53.918 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:113 - 마지막 포스트로 스크롤 (lazy loading) | keyword=이천데이트 event_name=scroll_to_last_post
2025-11-13 02:34:56.123 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'scrolled_to_bottom' reached | tracker=instagram_screenshot_이천데이트 elapsed=2.207s
2025-11-13 02:34:56.124 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:124 - 페이지 최상단으로 스크롤 | keyword=이천데이트 event_name=scroll_to_top
2025-11-13 02:34:58.234 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'scrolled_to_top' reached | tracker=instagram_screenshot_이천데이트 elapsed=4.318s
2025-11-13 02:34:58.235 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:134 - 이미지 로딩 대기 중 | keyword=이천데이트 event_name=wait_for_images
2025-11-13 02:35:03.456 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'images_loaded' reached | tracker=instagram_screenshot_이천데이트 elapsed=9.540s
2025-11-13 02:35:03.457 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:157 - 이미지 로딩 완료 | keyword=이천데이트 event_name=images_loaded
2025-11-13 02:35:03.458 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:167 - 포스트 위치 정보 수집 중 | keyword=이천데이트 event_name=collect_bounding_boxes
2025-11-13 02:35:03.567 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:188 - 9개 포스트의 위치 정보 수집 완료 | keyword=이천데이트 box_count=9 event_name=boxes_collected
2025-11-13 02:35:03.568 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:225 - 스크린샷 영역 계산 완료 | keyword=이천데이트 total_width=1200 clip_height=800 viewport_height=900 event_name=screenshot_dimensions_calculated
2025-11-13 02:35:03.569 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:237 - Viewport 높이 조정 | keyword=이천데이트 original_height=1080 new_height=900 event_name=viewport_resized
2025-11-13 02:35:03.678 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'viewport_adjusted' reached | tracker=instagram_screenshot_이천데이트 elapsed=9.762s
2025-11-13 02:35:03.679 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:261 - 스크린샷 촬영 중 | keyword=이천데이트 output_path=/Users/yeonuk/Downloads/viral-reporter/instagram/test/1_이천데이트.png event_name=screenshot_capture_start
2025-11-13 02:35:04.123 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'screenshot_captured' reached | tracker=instagram_screenshot_이천데이트 elapsed=10.207s
2025-11-13 02:35:04.124 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:273 - Viewport 원상복구 | keyword=이천데이트 event_name=viewport_restored
2025-11-13 02:35:04.125 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.page_objects:take_screenshot_of_results:279 - 스크린샷 촬영 완료 | keyword=이천데이트 screenshot_path=/Users/yeonuk/Downloads/viral-reporter/instagram/test/1_이천데이트.png file_size_bytes=345678 event_name=screenshot_saved
2025-11-13 02:35:04.126 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:end:132 - Performance metrics for instagram_screenshot_이천데이트 | scrolled_to_bottom=2.207s scrolled_to_top=4.318s images_loaded=9.540s viewport_adjusted=9.762s screenshot_captured=10.207s total=10.210s
2025-11-13 02:35:04.127 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:__exit__:86 - ✓ Instagram 스크린샷 촬영 completed in 10.211s | keyword=이천데이트 index=1 duration=10.211s
2025-11-13 02:35:04.128 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:async_wrapper:31 - ← viral_marketing_reporter.infrastructure.platforms.instagram.page_objects.InstagramSearchPage.take_screenshot_of_results completed in 10.214s

2025-11-13 02:35:04.129 | DEBUG    | viral_marketing_reporter.infrastructure.logging_utils:checkpoint:117 - Checkpoint 'screenshot_taken' reached | tracker=instagram_search_이천데이트 elapsed=12.428s
2025-11-13 02:35:04.130 | INFO     | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:182 - 스크린샷 촬영 완료 | keyword=이천데이트 screenshot_path=/Users/yeonuk/Downloads/viral-reporter/instagram/test/1_이천데이트.png event_name=screenshot_completed platform=instagram

2025-11-13 02:35:04.131 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:end:132 - Performance metrics for instagram_search_이천데이트 | page_loaded=1.757s top_9_posts_retrieved=1.867s posts_matched=2.089s posts_highlighted=2.211s screenshot_taken=12.428s total=12.430s
2025-11-13 02:35:04.234 | DEBUG    | viral_marketing_reporter.infrastructure.platforms.instagram.service:search_and_find_posts:205 - Instagram 페이지 정리 | keyword=이천데이트 event_name=page_cleanup platform=instagram
2025-11-13 02:35:04.235 | INFO     | viral_marketing_reporter.infrastructure.logging_utils:__exit__:86 - ✓ Instagram 검색 및 포스트 매칭 completed in 12.534s | keyword=이천데이트 index=1 posts_to_find_count=2 duration=12.534s platform=instagram
```

---

## 요약

Viral Marketing Reporter의 로깅 시스템은 다음과 같은 이점을 제공합니다:

1. **완전한 추적성**: 모든 작업의 시작부터 종료까지 상세하게 기록
2. **성능 분석**: 각 단계별 실행 시간 측정으로 병목 지점 파악
3. **디버깅 용이성**: 이벤트 기반 로깅으로 문제 발생 지점 즉시 식별
4. **구조화된 데이터**: JSON 직렬화로 프로그래밍 방식의 로그 분석 가능
5. **플랫폼 독립적**: Instagram, Naver Blog 등 모든 플랫폼에 동일한 로깅 적용

로그를 통해 애플리케이션의 동작을 완벽하게 이해하고, 문제 발생 시 빠르게 원인을 파악하여 해결할 수 있습니다.
