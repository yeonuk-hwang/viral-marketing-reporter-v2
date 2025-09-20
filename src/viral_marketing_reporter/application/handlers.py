import asyncio
import uuid
from pathlib import Path

from loguru import logger

from viral_marketing_reporter.application.commands import StartSearchCommand
from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    SearchJob,
    SearchResult,
    SearchTask,
)
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)

# TODO: OS별 사용자 다운로드 폴더를 찾는 로직 추가
DEFAULT_DOWNLOAD_PATH = Path.home() / "Downloads"


class SearchCommandHandler:
    repository: SearchJobRepository
    factory: PlatformServiceFactory

    def __init__(
        self, repository: SearchJobRepository, factory: PlatformServiceFactory
    ):
        self.repository = repository
        self.factory = factory

    async def _execute_task(
        self, task: SearchTask, output_dir: Path
    ) -> tuple[uuid.UUID, SearchResult]:
        with logger.contextualize(task_id=str(task.task_id)):
            logger.info(f"'{task.keyword.text}' 키워드에 대한 작업 시작")
            platform_service = await self.factory.get_service(task.platform)
            result = await platform_service.search_and_find_posts(
                keyword=task.keyword,
                posts_to_find=task.blog_posts_to_find,
                output_dir=output_dir,
            )
            logger.info(f"'{task.keyword.text}' 키워드에 대한 작업 종료")
            return task.task_id, result

    async def handle(self, command: StartSearchCommand):
        tasks = [
            SearchTask(
                keyword=Keyword(text=task_dto.keyword),
                blog_posts_to_find=[Post(url=url) for url in task_dto.urls],
                platform=task_dto.platform,
            )
            for task_dto in command.tasks
        ]
        search_job = SearchJob(tasks=tasks)

        with logger.contextualize(job_id=str(search_job.job_id)):
            logger.info("새로운 검색 작업 시작", event_name="new_search_job_started")
            search_job.start()

            output_dir = DEFAULT_DOWNLOAD_PATH / str(search_job.job_id)

            async def run_and_capture_result(
                task: SearchTask,
            ) -> tuple[uuid.UUID, SearchResult | BaseException]:
                """_execute_task를 안전하게 실행하고 예외 발생 시에도 task_id를 함께 반환합니다."""
                try:
                    # _execute_task는 성공 시 (task_id, result) 튜플을 반환합니다.
                    _, result = await self._execute_task(task, output_dir)
                    return task.task_id, result
                except Exception as e:
                    return task.task_id, e

            async_tasks = [run_and_capture_result(task) for task in search_job.tasks]
            results = await asyncio.gather(*async_tasks)

            for task_id, result in results:
                if isinstance(result, BaseException):
                    logger.error(f"태스크(id:{task_id}) 처리 중 예외 발생: {result}")
                    search_job.update_task_error(task_id)
                else:
                    search_job.update_task_result(task_id, result)

            logger.info("작업 종료", event_name="new_search_job_finished")

        await self.repository.save(search_job)
