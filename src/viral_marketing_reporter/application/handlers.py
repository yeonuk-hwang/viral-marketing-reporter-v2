from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from viral_marketing_reporter.application.commands import (
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
)
from viral_marketing_reporter.domain.events import (
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)
from viral_marketing_reporter.domain.message_bus import MessageBus
from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    SearchJob,
    SearchTask,
)
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)

if TYPE_CHECKING:
    from viral_marketing_reporter.domain.uow import UnitOfWork


class CreateSearchCommandHandler:
    """StartSearchCommand를 처리하여 SearchJob을 생성하고 저장합니다."""

    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, command: CreateSearchCommand):
        """커맨드를 처리합니다."""
        tasks = [
            SearchTask(
                keyword=Keyword(text=task_dto.keyword),
                blog_posts_to_find=[Post(url=url) for url in task_dto.urls],
                platform=task_dto.platform,
            )
            for task_dto in command.tasks
        ]
        async with self.uow:
            job = SearchJob.create(job_id=command.job_id, tasks=tasks)
            await self.uow.search_jobs.save(job)
            await self.uow.commit()


class SearchJobCreatedHandler:
    """SearchJobCreated 이벤트를 처리하여 Job을 시작 상태로 변경합니다."""

    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, event: SearchJobCreated):
        """이벤트가 발생하면, Job을 시작하고 SearchJobStarted 이벤트를 발행합니다."""
        async with self.uow:
            job = await self.uow.search_jobs.get(event.job_id)
            if not job:
                return
            job.start()
            await self.uow.commit()


class SearchJobStartedHandler:
    """SearchJobStarted 이벤트를 처리하여 개별 Task 실행을 위임합니다."""

    def __init__(self, uow: UnitOfWork, bus: MessageBus):
        self.uow: Final = uow
        self.bus: Final = bus

    async def handle(self, event: SearchJobStarted):
        """이벤트가 발생하면, 각 태스크에 대한 커맨드를 발행합니다."""
        async with self.uow:
            job = await self.uow.search_jobs.get(event.job_id)
            if not job:
                return
            for task in job.tasks:
                await self.bus.handle(
                    ExecuteSearchTaskCommand(job_id=job.job_id, task_id=task.task_id)
                )


class ExecuteSearchTaskCommandHandler:
    """ExecuteSearchTaskCommand를 처리하여 개별 태스크를 실행합니다."""

    def __init__(self, uow: UnitOfWork, factory: PlatformServiceFactory):
        self.uow: Final = uow
        self.factory: Final = factory

    async def handle(self, command: ExecuteSearchTaskCommand):
        """커맨드를 처리하여 실제 크롤링을 수행하고 결과를 저장합니다."""
        async with self.uow:
            job = await self.uow.search_jobs.get(command.job_id)
            if not job:
                return
            task_to_execute = next(
                (t for t in job.tasks if t.task_id == command.task_id), None
            )
            if not task_to_execute:
                return

            platform_service = await self.factory.get_service(task_to_execute.platform)
            # TODO: output_dir을 설정 등에서 받아오도록 수정 필요
            output_dir = Path("/tmp/screenshots")
            output_dir.mkdir(exist_ok=True)

            try:
                result = await platform_service.search_and_find_posts(
                    keyword=task_to_execute.keyword,
                    posts_to_find=task_to_execute.blog_posts_to_find,
                    output_dir=output_dir,
                )
                job.update_task_result(task_to_execute.task_id, result)
            except Exception:
                job.update_task_error(task_to_execute.task_id)

            await self.uow.search_jobs.save(job)
            await self.uow.commit()


class TaskCompletedHandler:
    """TaskCompleted 이벤트를 처리하여 Job의 완료 여부를 체크합니다."""

    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, event: TaskCompleted):
        """모든 태스크가 완료되었는지 확인하고, 그렇다면 Job을 완료 처리합니다."""
        async with self.uow:
            job = await self.uow.search_jobs.get(event.job_id)
            if not job:
                return
            job.check_if_completed()
            await self.uow.commit()

