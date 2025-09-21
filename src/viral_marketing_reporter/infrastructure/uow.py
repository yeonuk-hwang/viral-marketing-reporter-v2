
from __future__ import annotations

from types import TracebackType
from typing import Type

from sqlalchemy.orm import Session, sessionmaker

from viral_marketing_reporter.domain.events import Event
from viral_marketing_reporter.domain.model import SearchJob
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.domain.uow import UnitOfWork
from viral_marketing_reporter.infrastructure import message_bus
from viral_marketing_reporter.infrastructure.persistence.repositories import (
    SqliteSearchJobRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy를 사용한 Unit of Work 구현체"""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self.session: Session = self.session_factory()
        self.search_jobs: SearchJobRepository = SqliteSearchJobRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ):
        if exc_type:
            await self.rollback()
        self.session.close()

    async def commit(self):
        """DB 변경사항을 커밋하고, 수집된 도메인 이벤트를 발행합니다."""
        # self.session.dirty를 사용하여 변경된 애그리거트를 찾습니다.
        dirty_aggregates = [obj for obj in self.session.dirty if isinstance(obj, SearchJob)]
        
        all_events: list[Event] = []
        for aggregate in dirty_aggregates:
            all_events.extend(aggregate.pull_events())

        self.session.commit()

        # DB 커밋이 성공한 후에만 이벤트를 발행합니다.
        for event in all_events:
            await message_bus.handle(event)

    async def rollback(self):
        self.session.rollback()
