from typing import Type

from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.context import SearchExecutionContext
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService


class PlatformServiceFactory:
    def __init__(self, context: SearchExecutionContext) -> None:
        self._context: SearchExecutionContext = context
        self._service_classes: dict[Platform, Type[SearchPlatformService]] = {}

    def register_service(
        self, platform: Platform, service_class: Type[SearchPlatformService]
    ) -> None:
        """팩토리에 새로운 플랫폼 서비스 클래스를 등록합니다."""
        self._service_classes[platform] = service_class

    async def get_service(self, platform: Platform) -> SearchPlatformService:
        """컨텍스트를 이용해 페이지를 생성하고, 등록된 서비스 클래스를 인스턴스화하여 반환합니다."""
        service_class = self._service_classes.get(platform)
        if not service_class:
            raise ValueError(f"지원하지 않는 플랫폼입니다: {platform.name}")

        page = await self._context.new_page()
        return service_class(page=page)
