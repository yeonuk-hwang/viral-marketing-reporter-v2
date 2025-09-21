import uuid
from typing import override

from viral_marketing_reporter.domain.model import SearchJob
from viral_marketing_reporter.domain.repositories import SearchJobRepository


class InMemorySearchJobRepository(SearchJobRepository):
    def __init__(self) -> None:
        super().__init__()
        self._jobs: dict[uuid.UUID, SearchJob] = {}

    @override
    async def _add(self, search_job: SearchJob) -> None:
        self._jobs[search_job.job_id] = search_job

    @override
    async def _get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        return self._jobs.get(search_job_id)


_repo = None


def in_memory_repository_factory():
    global _repo

    if not _repo:
        _repo = InMemorySearchJobRepository()
        return _repo
    else:
        return _repo
