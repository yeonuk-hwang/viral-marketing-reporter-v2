from __future__ import annotations

import uuid
from collections import defaultdict, deque
from typing import override

import pytest
from pytest_mock import MockerFixture

from viral_marketing_reporter import bootstrap
from viral_marketing_reporter.application.commands import (
    Command,
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
    TaskDTO,
)
from viral_marketing_reporter.domain.events import (
    Event,
    JobCompleted,
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)
from viral_marketing_reporter.domain.message_bus import Handler, MessageBus
from viral_marketing_reporter.domain.model import (
    JobStatus,
    Platform,
    SearchJob,
    SearchResult,
)
from viral_marketing_reporter.infrastructure.message_bus import InMemoryMessageBus
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)
from viral_marketing_reporter.infrastructure.uow import InMemoryUnitOfWork


class FakeQueueMessageBus(MessageBus):
    def __init__(self):
        self.queue = deque()
        self._command_handlers: dict[type[Command], Handler] = {}
        self._event_handlers: defaultdict[type[Event], list[Handler]] = defaultdict(
            list
        )

    def register_command(self, command, handler):
        self._command_handlers[command] = handler

    def subscribe_to_event(self, event, handler):
        self._event_handlers[event].append(handler)

    async def handle(self, message):
        self.queue.append(message)

    async def run_once(self):
        if not self.queue:
            return
        message = self.queue.popleft()
        if type(message) in self._command_handlers:
            await self._command_handlers[type(message)].handle(message)
        elif type(message) in self._event_handlers:
            for handler in self._event_handlers[type(message)]:
                await handler.handle(message)
        else:
            raise ValueError(f"No handler for {type(message)}")


# Integration Test


@pytest.mark.asyncio
async def test_full_process_manager_flow(mocker: MockerFixture):
    # Arrange
    bus = FakeQueueMessageBus()
    uow = InMemoryUnitOfWork(bus)

    factory = mocker.AsyncMock(spec=PlatformServiceFactory)
    fake_service = mocker.AsyncMock(spec=SearchPlatformService)
    fake_service.search_and_find_posts.return_value = SearchResult(
        found_posts=[], screenshot=None
    )
    factory.get_service.return_value = fake_service

    bootstrap.bootstrap(uow=uow, bus=bus, factory=factory)

    # Act & Assert
    job_id = uuid.uuid4()
    await bus.handle(
        CreateSearchCommand(
            job_id=job_id,
            tasks=[TaskDTO(keyword="k1", urls=[], platform=Platform.NAVER_BLOG)],
        )
    )

    # 1. CreateSearchCommandHandler
    await bus.run_once()
    assert len(bus.queue) == 1
    assert isinstance(bus.queue[0], SearchJobCreated)

    # 2. SearchJobCreatedHandler
    await bus.run_once()
    assert len(bus.queue) == 1
    assert isinstance(bus.queue[0], SearchJobStarted)

    # 3. SearchJobStartedHandler
    await bus.run_once()
    assert len(bus.queue) == 1
    assert isinstance(bus.queue[0], ExecuteSearchTaskCommand)

    # 4. ExecuteSearchTaskCommandHandler
    await bus.run_once()
    assert len(bus.queue) == 1
    assert isinstance(bus.queue[0], TaskCompleted)

    # 5. TaskCompletedHandler
    await bus.run_once()
    assert len(bus.queue) == 1
    assert isinstance(bus.queue[0], JobCompleted)

    # 6. Final state check
    saved_job = await uow.search_jobs.get(job_id)
    assert saved_job is not None
    assert saved_job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_full_process_manager_flow_with_in_memory_bus(mocker: MockerFixture):
    # Arrange
    bus = InMemoryMessageBus()
    uow = InMemoryUnitOfWork(bus)

    factory = mocker.AsyncMock(spec=PlatformServiceFactory)
    fake_service = mocker.AsyncMock(spec=SearchPlatformService)
    fake_service.search_and_find_posts.return_value = SearchResult(
        found_posts=[], screenshot=None
    )
    factory.get_service.return_value = fake_service

    bootstrap.bootstrap(uow=uow, bus=bus, factory=factory)

    # Act & Assert
    job_id = uuid.uuid4()
    await bus.handle(
        CreateSearchCommand(
            job_id=job_id,
            tasks=[TaskDTO(keyword="k1", urls=[], platform=Platform.NAVER_BLOG)],
        )
    )

    # 6. Final state check
    saved_job = await uow.search_jobs.get(job_id)
    assert saved_job is not None
    assert saved_job.status == JobStatus.COMPLETED

