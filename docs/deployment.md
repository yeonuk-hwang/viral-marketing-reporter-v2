# Windows 배포 가이드

## 현재 배포 방식

이 프로젝트는 GitHub Actions와 PyInstaller를 사용하여 Windows용 portable ZIP을 배포한다.

```text
v* 태그 push
  → GitHub Actions windows-latest
  → Python 3.13 및 uv 설치
  → uv.lock 기준 의존성 설치
  → PyInstaller --onedir --windowed 빌드
  → 결과 폴더 ZIP 압축
  → GitHub Release 생성 및 ZIP 첨부
```

워크플로 파일은 `.github/workflows/release.yml`이다.

## 배포 결과물

릴리스 파일 이름은 다음 형식이다.

```text
ViralMarketingReporter-windows-v<버전>.zip
```

ZIP 내부에는 PyInstaller의 `onedir` 결과인 `viral-marketing-reporter` 폴더가 들어 있다. 사용자는 ZIP 전체를 압축 해제한 뒤 폴더 안의 실행 파일을 실행해야 한다.

현재 배포물은 다음 형태가 아니다.

- Windows 설치 프로그램(MSI 또는 setup.exe)
- 단일 실행 파일(`onefile`)
- Microsoft Store 패키지
- 자동 업데이트 지원 패키지

`onedir`를 사용하는 이유는 GUI 및 Playwright 관련 라이브러리를 단일 파일로 매번 임시 해제하는 비용을 피하고 시작 및 문제 진단을 단순하게 유지하기 위해서다.

## 사용자 PC 요구사항

### 운영체제

- Windows 10 또는 Windows 11 권장
- 64비트 환경 기준

### Google Chrome

Instagram 릴스의 H.264 영상을 정상적으로 디코딩하기 위해 Google Chrome 설치가 필수다.

Playwright 번들 Chromium은 릴리스에 설치하거나 포함하지 않는다. 앱 시작 시 다음 Windows 기본 경로에서 Chrome을 찾는다.

```text
%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
%PROGRAMFILES%\Google\Chrome\Application\chrome.exe
%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe
```

Chrome을 찾지 못하면 앱은 설치 안내 메시지를 표시한다. 필요한 경우 `VIRAL_REPORTER_BROWSER_PATH` 환경 변수로 Chrome 실행 파일 경로를 명시할 수 있다.

Chrome 실행 파일만 사용하며 사용자의 일반 Chrome 프로필은 사용하지 않는다. Instagram 인증은 Playwright의 격리된 BrowserContext에서 동작한다.

## 사용자 데이터 위치

애플리케이션 데이터는 실행 파일 폴더가 아니라 사용자 Downloads 아래에 저장된다.

Windows 예시:

```text
C:\Users\<사용자>\Downloads\viral-reporter\
```

주요 파일과 폴더:

```text
instagram_session.json      Instagram 앱 전용 로그인 세션
debug.log                   애플리케이션 로그
instagram\<작업 ID>\       Instagram 스크린샷
```

새 버전 ZIP으로 교체해도 위 세션 파일은 그대로 남으므로 유효한 로그인 세션을 재사용할 수 있다. 사용자의 기존 Chrome 프로필 및 쿠키와는 분리된다.

## 릴리스 절차

### 1. 변경 사항 검증

릴리스 전에 최소한 다음 검증을 수행한다.

```bash
uv sync --frozen
uv run pytest tests/unit/infrastructure -q
```

Instagram UI 또는 캡처 코드가 변경됐다면 실제 세션을 사용한 다음 진단도 수행한다.

```bash
uv run python scripts/diagnose_instagram_session.py
uv run python scripts/diagnose_instagram_video.py
```

진단 결과는 `.diagnostics/`에 생성되고 Git에는 포함되지 않는다.

### 2. 버전 변경

`pyproject.toml`의 프로젝트 버전을 다음 릴리스 버전으로 변경한다.

```toml
[project]
version = "2.3.1"
```

태그와 프로젝트 버전은 동일하게 유지하는 것을 권장한다.

```text
pyproject.toml: 2.3.1
Git tag:        v2.3.1
```

### 3. 릴리스 커밋 및 태그 생성

```bash
git add pyproject.toml
git commit -m "chore(release): prepare v2.3.1"
git tag -a v2.3.1 -m "Release v2.3.1"
```

### 4. 원격 저장소에 push

```bash
git push origin main
git push origin v2.3.1
```

`v*` 형식의 태그가 push되면 `Release Windows Executable` 워크플로가 자동 실행된다.

### 5. GitHub Actions 확인

GitHub 저장소의 Actions 화면에서 다음 단계가 성공했는지 확인한다.

1. Checkout code
2. Set up Python 3.13
3. Install uv
4. Install dependencies
5. Build with PyInstaller
6. Package application for release
7. Create GitHub Release

빌드 명령은 다음과 같다.

```text
uv run pyinstaller --noconfirm --onedir \
  --name viral-marketing-reporter \
  --windowed \
  ./src/viral_marketing_reporter/main.py
```

### 6. 릴리스 결과 확인

GitHub Releases에서 다음을 확인한다.

- 태그와 릴리스 버전이 일치하는지
- Windows ZIP이 첨부됐는지
- ZIP을 새 폴더에 압축 해제할 수 있는지
- 실행 파일이 정상 시작되는지
- Chrome 미설치 안내가 정상 표시되는지
- Instagram 저장 세션 또는 신규 로그인 흐름이 정상인지
- 이미지와 릴스가 포함된 상위 10개 스크린샷이 정상인지

## 수동 실행

워크플로에는 `workflow_dispatch`도 설정되어 있어 GitHub Actions 화면에서 수동 실행할 수 있다. GitHub Release를 생성하려면 브랜치가 아니라 릴리스할 `v*` 태그를 실행 기준 ref로 선택하는 것이 안전하다. 정식 배포는 태그 push 방식을 권장한다.

## PyInstaller spec 파일과 실제 Windows 빌드

저장소 루트의 `ViralMarketingReporter.spec`도 PyInstaller 설정을 담고 있지만 현재 GitHub Actions Windows 릴리스는 이 spec 파일을 사용하지 않는다. 워크플로에 직접 작성된 `pyinstaller --onedir` 명령이 실제 배포 기준이다.

spec 파일에는 macOS `BUNDLE` 설정도 포함되어 있으므로 Windows 릴리스 설정으로 오해하지 않아야 한다. 향후 아이콘, 데이터 파일, hidden import 또는 버전 리소스가 필요해지면 다음 중 하나로 설정을 통일해야 한다.

1. Windows 전용 spec 파일을 만들고 워크플로에서 해당 파일 사용
2. 현재처럼 워크플로 명령행 옵션을 단일 기준으로 유지

현재는 두 번째 방식이다.

## 현재 배포의 제한사항

### 코드 서명 없음

Windows 실행 파일에 Authenticode 서명이 적용되지 않는다. 다른 PC에서 처음 실행할 때 Windows SmartScreen 경고가 표시될 수 있다.

### 자동 업데이트 없음

새 버전이 나오면 사용자가 GitHub Release에서 새 ZIP을 내려받아 기존 프로그램 폴더를 교체해야 한다. Downloads 아래의 세션 및 결과 데이터는 프로그램 폴더와 분리되어 있으므로 유지된다.

### 설치 프로그램 없음

바탕화면 바로가기, 시작 메뉴 등록, 제거 프로그램 등록을 자동으로 처리하지 않는다.

### 릴리스 전 전체 자동 테스트 없음

현재 release 워크플로는 의존성 설치 후 바로 빌드한다. 테스트는 로컬에서 수행해야 한다. 안정성이 더 중요해지면 별도의 CI 워크플로를 추가하고 해당 검사가 통과한 태그만 릴리스하도록 보호 규칙을 설정하는 것이 좋다.

## 향후 개선 후보

- Windows Authenticode 코드 서명
- Inno Setup 또는 WiX 기반 설치 프로그램
- 애플리케이션 아이콘 및 Windows 버전 리소스
- 전체 테스트를 수행하는 별도 CI 워크플로
- 태그와 `pyproject.toml` 버전 일치 자동 검증
- SHA-256 체크섬 첨부
- 자동 업데이트 또는 새 버전 알림
