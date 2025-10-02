import uuid
from pathlib import Path

import pytest

from viral_marketing_reporter import bootstrap
from viral_marketing_reporter.application.commands import CreateSearchCommand, TaskDTO
from viral_marketing_reporter.domain.model import JobStatus, Platform, TaskStatus
from viral_marketing_reporter.infrastructure.context import ApplicationContext
from viral_marketing_reporter.infrastructure.message_bus import InMemoryMessageBus
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)
from viral_marketing_reporter.infrastructure.platforms.naver_blog.service import (
    PlaywrightNaverBlogService,
)
from viral_marketing_reporter.infrastructure.uow import InMemoryUnitOfWork

SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"


@pytest.mark.asyncio
async def test_e2e_full_process_with_mixed_results():
    bus = InMemoryMessageBus()
    uow = InMemoryUnitOfWork(bus)

    # 테스트 데이터 설정, Smoke Test로 실제 UI가 변경되면 실패할 수 있음
    keyword = "파이썬 Playwright"
    urls_to_find = [
        "https://blog.naver.com/richlegend1/223526683586",  # Found
        "https://blog.naver.com/sinx2233/223320815540",  # Found
        "https://blog.naver.com/theboni/224013165053",  # Not Found
    ]
    expected_found_urls = set(urls_to_find[:2])

    job_id = uuid.uuid4()
    output_path = (
        Path.home()
        / "Downloads"
        / "viral-reporter"
        / "naver_blog"
        / str(job_id)
        / ("1_" + keyword.replace(" ", "_") + ".png")
    )

    # 2. Act: 실제 애플리케이션의 실행 흐름을 모방합니다.
    async with ApplicationContext() as context:
        # 2.2. 실제 Factory를 생성하고, 실제 Service를 등록합니다.
        factory = PlatformServiceFactory(context)
        factory.register_service(Platform.NAVER_BLOG, PlaywrightNaverBlogService)

        # 2.3. 모든 의존성을 주입하여 핸들러들을 연결합니다.
        bootstrap.bootstrap(uow=uow, bus=bus, factory=factory)

        # 2.4. 최초 커맨드를 발행하고, 최종 이벤트가 발생할 때까지 기다립니다.
        command = CreateSearchCommand(
            job_id=job_id,
            tasks=[
                TaskDTO(
                    index=1,
                    keyword=keyword,
                    urls=urls_to_find,
                    platform=Platform.NAVER_BLOG,
                )
            ],
        )
        await bus.handle(command)

    # 3. Assert: 최종 결과를 검증합니다.
    async with uow:
        job = await uow.search_jobs.get(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert len(job.tasks) == 1
        task = job.tasks[0]
        assert task.status == TaskStatus.FOUND
        assert task.result is not None
        found_urls_in_result = {post.url for post in task.result.found_posts}
        assert found_urls_in_result == expected_found_urls
        assert output_path.exists()

