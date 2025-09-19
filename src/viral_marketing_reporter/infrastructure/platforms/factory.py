from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService


class PlatformServiceFactory:
    def __init__(self) -> None:
        self._services: dict[Platform, SearchPlatformService] = {}

    def register_service(
        self, platform: Platform, service: SearchPlatformService
    ) -> None:
        """팩토리에 새로운 플랫폼 서비스를 등록합니다."""
        self._services[platform] = service

    def get_service(self, platform: Platform) -> SearchPlatformService:
        """등록된 플랫폼 서비스를 가져옵니다."""
        service = self._services.get(platform)
        if not service:
            raise ValueError(f"지원하지 않는 플랫폼입니다: {platform.name}")
        return service
