# pyright: reportPrivateUsage=false
from __future__ import annotations

import uuid
from typing import override

import pytest
from pytest_mock import MockerFixture

from viral_marketing_reporter.application.commands import (
    Command,
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
    TaskDTO,
)
from viral_marketing_reporter.application.handlers import (
    CreateSearchCommandHandler,
    ExecuteSearchTaskCommandHandler,
    SearchJobCreatedHandler,
    SearchJobStartedHandler,
    TaskCompletedHandler,
)
from viral_marketing_reporter.domain.events import (
    Event,
    JobCompleted,
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)
from viral_marketing_reporter.domain.model import (
    JobStatus,
    Keyword,
    Platform,
    SearchJob,
    SearchResult,
    SearchTask,
    TaskStatus,
)
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.domain.uow import UnitOfWork
from viral_marketing_reporter.infrastructure import message_bus
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)

# Fakes


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.search_jobs: InMemorySearchJobRepository = InMemorySearchJobRepository()  # pyright: ignore[reportIncompatibleVariableOverride]
        self.committed: bool = False
        self.events: list[Event] = []

    @override
    async def __aenter__(self) -> FakeUnitOfWork:
        self.committed = False
        self.events.clear()
        return self

    @override
    async def __aexit__(self, exc_type, exc_val, traceback):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        pass

    @override
    async def commit(self):
        for job in self.search_jobs._jobs.values():
            self.events.extend(job.pull_events())
        self.committed = True

    @override
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


# Unit Tests


@pytest.mark.asyncio
async def test_create_search_command_handler_creates_job():
    uow = FakeUnitOfWork()
    handler = CreateSearchCommandHandler(uow=uow)
    job_id = uuid.uuid4()
    command = CreateSearchCommand(
        job_id=job_id,
        tasks=[TaskDTO(keyword="k1", urls=[], platform=Platform.NAVER_BLOG)]
    )

    await handler.handle(command)

    assert uow.committed is True
    saved_job = await uow.search_jobs.get(job_id)
    assert saved_job is not None
    assert len(uow.events) == 1
    assert isinstance(uow.events[0], SearchJobCreated)
    assert uow.events[0].job_id == job_id


@pytest.mark.asyncio
async def test_search_job_created_handler_starts_job():
    uow = FakeUnitOfWork()
    handler = SearchJobCreatedHandler(uow=uow)
    job_id = uuid.uuid4()
    job = SearchJob.create(job_id=job_id, tasks=[])
    await uow.search_jobs.save(job)
    await uow.commit()

    event = SearchJobCreated(job_id=job.job_id, created_at=job.created_at)
    await handler.handle(event)
    assert uow.committed is True

    saved_job = await uow.search_jobs.get(job.job_id)

    assert saved_job is not None
    assert saved_job.status == JobStatus.RUNNING
    assert len(uow.events) == 1
    assert isinstance(uow.events[0], SearchJobStarted)


@pytest.mark.asyncio
async def test_search_job_started_handler_dispatches_commands(mocker: MockerFixture):
    uow = FakeUnitOfWork()
    bus = message_bus.InMemoryMessageBus()
    spy_handle = mocker.spy(bus, "handle")
    handler = SearchJobStartedHandler(uow=uow, bus=bus)

    # Register a dummy handler to prevent KeyError
    class DummyExecuteTaskHandler:
        async def handle(self, cmd: Command):
            pass

    bus.register_command(ExecuteSearchTaskCommand, DummyExecuteTaskHandler())  # pyright: ignore[reportUnknownMemberType]

    task = SearchTask(
        keyword=Keyword(text="k1"), blog_posts_to_find=[], platform=Platform.NAVER_BLOG
    )
    job = SearchJob(tasks=[task])
    await uow.search_jobs.save(job)

    event = SearchJobStarted(job_id=job.job_id)
    await handler.handle(event)

    assert spy_handle.call_count == 1
    dispatched_command = spy_handle.call_args.args[0]  # pyright: ignore[reportAny]
    assert isinstance(dispatched_command, ExecuteSearchTaskCommand)
    assert dispatched_command.job_id == job.job_id
    assert dispatched_command.task_id == task.task_id


@pytest.mark.asyncio
async def test_execute_search_task_handler_updates_job(mocker: MockerFixture):
    uow = FakeUnitOfWork()
    factory = mocker.AsyncMock(spec=PlatformServiceFactory)
    fake_service = mocker.AsyncMock(spec=SearchPlatformService)
    fake_service.search_and_find_posts.return_value = SearchResult(  # pyright: ignore[reportAny]
        found_posts=[], screenshot=None
    )
    factory.get_service.return_value = fake_service  # pyright: ignore[reportAny]

    task = SearchTask(
        keyword=Keyword(text="k1"), blog_posts_to_find=[], platform=Platform.NAVER_BLOG
    )
    job = SearchJob(tasks=[task])
    await uow.search_jobs.save(job)
    await uow.commit()

    handler = ExecuteSearchTaskCommandHandler(uow=uow, factory=factory)
    command = ExecuteSearchTaskCommand(job_id=job.job_id, task_id=task.task_id)

    await handler.handle(command)

    assert uow.committed is True
    saved_job = await uow.search_jobs.get(job.job_id)
    assert saved_job is not None
    assert saved_job.tasks[0].status == TaskStatus.NOT_FOUND
    assert len(uow.events) == 1
    assert isinstance(uow.events[0], TaskCompleted)


@pytest.mark.asyncio
async def test_task_completed_handler_marks_job_as_completed():
    uow = FakeUnitOfWork()
    handler = TaskCompletedHandler(uow=uow)

    task1 = SearchTask(
        keyword=Keyword(text="k1"), blog_posts_to_find=[], platform=Platform.NAVER_BLOG
    )
    task2 = SearchTask(
        keyword=Keyword(text="k2"), blog_posts_to_find=[], platform=Platform.NAVER_BLOG
    )
    job = SearchJob(tasks=[task1, task2])
    job.update_task_result(task1.task_id, SearchResult(found_posts=[], screenshot=None))
    job.update_task_result(task2.task_id, SearchResult(found_posts=[], screenshot=None))
    await uow.search_jobs.save(job)
    await uow.commit()

    event = TaskCompleted(
        job_id=job.job_id, task_id=task2.task_id, status=TaskStatus.NOT_FOUND.value
    )
    await handler.handle(event)

    assert uow.committed is True
    saved_job = await uow.search_jobs.get(job.job_id)
    assert saved_job is not None
    assert saved_job.status == JobStatus.COMPLETED
    assert len(uow.events) == 1
    assert isinstance(uow.events[0], JobCompleted)
