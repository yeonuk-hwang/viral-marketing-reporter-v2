import uuid

from viral_marketing_reporter.application.commands import StartSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import SearchCommandHandler
from viral_marketing_reporter.domain.model import Platform, SearchJob


class InMemorySearchJobRepository:
    """Protocol을 만족하는 가짜 리포지토리 구현체"""

    def __init__(self) -> None:
        self._jobs: list[SearchJob] = []

    def save(self, search_job: SearchJob) -> None:
        self._jobs.append(search_job)

    def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        return next((job for job in self._jobs if job.job_id == search_job_id), None)

    def list(self) -> list[SearchJob]:
        """테스트 검증을 위해 저장된 모든 job을 반환하는 공개 메서드"""
        return self._jobs


def test_handler_creates_and_saves_search_job():
    """
    StartSearchCommand를 처리할 때, 핸들러는 SearchJob을 생성하고 저장해야 한다.
    """
    # 1. 준비 (Arrange)
    fake_repository = InMemorySearchJobRepository()
    handler = SearchCommandHandler(repository=fake_repository)
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
    handler.handle(command)

    # 3. 검증 (Assert)
    saved_jobs = fake_repository.list()
    assert len(saved_jobs) == 1

    saved_job = saved_jobs[0]
    assert isinstance(saved_job, SearchJob)
    assert len(saved_job.tasks) == 2
