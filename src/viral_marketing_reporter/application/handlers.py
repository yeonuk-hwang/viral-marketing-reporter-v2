import asyncio
import uuid
from pathlib import Path

from viral_marketing_reporter.application.commands import StartSearchCommand
from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    SearchJob,
    SearchResult,
    SearchTask,
)
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.infrastructure.context import SearchExecutionContext
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
        self, task: SearchTask, output_dir: str
    ) -> tuple[uuid.UUID, SearchResult]:
        """개별 태스크를 비동기적으로 실행합니다."""
        platform_service = await self.factory.get_service(task.platform)
        result = await platform_service.search_and_find_posts(
            keyword=task.keyword,
            posts_to_find=task.blog_posts_to_find,
            output_dir=output_dir,
        )
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
        search_job.start()

        output_dir = DEFAULT_DOWNLOAD_PATH / str(search_job.job_id)

        async with SearchExecutionContext() as context:
            factory = PlatformServiceFactory(context)
            # TODO: Composition Root에서 팩토리 설정이 이루어져야 함
            # factory.register_service(...)

            async_tasks = [
                self._execute_task(task, str(output_dir)) for task in search_job.tasks
            ]
            results = await asyncio.gather(*async_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # TODO: 태스크 ID를 특정하여 에러 처리 개선 필요
                print(f"태스크 처리 중 에러 발생: {result}")
            else:
                task_id, search_result = result
                search_job.update_task_result(task_id, search_result)

        await self.repository.save(search_job)