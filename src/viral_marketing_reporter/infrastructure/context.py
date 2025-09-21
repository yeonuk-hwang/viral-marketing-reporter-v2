from __future__ import annotations

from types import TracebackType
from typing import Type

from playwright.async_api import Browser, Page, Playwright, async_playwright
from sqlalchemy.orm import sessionmaker

from viral_marketing_reporter.domain.uow import UnitOfWork
from viral_marketing_reporter.infrastructure.persistence.database import (
    create_tables,
    get_engine,
    get_session_factory,
)
from viral_marketing_reporter.infrastructure.persistence.orm import start_mappers
from viral_marketing_reporter.infrastructure.uow import SqlAlchemyUnitOfWork


class ApplicationContext:
    """애플리케이션의 전역 리소스(브라우저, DB 연결 풀)를 관리합니다."""

    def __init__(self, db_path: str = "sqlite:///viral_reporter.db") -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._pages: list[Page] = []
        self.db_path = db_path
        self.session_factory: sessionmaker | None = None

    async def __aenter__(self) -> ApplicationContext:
        # Playwright 초기화
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=False)

        # 데이터베이스 및 ORM 초기화
        engine = get_engine(self.db_path)
        start_mappers()
        create_tables(engine)
        self.session_factory = get_session_factory(engine)

        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Playwright 정리
        for page in self._pages:
            await page.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self.browser:
            raise RuntimeError("Browser context is not running.")
        page = await self.browser.new_page(viewport={"width": 1920, "height": 1080})
        self._pages.append(page)
        return page

    def uow(self) -> UnitOfWork:
        """새로운 Unit of Work 인스턴스를 반환합니다."""
        if not self.session_factory:
            raise RuntimeError("Database is not initialized.")
        return SqlAlchemyUnitOfWork(self.session_factory)