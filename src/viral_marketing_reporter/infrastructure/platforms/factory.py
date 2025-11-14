from typing import Type

from loguru import logger
from playwright.async_api import BrowserContext

from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.context import ApplicationContext
from viral_marketing_reporter.infrastructure.logging_utils import (
    log_function_call,
    log_step,
    PerformanceTracker,
)
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
        self._created_contexts: list[BrowserContext] = []  # Factory가 생성한 context들 추적

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
        tracker = PerformanceTracker("prepare_platforms")
        tracker.start()

        with log_step(
            "플랫폼 사전 준비",
            platforms=[p.value for p in platforms],
            platform_count=len(platforms),
        ):
            for platform in platforms:
                if platform in self._auth_services:
                    auth_service = self._auth_services[platform]
                    if not auth_service.is_authenticated():
                        logger.info(
                            f"{platform.value} 인증 시작",
                            platform=platform.value,
                            event_name="auth_start",
                        )
                        await auth_service.authenticate()
                        tracker.checkpoint(f"{platform.value}_authenticated")
                    else:
                        logger.debug(
                            f"{platform.value} 이미 인증됨",
                            platform=platform.value,
                            event_name="auth_skip",
                        )
                else:
                    logger.debug(
                        f"{platform.value} 인증 불필요",
                        platform=platform.value,
                        event_name="auth_not_required",
                    )

        tracker.end()

    async def get_service(self, platform: Platform) -> SearchPlatformService:
        """컨텍스트를 이용해 페이지를 생성하고, 등록된 서비스 클래스를 인스턴스화하여 반환합니다.

        Args:
            platform: 서비스를 가져올 플랫폼

        Returns:
            플랫폼에 해당하는 SearchPlatformService 인스턴스

        Raises:
            ValueError: 등록되지 않은 플랫폼인 경우
        """
        logger.debug(
            f"플랫폼 서비스 생성 시작",
            platform=platform.value,
            event_name="service_creation_start",
        )

        service_class = self._service_classes.get(platform)
        if not service_class:
            logger.error(
                f"지원하지 않는 플랫폼",
                platform=platform.name,
                event_name="unsupported_platform",
            )
            raise ValueError(f"지원하지 않는 플랫폼입니다: {platform.name}")

        # 인증 서비스가 등록된 플랫폼인 경우
        if platform in self._auth_services:
            logger.debug(
                f"인증된 컨텍스트 사용",
                platform=platform.value,
                event_name="using_authenticated_context",
            )
            auth_service = self._auth_services[platform]
            context = await auth_service.authenticate()
            page = await context.new_page()
        else:
            # 인증이 필요 없는 플랫폼은 Factory가 직접 context 생성
            logger.debug(
                f"새 컨텍스트 생성",
                platform=platform.value,
                event_name="creating_new_context",
            )
            context = await self._context.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-GB",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            self._created_contexts.append(context)
            page = await context.new_page()

        logger.info(
            f"플랫폼 서비스 생성 완료",
            platform=platform.value,
            service_class=service_class.__name__,
            event_name="service_created",
        )
        return service_class(page=page)

    async def cleanup(self) -> None:
        """팩토리가 관리하는 모든 리소스를 정리합니다."""
        with log_step(
            "팩토리 리소스 정리",
            auth_service_count=len(self._auth_services),
            created_context_count=len(self._created_contexts),
        ):
            # Factory가 생성한 context들 닫기
            for idx, context in enumerate(self._created_contexts):
                try:
                    logger.debug(
                        f"Factory 생성 컨텍스트 정리 중",
                        context_index=idx,
                        event_name="context_cleanup_start",
                    )
                    await context.close()
                    logger.debug(
                        f"Factory 생성 컨텍스트 정리 완료",
                        context_index=idx,
                        event_name="context_cleanup_success",
                    )
                except Exception as e:
                    logger.warning(
                        f"Factory 생성 컨텍스트 정리 중 오류",
                        context_index=idx,
                        error=str(e),
                        error_type=e.__class__.__name__,
                        event_name="context_cleanup_error",
                    )
            self._created_contexts.clear()

            # 인증 서비스 정리
            for platform, auth_service in self._auth_services.items():
                try:
                    logger.debug(
                        f"{platform.value} 인증 서비스 정리 시작",
                        platform=platform.value,
                        event_name="cleanup_start",
                    )
                    await auth_service.cleanup()
                    logger.debug(
                        f"{platform.value} 인증 서비스 정리 완료",
                        platform=platform.value,
                        event_name="cleanup_success",
                    )
                except Exception as e:
                    logger.warning(
                        f"{platform.value} 인증 서비스 정리 중 오류",
                        platform=platform.value,
                        error=str(e),
                        error_type=e.__class__.__name__,
                        event_name="cleanup_error",
                    )
