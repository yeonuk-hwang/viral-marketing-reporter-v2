"""Instagram 인증 서비스"""

import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page

from viral_marketing_reporter.infrastructure.logging_utils import (
    PerformanceTracker,
    log_function_call,
    log_step,
)
from viral_marketing_reporter.infrastructure.context import require_google_chrome
from viral_marketing_reporter.infrastructure.platforms.authentication import (
    PlatformAuthenticationService,
)


class InstagramAuthService(PlatformAuthenticationService):
    """Instagram 로그인 세션을 관리하고 인증을 제공합니다.

    - 로그인 세션을 파일로 저장/로드
    - 세션 유효성 검증
    - 필요 시 headful 브라우저로 로그인 창 표시
    - BrowserContext 캐싱 및 재사용
    """

    AUTHENTICATED_UI_SELECTOR = 'svg[aria-label="New post"]'

    def __init__(self, browser: Browser, storage_path: Path | None = None):
        """
        Args:
            browser: Playwright 브라우저 인스턴스 (headless)
            storage_path: 세션 저장 경로 (기본값: ~/Downloads/viral-reporter/instagram_session.json)
        """
        self.browser = browser

        if storage_path is None:
            storage_path = (
                Path.home() / "Downloads" / "viral-reporter" / "instagram_session.json"
            )
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._context: BrowserContext | None = None  # 인증된 Context 캐싱

    # PlatformAuthenticationService 인터페이스 구현

    async def authenticate(self) -> BrowserContext:
        """Instagram 인증을 수행하고 인증된 BrowserContext를 반환합니다.

        이미 인증된 경우 캐시된 Context를 반환합니다.

        Returns:
            인증된 BrowserContext

        Raises:
            Exception: 로그인 실패 시
        """
        if self._context is None:
            logger.info("Instagram 인증을 시작합니다...")
            self._context = await self._get_authenticated_context()
            logger.info("Instagram 인증이 완료되었습니다.")
        else:
            logger.debug("캐시된 Instagram Context를 재사용합니다.")

        return self._context

    def is_authenticated(self) -> bool:
        """현재 인증 상태를 반환합니다.

        Returns:
            인증된 Context가 있으면 True, 아니면 False
        """
        return self._context is not None

    async def cleanup(self) -> None:
        """Instagram 인증 Context를 정리합니다."""
        if self._context:
            await self._context.close()
            self._context = None
            logger.info("Instagram 인증 Context를 정리했습니다.")

    # Instagram 전용 메서드들

    def has_saved_session(self) -> bool:
        """저장된 로그인 세션이 있는지 확인합니다."""
        return self.storage_path.exists()

    @log_function_call
    async def _get_authenticated_context(self) -> BrowserContext:
        """인증된 브라우저 컨텍스트를 반환합니다.

        저장된 세션이 있으면 로드하고, 없거나 만료되었으면 로그인 다이얼로그를 표시합니다.

        Returns:
            인증된 BrowserContext

        Raises:
            Exception: 로그인 실패 시
        """
        tracker = PerformanceTracker("instagram_authentication")
        tracker.start()

        # 컨텍스트 생성 옵션
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-GB",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        # 저장된 세션이 있으면 로드
        if self.has_saved_session():
            context_options["storage_state"] = str(self.storage_path)
            logger.info(
                "저장된 Instagram 세션 로드",
                storage_path=str(self.storage_path),
                event_name="session_load",
            )

            # 세션으로 컨텍스트 생성
            context = await self.browser.new_context(**context_options)
            tracker.checkpoint("context_created_with_session")

            # 세션 유효성 검증
            if await self._is_session_valid(context):
                logger.info(
                    "Instagram 인증된 컨텍스트 사용",
                    event_name="authenticated_context_ready",
                )
                tracker.checkpoint("session_validated")
                tracker.end()
                return context
            else:
                logger.warning(
                    "세션 만료",
                    storage_path=str(self.storage_path),
                    event_name="session_expired",
                )
                await context.close()
                tracker.checkpoint("session_invalid_closed")

        # 세션이 없거나 만료된 경우: 로그인 다이얼로그 표시
        logger.info("Instagram 로그인 필요", event_name="login_required")
        login_success = await self._show_login_dialog()
        tracker.checkpoint("login_dialog_completed")

        if not login_success:
            logger.error("Instagram 로그인 실패", event_name="login_failed")
            tracker.end()
            raise Exception("Instagram 로그인에 실패했습니다.")

        # 새로운 세션으로 컨텍스트 재생성
        context_options["storage_state"] = str(self.storage_path)
        context = await self.browser.new_context(**context_options)
        tracker.checkpoint("context_created_with_new_session")

        logger.info(
            "Instagram 인증된 컨텍스트 준비 완료",
            event_name="authenticated_context_ready",
        )
        tracker.end()
        return context

    @log_function_call
    async def _is_session_valid(self, context: BrowserContext) -> bool:
        """현재 세션이 유효한지 Instagram 페이지에 접속해서 확인합니다."""
        with log_step("Instagram 세션 유효성 검증"):
            page: Page | None = None
            try:
                page = await context.new_page()
                logger.debug(
                    "Instagram 홈페이지로 이동하여 세션 검증 시작",
                    event_name="session_validation_start",
                )
                await page.goto("https://www.instagram.com/", timeout=30000)

                await self._wait_for_authenticated_ui(page, timeout_ms=10_000)

                # Instagram이 검증 요청 중 갱신한 쿠키도 다음 실행에 유지합니다.
                await context.storage_state(path=str(self.storage_path))
                logger.info(
                    "세션 유효성 검증 성공 - 인증 UI 확인됨",
                    event_name="session_valid",
                )
                return True

            except Exception as e:
                logger.warning(
                    "세션 유효성 검증 실패 - 인증 UI 미발견",
                    error=str(e),
                    error_type=e.__class__.__name__,
                    event_name="session_invalid",
                )
                return False
            finally:
                if page and not page.is_closed():
                    await page.close()

    async def _wait_for_authenticated_ui(
        self, page: Page, timeout_ms: int
    ) -> None:
        """로그인 사용자에게만 표시되는 UI가 나타날 때까지 기다립니다."""
        await page.locator(self.AUTHENTICATED_UI_SELECTOR).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )

    @log_function_call
    async def _show_login_dialog(self) -> bool:
        """별도의 headful 브라우저를 열어 사용자가 Instagram에 로그인하도록 합니다.

        Returns:
            로그인 성공 여부
        """
        with log_step("Instagram 로그인 다이얼로그 표시"):
            logger.info(
                "Headful 브라우저로 로그인 창 열기",
                event_name="login_dialog_open",
            )

            # 별도의 headful Playwright 인스턴스 생성
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                # headful 브라우저 실행 (자동화 감지 우회)
                browser = await playwright.chromium.launch(
                    headless=False,
                    executable_path=require_google_chrome(),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                    ],
                )
                context = await browser.new_context(
                    # 로그인 창은 실제 Chrome 창 크기를 따르고 Playwright viewport를 강제하지 않습니다.
                    no_viewport=True,
                    locale="en-GB",
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                logger.debug(
                    "Headful 브라우저 컨텍스트 생성 완료",
                    event_name="headful_context_created",
                )

                # 저장된 세션이 있으면 먼저 로드 시도
                if self.has_saved_session():
                    try:
                        storage_state = self._load_storage_state()
                        await context.add_cookies(storage_state["cookies"])
                        logger.info(
                            "기존 세션 쿠키 로드 완료",
                            event_name="existing_cookies_loaded",
                        )
                    except Exception as e:
                        logger.warning(
                            "기존 세션 로드 실패",
                            error=str(e),
                            error_type=e.__class__.__name__,
                            event_name="existing_cookies_load_failed",
                        )

                page = await context.new_page()
                # 메인 페이지로 이동 (/accounts/login/은 429로 차단될 수 있음)
                await page.goto("https://www.instagram.com/", timeout=30000)
                logger.debug(
                    "Instagram 로그인 페이지 이동 완료",
                    event_name="login_page_loaded",
                )

                logger.info("=" * 60)
                logger.info("브라우저에서 Instagram에 로그인해주세요.")
                logger.info("로그인이 완료되면 자동으로 감지하여 진행합니다.")
                logger.info("=" * 60)

                # 로그인 완료 대기 (프로필 요소 감지)
                success = await self._wait_for_login_completion(page)

                if success:
                    # 세션 저장
                    storage_state = await context.storage_state()
                    self._save_storage_state(storage_state)
                    logger.info(
                        "로그인 세션 저장 완료",
                        storage_path=str(self.storage_path),
                        event_name="session_saved",
                    )
                else:
                    logger.warning(
                        "로그인 완료되지 않음",
                        event_name="login_incomplete",
                    )

                await browser.close()
                logger.info(
                    "Headful 브라우저 닫기 완료",
                    event_name="headful_browser_closed",
                )

            return success

    @log_function_call
    async def _wait_for_login_completion(
        self,
        page: Page,
        timeout: int = 300,
    ) -> bool:
        """New post 아이콘 표시 여부로 로그인 완료를 감지합니다."""

        with log_step("로그인 완료 대기", timeout_seconds=timeout):
            try:
                logger.info(
                    "로그인 완료 대기 시작",
                    timeout=timeout,
                    event_name="login_wait_start",
                )

                await self._wait_for_authenticated_ui(
                    page,
                    timeout_ms=timeout * 1000,
                )

                logger.info(
                    "New post 아이콘 감지 - 로그인 성공",
                    event_name="new_post_icon_detected",
                )

                await self._dismiss_popups(page)

                logger.info(
                    "로그인 완료 감지 성공",
                    event_name="login_completed",
                )
                return True

            except Exception as e:
                logger.warning(
                    "New post 아이콘 미발견 - 로그인 미완료",
                    error=str(e),
                    error_type=e.__class__.__name__,
                    event_name="new_post_icon_not_found",
                )
                return False

    async def _dismiss_popups(self, page: Page) -> None:
        """로그인 후 나타나는 팝업을 자동으로 닫습니다."""
        # "Save login info" 팝업
        try:
            not_now = page.get_by_role("button", name="Not now")
            if await not_now.is_visible(timeout=2000):
                await not_now.click()
                logger.info("'Save login info' 팝업 닫음")
                await asyncio.sleep(1)
        except Exception:
            pass

        # "Turn on notifications" 팝업
        try:
            not_now = page.get_by_role("button", name="Not Now")
            if await not_now.is_visible(timeout=2000):
                await not_now.click()
                logger.info("'Turn on notifications' 팝업 닫음")
                await asyncio.sleep(1)
        except Exception:
            pass

    def _load_storage_state(self) -> dict:
        """저장된 세션을 로드합니다."""
        import json

        with open(self.storage_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_storage_state(self, state: dict) -> None:
        """세션을 파일로 저장합니다."""
        import json

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def clear_session(self) -> None:
        """저장된 세션을 삭제합니다."""
        if self.storage_path.exists():
            self.storage_path.unlink()
            logger.info("Instagram 세션을 삭제했습니다.")
