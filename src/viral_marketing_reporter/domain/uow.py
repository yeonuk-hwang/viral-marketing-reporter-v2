
from __future__ import annotations
from typing import Protocol

from viral_marketing_reporter.domain.repositories import SearchJobRepository


class UnitOfWork(Protocol):
    """Unit of Work 패턴의 추상 인터페이스"""

    search_jobs: SearchJobRepository

    async def __aenter__(self) -> UnitOfWork:
        ...

    async def __aexit__(self, exc_type, exc_val, traceback):
        ...

    async def commit(self):
        ...

    async def rollback(self):
        ...
