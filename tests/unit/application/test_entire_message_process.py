from __future__ import annotations
import uuid
from collections import deque, defaultdict
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
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.domain.uow import UnitOfWork
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)

# Fakes for Integration Test


class FakeQueueMessageBus(MessageBus):
    def __init__(self):
        self.queue = deque()
        self._command_handlers: dict[type[Command], Handler] = {}
        self._event_handlers: defaultdict[type[Event], list[Handler]] = defaultdict(list)

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


class FakeIntegrationUnitOfWork(UnitOfWork):
    def __init__(self, bus: FakeQueueMessageBus):
        self.search_jobs = InMemorySearchJobRepository()
        self.bus = bus

    async def __aenter__(self) -> FakeIntegrationUnitOfWork:
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, traceback):
        pass

    async def commit(self):
        for job in self.search_jobs._jobs.values():
            for event in job.pull_events():
                await self.bus.handle(event)
        self.committed = True

    async def rollback(self):
        pass


class InMemorySearchJobRepository(SearchJobRepository):
    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, SearchJob] = {}

    @override
    async def save(self, search_job: SearchJob) -> None:
        self._jobs[search_job.job_id] = search_job

    @override
    async def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        return self._jobs.get(search_job_id)


# Integration Test


@pytest.mark.asyncio
async def test_full_process_manager_flow(mocker: MockerFixture):
    # Arrange
    bus = FakeQueueMessageBus()
    uow = FakeIntegrationUnitOfWork(bus)

    factory = mocker.AsyncMock(spec=PlatformServiceFactory)
    fake_service = mocker.AsyncMock(spec=SearchPlatformService)
    fake_service.search_and_find_posts.return_value = SearchResult(found_posts=[], screenshot=None)
    factory.get_service.return_value = fake_service

    bootstrap.bootstrap(uow=uow, bus=bus, factory=factory)
    class DummyJobCompletedHandler(Handler):
        async def handle(self, event: JobCompleted) -> None: pass
    bus.subscribe_to_event(JobCompleted, DummyJobCompletedHandler())

    # Act & Assert
    job_id = uuid.uuid4()
    await bus.handle(CreateSearchCommand(job_id=job_id, tasks=[TaskDTO(keyword="k1", urls=[], platform=Platform.NAVER_BLOG)]))

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