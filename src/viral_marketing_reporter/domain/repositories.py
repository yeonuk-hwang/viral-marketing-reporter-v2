import uuid
from abc import ABC, abstractmethod
from typing import Set

from viral_marketing_reporter.domain.model import SearchJob


class SearchJobRepository(ABC):
    seen: Set[SearchJob]

    def __init__(self):
        self.seen = set()

    async def add(self, search_job: SearchJob) -> None:
        await self._add(search_job)
        self.seen.add(search_job)

    async def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        search_job = await self._get(search_job_id)
        if search_job:
            self.seen.add(search_job)
        return search_job

    @abstractmethod
    async def _add(self, search_job: SearchJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def _get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        raise NotImplementedError

