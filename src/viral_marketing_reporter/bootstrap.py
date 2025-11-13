from __future__ import annotations

from typing import TYPE_CHECKING

from viral_marketing_reporter.application import handlers
from viral_marketing_reporter.application.commands import (
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
)
from viral_marketing_reporter.domain.events import (
    JobCompleted,
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)

if TYPE_CHECKING:
    from viral_marketing_reporter.domain.message_bus import MessageBus
    from viral_marketing_reporter.domain.uow import UnitOfWork
    from viral_marketing_reporter.infrastructure.platforms.factory import (
        PlatformServiceFactory,
    )


def bootstrap(
    uow: UnitOfWork,
    bus: MessageBus,
    factory: PlatformServiceFactory,
) -> MessageBus:
    """메시지 버스에 커맨드와 이벤트 핸들러를 등록합니다."""
    # 커맨드 핸들러 등록
    bus.register_command(
        CreateSearchCommand,
        handlers.CreateSearchCommandHandler(uow=uow),
    )
    bus.register_command(
        ExecuteSearchTaskCommand,
        handlers.ExecuteSearchTaskCommandHandler(uow=uow, factory=factory),
    )

    # 이벤트 핸들러 등록
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

    return bus
