from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from viral_marketing_reporter.application import handlers
from viral_marketing_reporter.application.commands import (
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
)
from viral_marketing_reporter.application.handlers import GetJobResultQueryHandler
from viral_marketing_reporter.domain.events import (
    JobCompleted,
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)
from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.message_bus import InMemoryMessageBus
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)
from viral_marketing_reporter.infrastructure.platforms.instagram.auth_service import (
    InstagramAuthService,
)
from viral_marketing_reporter.infrastructure.platforms.instagram.service import (
    PlaywrightInstagramService,
)
from viral_marketing_reporter.infrastructure.platforms.naver_blog.service import (
    PlaywrightNaverBlogService,
)
from viral_marketing_reporter.infrastructure.uow import InMemoryUnitOfWork

if TYPE_CHECKING:
    from viral_marketing_reporter.domain.message_bus import MessageBus
    from viral_marketing_reporter.domain.uow import UnitOfWork
    from viral_marketing_reporter.infrastructure.context import ApplicationContext


class Application:
    """애플리케이션의 핵심 컴포넌트들을 관리하는 클래스"""

    def __init__(
        self,
        bus: MessageBus,
        uow: UnitOfWork,
        factory: PlatformServiceFactory,
        query_handler: GetJobResultQueryHandler,
    ):
        self.bus = bus
        self.uow = uow
        self.factory = factory
        self.query_handler = query_handler


def bootstrap(context: ApplicationContext) -> Application:
    """애플리케이션을 초기화하고 모든 컴포넌트를 설정합니다.

    Args:
        context: Playwright 브라우저 컨텍스트를 관리하는 ApplicationContext

    Returns:
        초기화된 Application 객체
    """
    logger.info("애플리케이션 bootstrap 시작")

    # 1. 메시지 버스 및 UnitOfWork 생성
    bus = InMemoryMessageBus()
    uow = InMemoryUnitOfWork(bus)
    logger.debug("MessageBus 및 UnitOfWork 생성 완료")

    # 2. 플랫폼 서비스 팩토리 생성 및 설정
    factory = PlatformServiceFactory(context)

    # 플랫폼 서비스 등록
    factory.register_service(Platform.NAVER_BLOG, PlaywrightNaverBlogService)
    factory.register_service(Platform.INSTAGRAM, PlaywrightInstagramService)
    logger.debug("플랫폼 서비스 등록 완료: NAVER_BLOG, INSTAGRAM")

    # 인증 서비스 등록 (인증이 필요한 플랫폼만)
    instagram_auth = InstagramAuthService(browser=context.browser)
    factory.register_auth_service(Platform.INSTAGRAM, instagram_auth)
    logger.debug("Instagram 인증 서비스 등록 완료")

    # 3. 커맨드 핸들러 등록
    bus.register_command(
        CreateSearchCommand,
        handlers.CreateSearchCommandHandler(uow=uow),
    )
    bus.register_command(
        ExecuteSearchTaskCommand,
        handlers.ExecuteSearchTaskCommandHandler(uow=uow, factory=factory),
    )
    logger.debug("커맨드 핸들러 등록 완료")

    # 4. 이벤트 핸들러 등록
    bus.subscribe_to_event(
        SearchJobCreated,
        handlers.SearchJobCreatedHandler(uow=uow, factory=factory),
    )
    bus.subscribe_to_event(
        SearchJobStarted,
        handlers.SearchJobStartedHandler(uow=uow, bus=bus),
    )
    bus.subscribe_to_event(
        TaskCompleted,
        handlers.TaskCompletedHandler(uow=uow),
    )
    bus.subscribe_to_event(JobCompleted, handlers.JobCompletedHandler(uow=uow))
    logger.debug("이벤트 핸들러 등록 완료")

    # 5. 쿼리 핸들러 생성
    query_handler = GetJobResultQueryHandler(uow=uow)
    logger.debug("쿼리 핸들러 생성 완료")

    logger.info("애플리케이션 bootstrap 완료")

    return Application(
        bus=bus,
        uow=uow,
        factory=factory,
        query_handler=query_handler,
    )
