from viral_marketing_reporter.application.commands import StartSearchCommand
from viral_marketing_reporter.domain.model import Keyword, Post, SearchJob, SearchTask
from viral_marketing_reporter.domain.repositories import SearchJobRepository
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)


class SearchCommandHandler:
    repository: SearchJobRepository
    factory: PlatformServiceFactory

    def __init__(self, repository: SearchJobRepository, factory: PlatformServiceFactory):
        self.repository = repository
        self.factory = factory

    def handle(self, command: StartSearchCommand) -> None:
        # 1. Command DTO를 Domain Object로 변환
        tasks = [
            SearchTask(
                keyword=Keyword(text=task_dto.keyword),
                blog_posts_to_find=[Post(url=url) for url in task_dto.urls],
                platform=task_dto.platform,
            )
            for task_dto in command.tasks
        ]
        search_job = SearchJob(tasks=tasks)
        search_job.start()  # 작업 상태를 RUNNING으로 변경

        # 2. 각 태스크를 순회하며 플랫폼 서비스를 통해 실행
        for task in search_job.tasks:
            try:
                # 2.1. 팩토리에서 적절한 플랫폼 서비스 가져오기
                platform_service = self.factory.get_service(task.platform)

                # 2.2. 서비스 실행 및 결과 받기
                result = platform_service.search_and_find_posts(
                    keyword=task.keyword, posts_to_find=task.blog_posts_to_find
                )

                # 2.3. 도메인 객체에 결과 업데이트
                search_job.update_task_result(task.task_id, result)

            except Exception as e:
                print(f"태스크 처리 중 에러 발생: {e}")  # 임시 에러 처리
                search_job.update_task_error(task.task_id)

        # 3. 모든 태스크가 처리된 최종 작업 결과를 저장
        self.repository.save(search_job)