from __future__ import annotations

from typing import override

from loguru import logger

from viral_marketing_reporter.domain.message_bus import MessageBus
from viral_marketing_reporter.domain.uow import UnitOfWork
from viral_marketing_reporter.infrastructure.repositories import (
    in_memory_repository_factory,
)


class InMemoryUnitOfWork(UnitOfWork):
    """인메모리 Unit of Work 구현체"""

    def __init__(self, bus: MessageBus):
        self.search_jobs = in_memory_repository_factory()
        self.bus = bus

    @override
    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    @override
    async def __aexit__(self, exc_type, exc_val, traceback):
        await self.rollback()

    @override
    async def commit(self):
        for job in self.search_jobs.seen:
            events = job.pull_events()
            for event in events:
                logger.debug(f"Dispatching event: {event}")
                await self.bus.handle(event)

    @override
    async def rollback(self):
        pass

