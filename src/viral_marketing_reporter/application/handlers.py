from viral_marketing_reporter.application.commands import StartSearchCommand
from viral_marketing_reporter.domain.model import Keyword, Post, SearchJob, SearchTask
from viral_marketing_reporter.domain.repositories import SearchJobRepository


class SearchCommandHandler:
    repository: SearchJobRepository

    def __init__(self, repository: SearchJobRepository):
        self.repository = repository

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

        # 2. Aggregate Root 생성
        search_job = SearchJob(tasks=tasks)

        # 3. Repository를 통해 저장
        self.repository.save(search_job)
