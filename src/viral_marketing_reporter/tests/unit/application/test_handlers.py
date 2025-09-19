import asyncio
import uuid
from typing import override

import pytest

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
    """실제 네트워크 요청을 하지 않는 가짜 서비스"""

    @override
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post]
    ) -> SearchResult:
        await asyncio.sleep(0.01)  # 비동기 작업 흉내
        # 테스트의 목적에 맞게 특정 포스트를 찾았다고 가정
        if keyword.text == "강남 맛집":
            return SearchResult(found_posts=[posts_to_find[0]], screenshot=None)
        return SearchResult(found_posts=[], screenshot=None)


@pytest.mark.asyncio
async def test_handler_executes_tasks_concurrently():
    """핸들러는 여러 태스크를 동시에 실행하고 결과를 종합해야 한다."""
    # 1. 준비 (Arrange)
    fake_repository = InMemorySearchJobRepository()
    factory = PlatformServiceFactory()
    factory.register_service(Platform.NAVER_BLOG, FakeSearchPlatformService())

    handler = SearchCommandHandler(repository=fake_repository, factory=factory)
    command = StartSearchCommand(
        tasks=[
            TaskDTO(
                keyword="강남 맛집",
                urls=["https://blog.naver.com/post1"],
                platform=Platform.NAVER_BLOG,
            ),
            TaskDTO(
                keyword="제주도 여행",
                urls=["https://blog.naver.com/post2"],
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
    assert len(saved_job.tasks) == 2

    # 각 태스크의 결과 확인
    task1 = next(t for t in saved_job.tasks if t.keyword.text == "강남 맛집")
    task2 = next(t for t in saved_job.tasks if t.keyword.text == "제주도 여행")
    assert task1.status == TaskStatus.FOUND
    assert task2.status == TaskStatus.NOT_FOUND
