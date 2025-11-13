"""플랫폼 인증 서비스 추상화"""

from abc import ABC, abstractmethod

from playwright.async_api import Browser, BrowserContext


class PlatformAuthenticationService(ABC):
    """플랫폼별 인증을 담당하는 서비스의 추상 클래스"""

    @abstractmethod
    async def authenticate(self) -> BrowserContext:
        """플랫폼 인증을 수행하고 인증된 BrowserContext를 반환합니다.

        Returns:
            인증된 BrowserContext
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """현재 인증 상태를 반환합니다.

        Returns:
            인증되어 있으면 True, 아니면 False
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """인증 서비스가 소유한 리소스를 정리합니다."""
        pass
