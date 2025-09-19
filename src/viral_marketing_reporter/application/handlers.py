import asyncio
import uuid

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


class SearchCommandHandler:
    repository: SearchJobRepository
    factory: PlatformServiceFactory

    def __init__(
        self, repository: SearchJobRepository, factory: PlatformServiceFactory
    ):
        self.repository = repository
        self.factory = factory

    async def _execute_task(self, task: SearchTask) -> tuple[uuid.UUID, SearchResult]:
        """개별 태스크를 비동기적으로 실행합니다."""
        platform_service = self.factory.get_service(task.platform)
        result = await platform_service.search_and_find_posts(
            keyword=task.keyword, posts_to_find=task.blog_posts_to_find
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

        # 각 태스크를 비동기 작업으로 생성
        async_tasks = [self._execute_task(task) for task in search_job.tasks]

        # 모든 태스크를 동시에 실행
        results = await asyncio.gather(*async_tasks, return_exceptions=True)

        # 결과 업데이트
        for result in results:
            if isinstance(result, Exception):
                # 실제로는 태스크 ID를 알 수 없으므로, 더 나은 예외 처리 방식이 필요함
                print(f"태스크 처리 중 에러 발생: {result}")
            else:
                task_id, search_result = result
                search_job.update_task_result(task_id, search_result)

        await self.repository.save(search_job)
