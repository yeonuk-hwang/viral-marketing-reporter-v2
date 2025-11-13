"""Instagram 인증 서비스"""

from loguru import logger
from playwright.async_api import Browser, BrowserContext

from viral_marketing_reporter.infrastructure.platforms.authentication import (
    PlatformAuthenticationService,
)
from viral_marketing_reporter.infrastructure.platforms.instagram.auth_manager import (
    InstagramAuthManager,
)


class InstagramAuthenticationService(PlatformAuthenticationService):
    """Instagram 플랫폼의 인증을 담당하는 서비스"""

    def __init__(self, browser: Browser):
        """
        Args:
            browser: Playwright 브라우저 인스턴스
        """
        self.browser = browser
        self.auth_manager = InstagramAuthManager()
        self._context: BrowserContext | None = None

    async def authenticate(self) -> BrowserContext:
        """Instagram 인증을 수행하고 인증된 BrowserContext를 반환합니다.

        이미 인증된 경우 캐시된 Context를 반환합니다.

        Returns:
            인증된 BrowserContext
        """
        if self._context is None:
            logger.info("Instagram 인증을 시작합니다...")
            self._context = await self.auth_manager.get_authenticated_context(
                self.browser
            )
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
