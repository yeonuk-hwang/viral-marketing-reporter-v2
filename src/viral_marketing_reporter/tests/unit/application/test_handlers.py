import uuid
from typing import override

from viral_marketing_reporter.application.commands import StartSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import SearchCommandHandler
from viral_marketing_reporter.domain.model import JobStatus, Platform, SearchJob, TaskStatus
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)
from viral_marketing_reporter.infrastructure.platforms.naver_blog_service import (
    PlaywrightNaverBlogService,
)


class InMemorySearchJobRepository:
    """Protocol을 만족하는 가짜 리포지토리 구현체"""

    def __init__(self) -> None:
        self._jobs: list[SearchJob] = []

    @override
    def save(self, search_job: SearchJob) -> None:
        self._jobs.append(search_job)

    @override
    def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        return next((job for job in self._jobs if job.job_id == search_job_id), None)

    def list(self) -> list[SearchJob]:
        """테스트 검증을 위해 저장된 모든 job을 반환하는 공개 메서드"""
        return self._jobs


def test_handler_executes_search_job_via_factory():
    """
    핸들러는 팩토리를 통해 적절한 서비스를 받아 태스크를 실행해야 한다.
    """
    # 1. 준비 (Arrange)
    fake_repository = InMemorySearchJobRepository()

    # 실제 팩토리를 사용하되, 실제 서비스를 등록
    factory = PlatformServiceFactory()
    factory.register_service(Platform.NAVER_BLOG, PlaywrightNaverBlogService())

    handler = SearchCommandHandler(repository=fake_repository, factory=factory)
    command = StartSearchCommand(
        tasks=[
            TaskDTO(
                keyword="강남 맛집",
                urls=["https://blog.naver.com/post1"],
                platform=Platform.NAVER_BLOG,
            ),
        ]
    )

    # 2. 실행 (Act)
    handler.handle(command)

    # 3. 검증 (Assert)
    saved_jobs = fake_repository.list()
    assert len(saved_jobs) == 1

    saved_job = saved_jobs[0]
    # 핸들러가 search_job.start()와 search_job.update_task_result()를 호출했으므로
    # 최종 상태는 COMPLETED 여야 함
    assert saved_job.status == JobStatus.COMPLETED
    assert len(saved_job.tasks) == 1
    assert saved_job.tasks[0].status == TaskStatus.NOT_FOUND