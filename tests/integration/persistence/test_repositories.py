
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from viral_marketing_reporter.domain.model import (
    Keyword,
    Platform,
    Post,
    SearchJob,
    SearchResult,
    SearchTask,
    Screenshot,
)
from viral_marketing_reporter.infrastructure.persistence.database import create_tables
from viral_marketing_reporter.infrastructure.persistence.orm import start_mappers
from viral_marketing_reporter.infrastructure.persistence.repositories import (
    SqliteSearchJobRepository,
)


@pytest.fixture
def in_memory_session_factory():
    """In-memory SQLite 데이터베이스를 사용하는 세션 팩토리를 제공하는 Fixture"""
    engine = create_engine("sqlite:///:memory:")
    start_mappers()
    create_tables(engine)
    return sessionmaker(bind=engine)


async def test_repository_can_save_and_get_search_job(in_memory_session_factory):
    """SearchJob 애그리거트를 저장하고 조회할 수 있는지 테스트합니다."""
    session = in_memory_session_factory()
    repo = SqliteSearchJobRepository(session)

    # 1. 테스트할 애그리거트 생성
    posts_to_find = [Post(url="http://blog.naver.com/post1")]
    task = SearchTask(
        keyword=Keyword(text="테스트 키워드"),
        blog_posts_to_find=posts_to_find,
        platform=Platform.NAVER_BLOG,
    )
    job = SearchJob.create(tasks=[task])
    job_id = job.job_id

    # 2. 태스크 결과를 업데이트하여 result 필드를 채웁니다.
    screenshot_path = Path("/tmp/screenshot.png")
    result = SearchResult(
        found_posts=[Post(url="http://blog.naver.com/post1")],
        screenshot=Screenshot(file_path=screenshot_path),
    )
    job.update_task_result(task.task_id, result)

    # 3. 저장
    await repo.save(job)
    session.close()

    # 4. 새로운 세션에서 조회
    new_session = in_memory_session_factory()
    new_repo = SqliteSearchJobRepository(new_session)
    retrieved_job = await new_repo.get(job_id)

    # 5. 검증
    assert retrieved_job is not None
    assert retrieved_job.job_id == job_id
    assert len(retrieved_job.tasks) == 1
    retrieved_task = retrieved_job.tasks[0]
    assert retrieved_task.keyword.text == "테스트 키워드"
    assert retrieved_task.blog_posts_to_find[0].url == "http://blog.naver.com/post1"
    
    # Result 필드 검증 추가
    assert retrieved_task.result is not None
    assert len(retrieved_task.result.found_posts) == 1
    assert retrieved_task.result.found_posts[0].url == "http://blog.naver.com/post1"
    assert retrieved_task.result.screenshot is not None
    assert retrieved_task.result.screenshot.file_path == screenshot_path
