import asyncio
import uuid
from pathlib import Path
from typing import override

import pytest
from playwright.async_api import Page

from viral_marketing_reporter.application.commands import StartSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import SearchCommandHandler
from viral_marketing_reporter.domain.model import (
    JobStatus,
    Keyword,
    Platform,
    Post,
    SearchJob,
    SearchResult,
    TaskStatus,
)
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.infrastructure.context import SearchExecutionContext
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)


class InMemorySearchJobRepository(SearchJobRepository):
    def __init__(self) -> None:
        self._jobs: list[SearchJob] = []

    @override
    async def save(self, search_job: SearchJob) -> None:
        self._jobs.append(search_job)

    @override
    async def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        return next((job for job in self._jobs if job.job_id == search_job_id), None)

    def list(self) -> list[SearchJob]:
        return self._jobs


class FakeSearchPlatformService(SearchPlatformService):
    """성공, 실패, 예외 케이스를 시뮬레이션하는 가짜 서비스"""

    def __init__(self, page: Page) -> None:
        pass

    @override
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post], output_dir: Path
    ) -> SearchResult:
        await asyncio.sleep(0.01)
        if keyword.text == "SUCCESS_KEYWORD":
            return SearchResult(found_posts=[posts_to_find[0]], screenshot=None)
        if keyword.text == "ERROR_KEYWORD":
            raise ValueError("Intentional test error")
        return SearchResult(found_posts=[], screenshot=None)


class FakeExecutionContext(SearchExecutionContext):
    @override
    async def __aenter__(self) -> "FakeExecutionContext":
        return self

    @override
    async def __aexit__(self, *args, **kwargs) -> None:  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        pass

    @override
    async def new_page(self) -> Page:
        return None  # pyright: ignore[reportReturnType]


@pytest.mark.asyncio
async def test_handler_creates_and_saves_search_job_on_success():
    """핸들러가 모든 태스크가 성공했을 때 Job을 정상적으로 생성하고 저장하는지 검증합니다."""
    # 1. 준비 (Arrange)
    fake_repository = InMemorySearchJobRepository()
    fake_context = FakeExecutionContext()
    factory = PlatformServiceFactory(context=fake_context)
    factory.register_service(Platform.NAVER_BLOG, FakeSearchPlatformService)

    handler = SearchCommandHandler(repository=fake_repository, factory=factory)
    command = StartSearchCommand(
        tasks=[
            TaskDTO(
                keyword="SUCCESS_KEYWORD",
                urls=["https://blog.naver.com/post1"],
                platform=Platform.NAVER_BLOG,
            ),
        ]
    )

    # 2. 실행 (Act)
    await handler.handle(command)

    # 3. 검증 (Assert)
    saved_jobs = fake_repository.list()
    assert len(saved_jobs) == 1
    saved_job = saved_jobs[0]
    assert saved_job.status == JobStatus.COMPLETED
    assert saved_job.tasks[0].status == TaskStatus.FOUND


@pytest.mark.asyncio
async def test_handler_handles_mixed_task_results():
    """핸들러가 태스크의 성공, 실패, 예외 케이스를 모두 정확히 처리하는지 검증합니다."""
    # 1. 준비 (Arrange)
    fake_repository = InMemorySearchJobRepository()
    fake_context = FakeExecutionContext()
    factory = PlatformServiceFactory(context=fake_context)
    factory.register_service(Platform.NAVER_BLOG, FakeSearchPlatformService)

    handler = SearchCommandHandler(repository=fake_repository, factory=factory)
    command = StartSearchCommand(
        tasks=[
            TaskDTO(
                keyword="SUCCESS_KEYWORD",
                urls=["https://blog.naver.com/post1"],
                platform=Platform.NAVER_BLOG,
            ),
            TaskDTO(
                keyword="FAILURE_KEYWORD",
                urls=["https://blog.naver.com/post2"],
                platform=Platform.NAVER_BLOG,
            ),
            TaskDTO(
                keyword="ERROR_KEYWORD",
                urls=["https://blog.naver.com/post3"],
                platform=Platform.NAVER_BLOG,
            ),
        ]
    )

    # 2. 실행 (Act)
    await handler.handle(command)

    # 3. 검증 (Assert)
    saved_jobs = fake_repository.list()
    assert len(saved_jobs) == 1
    saved_job = saved_jobs[0]

    assert saved_job.status == JobStatus.COMPLETED
    assert len(saved_job.tasks) == 3

    # 각 태스크의 최종 상태를 정확히 기록했는지 확인
    status_map = {task.keyword.text: task.status for task in saved_job.tasks}
    assert status_map["SUCCESS_KEYWORD"] == TaskStatus.FOUND
    assert status_map["FAILURE_KEYWORD"] == TaskStatus.NOT_FOUND
    assert status_map["ERROR_KEYWORD"] == TaskStatus.ERROR
