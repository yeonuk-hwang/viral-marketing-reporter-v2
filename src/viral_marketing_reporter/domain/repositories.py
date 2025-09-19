import uuid
from typing import Protocol

from viral_marketing_reporter.domain.model import SearchJob


class SearchJobRepository(Protocol):
    def save(self, search_job: SearchJob) -> None:
        """SearchJob 애그리거트를 저장합니다."""
        ...

    def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        """ID로 SearchJob 애그리거트를 조회합니다."""
        ...
