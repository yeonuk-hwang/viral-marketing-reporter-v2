
import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    Screenshot,
    SearchJob,
    SearchResult,
    SearchTask,
)
from viral_marketing_reporter.domain.repositories import SearchJobRepository


class SqliteSearchJobRepository(SearchJobRepository):
    """SearchJobRepository의 SQLite 구현체"""

    def __init__(self, session: Session):
        self.session = session

    async def save(self, search_job: SearchJob) -> None:
        """SearchJob 애그리거트를 SQLite에 저장합니다."""
        self._prepare_for_persistence(search_job)
        self.session.merge(search_job)
        self.session.commit()

    async def get(self, search_job_id: uuid.UUID) -> SearchJob | None:
        """ID로 SearchJob 애그리거트를 조회하고 도메인 모델로 변환합니다."""
        job = self.session.query(SearchJob).filter_by(job_id=search_job_id).first()
        if job:
            self._reconstitute_from_persistence(job)
            return job
        return None

    def _prepare_for_persistence(self, search_job: SearchJob):
        """도메인 모델을 영속성 계층에 저장하기 전에 직렬화합니다."""
        for task in search_job.tasks:
            # VO -> 원시 타입
            setattr(task, 'keyword_text', task.keyword.text)
            setattr(task, 'posts_to_find_json', json.dumps([p.url for p in task.blog_posts_to_find]))
            if task.result:
                setattr(task, 'found_posts_json', json.dumps([p.url for p in task.result.found_posts]))
                if task.result.screenshot:
                    setattr(task, 'screenshot_path_str', str(task.result.screenshot.file_path))
                else:
                    setattr(task, 'screenshot_path_str', None)
            else:
                setattr(task, 'found_posts_json', None)
                setattr(task, 'screenshot_path_str', None)

    def _reconstitute_from_persistence(self, orm_job: SearchJob):
        """영속성 계층에서 로드한 ORM 객체를 도메인 모델로 재구성합니다."""
        for orm_task in orm_job.tasks:
            # 원시 타입 -> VO
            orm_task.keyword = Keyword(text=getattr(orm_task, 'keyword_text'))
            orm_task.blog_posts_to_find = [Post(url=url) for url in json.loads(getattr(orm_task, 'posts_to_find_json'))]
            
            found_posts_json = getattr(orm_task, 'found_posts_json', None)
            if found_posts_json is not None:
                found_posts = [Post(url=url) for url in json.loads(found_posts_json)]
                screenshot = None
                screenshot_path_str = getattr(orm_task, 'screenshot_path_str', None)
                if screenshot_path_str:
                    screenshot = Screenshot(file_path=Path(screenshot_path_str))
                orm_task.result = SearchResult(found_posts=found_posts, screenshot=screenshot)
            else:
                orm_task.result = None
