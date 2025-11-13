import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page


class InstagramAuthManager:
    """Instagram 로그인 세션을 관리합니다.

    - 로그인 세션을 파일로 저장/로드
    - 세션 유효성 검증
    - 필요 시 headful 브라우저로 로그인 창 표시
    """

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = (
                Path.home() / "Downloads" / "viral-reporter" / "instagram_session.json"
            )
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def has_saved_session(self) -> bool:
        """저장된 로그인 세션이 있는지 확인합니다."""
        return self.storage_path.exists()

    async def is_session_valid(self, context: BrowserContext) -> bool:
        """현재 세션이 유효한지 Instagram 페이지에 접속해서 확인합니다."""
        try:
            import re

            page = await context.new_page()
            await page.goto("https://www.instagram.com/", timeout=30000)

            # 로그인되어 있으면 Profile 텍스트가 있음
            try:
                await page.get_by_text(re.compile("profile", re.IGNORECASE)).wait_for(
                    timeout=10000, state="visible"
                )
                await page.close()
                return True
            except Exception:
                await page.close()
                return False

        except Exception as e:
            logger.warning(f"세션 유효성 검증 중 오류: {e}")
            return False

    async def show_login_dialog(self) -> bool:
        """별도의 headful 브라우저를 열어 사용자가 Instagram에 로그인하도록 합니다.

        Returns:
            로그인 성공 여부
        """
        logger.info("Instagram 로그인 창을 엽니다...")

        # 별도의 headful Playwright 인스턴스 생성
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            # headful 브라우저 실행
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1080}
            )

            # 저장된 세션이 있으면 먼저 로드 시도
            if self.has_saved_session():
                try:
                    storage_state = self._load_storage_state()
                    await context.add_cookies(storage_state["cookies"])
                    logger.info("기존 세션을 로드했습니다.")
                except Exception as e:
                    logger.warning(f"기존 세션 로드 실패: {e}")

            page = await context.new_page()
            await page.goto("https://www.instagram.com/accounts/login/", timeout=30000)

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
                logger.info(f"로그인 세션을 저장했습니다: {self.storage_path}")
            else:
                logger.warning("로그인이 완료되지 않았습니다.")

            await browser.close()
            logger.info("브라우저를 닫았습니다.")

        return success

    async def _wait_for_login_completion(self, page: Page, timeout: int = 300) -> bool:
        """로그인 완료를 감지합니다.

        로그인 후 URL이 변경되고 "Profile" 텍스트가 나타나는지 확인합니다.
        타임아웃: 5분 (300초)
        """
        try:
            logger.info("로그인 완료 대기 중... (최대 5분)")

            # 1단계: 로그인 페이지에서 벗어날 때까지 대기
            await page.wait_for_url(
                lambda url: "/accounts/login" not in url,
                timeout=timeout * 1000,
            )
            logger.info("로그인 페이지를 벗어났습니다.")

            # 2단계: "Profile" 또는 프로필 관련 텍스트가 나타날 때까지 대기
            import re

            try:
                # Profile, Home, Search 등 로그인 후 나타나는 텍스트 찾기
                await page.get_by_text(re.compile("profile", re.IGNORECASE)).wait_for(
                    timeout=30000, state="visible"
                )
                logger.info("프로필 요소 감지 - 로그인 성공!")
            except Exception as e:
                logger.warning(
                    f"프로필 텍스트를 찾지 못했지만 로그인 페이지는 벗어났습니다: {e}"
                )

            # 4단계: 팝업 자동 닫기 (선택사항)
            await self._dismiss_popups(page)

            return True

        except Exception as e:
            logger.error(f"로그인 완료 대기 중 오류: {e}")
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

    async def get_authenticated_context(self, browser: Browser) -> BrowserContext:
        """인증된 브라우저 컨텍스트를 반환합니다.

        저장된 세션이 있으면 로드하고, 없거나 만료되었으면 로그인 다이얼로그를 표시합니다.

        Args:
            browser: Playwright 브라우저 인스턴스 (headless)

        Returns:
            인증된 BrowserContext
        """
        # 컨텍스트 생성 옵션
        context_options = {"viewport": {"width": 1280, "height": 1080}}

        # 저장된 세션이 있으면 로드
        if self.has_saved_session():
            context_options["storage_state"] = str(self.storage_path)
            logger.info("저장된 Instagram 세션을 로드합니다.")

            # 세션으로 컨텍스트 생성
            context = await browser.new_context(**context_options)

            # 세션 유효성 검증
            if await self.is_session_valid(context):
                logger.info("Instagram 인증된 컨텍스트를 사용합니다.")
                return context
            else:
                logger.warning("저장된 세션이 만료되었습니다. 다시 로그인해주세요.")
                await context.close()

        # 세션이 없거나 만료된 경우: 로그인 다이얼로그 표시
        logger.info("Instagram 로그인이 필요합니다.")
        login_success = await self.show_login_dialog()

        if not login_success:
            raise Exception("Instagram 로그인에 실패했습니다.")

        # 새로운 세션으로 컨텍스트 재생성
        context_options["storage_state"] = str(self.storage_path)
        context = await browser.new_context(**context_options)

        logger.info("Instagram 인증된 컨텍스트를 사용합니다.")
        return context

    def clear_session(self) -> None:
        """저장된 세션을 삭제합니다."""
        if self.storage_path.exists():
            self.storage_path.unlink()
            logger.info("Instagram 세션을 삭제했습니다.")
