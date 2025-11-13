from typing import Type

from loguru import logger

from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.context import ApplicationContext
from viral_marketing_reporter.infrastructure.platforms.authentication import (
    PlatformAuthenticationService,
)
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService


class PlatformServiceFactory:
    """플랫폼 서비스와 인증 서비스를 관리하는 팩토리"""

    def __init__(self, context: ApplicationContext) -> None:
        self._context: ApplicationContext = context
        self._service_classes: dict[Platform, Type[SearchPlatformService]] = {}
        self._auth_services: dict[Platform, PlatformAuthenticationService] = {}

    def register_service(
        self, platform: Platform, service_class: Type[SearchPlatformService]
    ) -> None:
        """팩토리에 새로운 플랫폼 서비스 클래스를 등록합니다."""
        self._service_classes[platform] = service_class
        logger.debug(f"{platform.value} 서비스 클래스 등록 완료")

    def register_auth_service(
        self, platform: Platform, auth_service: PlatformAuthenticationService
    ) -> None:
        """팩토리에 플랫폼별 인증 서비스를 등록합니다."""
        self._auth_services[platform] = auth_service
        logger.debug(f"{platform.value} 인증 서비스 등록 완료")

    async def prepare_platforms(self, platforms: set[Platform]) -> None:
        """Job 시작 전에 필요한 플랫폼들의 인증을 사전 준비합니다.

        Args:
            platforms: 준비할 플랫폼들의 집합
        """
        logger.info(f"플랫폼 사전 준비 시작: {[p.value for p in platforms]}")

        for platform in platforms:
            if platform in self._auth_services:
                auth_service = self._auth_services[platform]
                if not auth_service.is_authenticated():
                    logger.info(f"{platform.value} 인증을 시작합니다...")
                    await auth_service.authenticate()
                else:
                    logger.debug(f"{platform.value}는 이미 인증되었습니다.")

        logger.info("플랫폼 사전 준비 완료")

    async def get_service(self, platform: Platform) -> SearchPlatformService:
        """컨텍스트를 이용해 페이지를 생성하고, 등록된 서비스 클래스를 인스턴스화하여 반환합니다.

        Args:
            platform: 서비스를 가져올 플랫폼

        Returns:
            플랫폼에 해당하는 SearchPlatformService 인스턴스

        Raises:
            ValueError: 등록되지 않은 플랫폼인 경우
        """
        service_class = self._service_classes.get(platform)
        if not service_class:
            raise ValueError(f"지원하지 않는 플랫폼입니다: {platform.name}")

        # 인증 서비스가 등록된 플랫폼인 경우
        if platform in self._auth_services:
            auth_service = self._auth_services[platform]
            context = await auth_service.authenticate()
            page = await context.new_page()
        else:
            # 인증이 필요 없는 플랫폼은 기본 컨텍스트 사용
            page = await self._context.new_page()

        return service_class(page=page)

    async def cleanup(self) -> None:
        """팩토리가 관리하는 모든 인증 서비스를 정리합니다."""
        logger.info("팩토리 리소스 정리 시작...")

        for platform, auth_service in self._auth_services.items():
            try:
                await auth_service.cleanup()
            except Exception as e:
                logger.warning(f"{platform.value} 인증 서비스 정리 중 오류: {e}")

        logger.info("팩토리 리소스 정리 완료")
