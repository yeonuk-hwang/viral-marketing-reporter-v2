from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Final

from loguru import logger

from viral_marketing_reporter.application.commands import (
    CreateSearchCommand,
    ExecuteSearchTaskCommand,
    LogoutInstagramCommand,
)
from viral_marketing_reporter.application.queries import (
    GetJobResultQuery,
    JobResultDTO,
    TaskResultDTO,
)
from viral_marketing_reporter.domain.events import (
    JobCompleted,
    SearchJobCreated,
    SearchJobStarted,
    TaskCompleted,
)
from viral_marketing_reporter.domain.message_bus import MessageBus
from viral_marketing_reporter.domain.model import (
    JobStatus,
    Keyword,
    Post,
    SearchJob,
    SearchTask,
    TaskStatus,
)
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)

if TYPE_CHECKING:
    from viral_marketing_reporter.domain.uow import UnitOfWork


class CreateSearchCommandHandler:
    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, command: CreateSearchCommand):
        with logger.contextualize(job_id=command.job_id):
            logger.debug(f"Handling CreateSearchCommand for job {command.job_id}.")
            tasks = [
                SearchTask(
                    index=dto.index,
                    keyword=Keyword(text=dto.keyword),
                    blog_posts_to_find=[Post(url=url) for url in dto.urls],
                    platform=dto.platform,
                    screenshot_all_posts=dto.screenshot_all_posts,
                )
                for dto in command.tasks
            ]
            async with self.uow:
                job = SearchJob.create(job_id=command.job_id, tasks=tasks)
                await self.uow.search_jobs.add(job)
                await self.uow.commit()
            logger.info(f"SearchJob {job.job_id} created with {len(tasks)} tasks.")


class SearchJobCreatedHandler:
    def __init__(self, uow: UnitOfWork, factory: PlatformServiceFactory):
        self.uow: Final = uow
        self.factory: Final = factory

    async def handle(self, event: SearchJobCreated):
        with logger.contextualize(job_id=event.job_id):
            logger.debug(f"Handling SearchJobCreated event for job {event.job_id}.")
            logger.debug(event)

            async with self.uow:
                job = await self.uow.search_jobs.get(event.job_id)
                if not job:
                    logger.warning(f"Job {event.job_id} not found. Cannot start.")
                    return

                # Job의 모든 플랫폼 추출
                platforms = {task.platform for task in job.tasks}
                logger.info(f"Job에 포함된 플랫폼: {[p.value for p in platforms]}")

                # 필요한 플랫폼들의 인증 사전 준비
                await self.factory.prepare_platforms(platforms)

                job.start()
                await self.uow.commit()

            logger.info(f"SearchJob {job.job_id} started.")


class SearchJobStartedHandler:
    def __init__(self, uow: UnitOfWork, bus: MessageBus):
        self.uow: Final = uow
        self.bus: Final = bus

    async def handle(self, event: SearchJobStarted):
        with logger.contextualize(job_id=event.job_id):
            logger.debug(f"Handling SearchJobStarted event for job {event.job_id}.")
            async with self.uow:
                job = await self.uow.search_jobs.get(event.job_id)
                if not job:
                    logger.warning(
                        f"Job {event.job_id} not found. Cannot dispatch tasks."
                    )
                    return

                logger.info(
                    f"Found {len(job.tasks)} tasks in job {job.job_id}. Dispatching commands concurrently..."
                )
                for task in job.tasks:
                    await self.bus.handle(
                        ExecuteSearchTaskCommand(
                            job_id=job.job_id, task_id=task.task_id
                        )
                    )

            logger.debug(f"Finished dispatching commands for job {event.job_id}.")


class ExecuteSearchTaskCommandHandler:
    def __init__(self, uow: UnitOfWork, factory: PlatformServiceFactory):
        self.uow: Final = uow
        self.factory: Final = factory

    async def handle(self, command: ExecuteSearchTaskCommand):
        with logger.contextualize(
            job_id=str(command.job_id), task_id=str(command.task_id)
        ):
            logger.debug("Handling ExecuteSearchTaskCommand.")

            try:
                async with self.uow:
                    job = await self.uow.search_jobs.get(command.job_id)
                    if not job:
                        logger.warning("Job not found. Aborting task.")
                        return
                    task = next(
                        (t for t in job.tasks if t.task_id == command.task_id),
                        None,
                    )
                    if not task:
                        logger.warning("Task not found in job. Aborting.")
                        return

                    urls_to_find = [p.url for p in task.blog_posts_to_find]
                    logger.info(
                        f"Executing search for keyword '{task.keyword.text}' with URLs: {urls_to_find}"
                    )

                    output_dir = (
                        Path.home()
                        / "Downloads"
                        / "viral-reporter"
                        / task.platform.value
                        / str(command.job_id)
                    )
                    output_dir.mkdir(parents=True, exist_ok=True)

                    platform_service = await self.factory.get_service(task.platform)
                    result = await platform_service.search_and_find_posts(
                        index=task.index,
                        keyword=task.keyword,
                        posts_to_find=task.blog_posts_to_find,
                        output_dir=output_dir,
                        screenshot_all_posts=task.screenshot_all_posts,
                    )
                    job.update_task_result(task.task_id, result)
                    logger.info("Task completed successfully.")
                    await self.uow.search_jobs.add(job)
                    await self.uow.commit()

            except Exception as e:
                logger.exception("An unexpected error occurred during task execution.")
                try:
                    async with self.uow:
                        job = await self.uow.search_jobs.get(command.job_id)
                        if job:
                            task = next(
                                (t for t in job.tasks if t.task_id == command.task_id),
                                None,
                            )
                            if task:
                                job.update_task_error(task.task_id, str(e))
                                await self.uow.search_jobs.add(job)
                                await self.uow.commit()
                except Exception as inner_e:
                    logger.critical(
                        f"Failed to update task status to ERROR after initial exception: {inner_e}"
                    )


class TaskCompletedHandler:
    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, event: TaskCompleted):
        with logger.contextualize(job_id=str(event.job_id), task_id=str(event.task_id)):
            logger.debug(
                f"Handling TaskCompleted event for task {event.task_id} in job {event.job_id}."
            )
            async with self.uow:
                job = await self.uow.search_jobs.get(event.job_id)
                if not job:
                    logger.warning(
                        f"Job {event.job_id} not found. Cannot check for completion."
                    )
                    return

                is_completed_before = job.status == JobStatus.COMPLETED
                job.check_if_completed()
                is_completed_after = job.status == JobStatus.COMPLETED

                if not is_completed_before and is_completed_after:
                    logger.info(f"All tasks for job {job.job_id} are complete.")
                else:
                    pending_tasks = [
                        t.task_id for t in job.tasks if t.status == TaskStatus.PENDING
                    ]
                    logger.debug(
                        f"Job {job.job_id} not yet complete. {len(pending_tasks)} tasks still pending."
                    )
                await self.uow.commit()


class JobCompletedHandler:
    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, event: JobCompleted):
        with logger.contextualize(job_id=str(event.job_id)):
            # UI 알림, 최종 리포트 생성 등 추가 작업 수행 가능
            logger.info(f"Job {event.job_id} officially marked as completed.")
            pass


class GetJobResultQueryHandler:
    def __init__(self, uow: UnitOfWork):
        self.uow: Final = uow

    async def handle(self, query: GetJobResultQuery) -> JobResultDTO | None:
        with logger.contextualize(job_id=str(query.job_id)):
            logger.debug(f"Handling GetJobResultQuery for job {query.job_id}.")
            async with self.uow:
                job = await self.uow.search_jobs.get(query.job_id)
                if not job:
                    logger.warning(f"Job {query.job_id} not found in query handler.")
                    return None

                task_dtos = [
                    TaskResultDTO(
                        keyword=task.keyword.text,
                        status=task.status.value,
                        found_post_urls=[
                            post.url for post in task.result.found_posts
                        ]
                        if task.result
                        else [],
                        screenshot_path=str(task.result.screenshot.file_path)
                        if task.result and task.result.screenshot
                        else None,
                        error_message=task.error_message,
                    )
                    for task in job.tasks
                ]
                logger.debug(
                    f"Returning DTO for job {query.job_id} with {len(task_dtos)} tasks."
                )
                return JobResultDTO(
                    job_id=job.job_id,
                    status=job.status.value,
                    tasks=task_dtos,
                )


class LogoutInstagramCommandHandler:
    def __init__(self, factory: PlatformServiceFactory):
        self.factory: Final = factory

    async def handle(self, command: LogoutInstagramCommand):
        logger.info("Handling LogoutInstagramCommand - clearing Instagram session.")
        try:
            await self.factory.logout_instagram()
            logger.info("Instagram session cleared successfully.")
        except Exception as e:
            logger.error(f"Failed to logout Instagram: {str(e)}")
