
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import registry, relationship
from sqlalchemy.types import TypeDecorator
from sqlalchemy.types import String as SQLString

from viral_marketing_reporter.domain.model import (
    JobStatus,
    Platform,
    SearchJob,
    SearchTask,
    TaskStatus,
)

# --- Custom Types ---

class GUID(TypeDecorator):
    """SQLite를 위한 UUID 커스텀 타입. UUID를 문자열로 저장합니다."""
    impl = SQLString(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(value)

# SQLAlchemy 2.0 스타일의 메타데이터 객체
metadata = MetaData()
mapper_registry = registry(metadata=metadata)


# 도메인 모델과 데이터베이스 테이블 간의 매핑 정의
search_jobs_table = Table(
    "search_jobs",
    mapper_registry.metadata,
    Column("job_id", GUID, primary_key=True, default=uuid.uuid4),
    Column("status", Enum(JobStatus), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

search_tasks_table = Table(
    "search_tasks",
    mapper_registry.metadata,
    Column("task_id", GUID, primary_key=True, default=uuid.uuid4),
    Column("job_id", GUID, ForeignKey("search_jobs.job_id"), nullable=False),
    Column("platform", Enum(Platform), nullable=False),
    Column("status", Enum(TaskStatus), nullable=False),
    # Value Objects를 직렬화된 형태로 저장
    Column("keyword", Text, nullable=False),  # Keyword.text
    Column("blog_posts_to_find", Text, nullable=False),  # json.dumps([post.url])
    Column("result_found_posts", Text, nullable=True),  # json.dumps([post.url])
    Column("result_screenshot_path", String, nullable=True),  # str(path)
)


def start_mappers():
    """
    도메인 모델과 테이블을 매핑합니다.
    이 함수는 애플리케이션 시작 시 한 번만 호출되어야 합니다.
    """
    # SearchTask 매핑
    # repository에서 VO와 원시 타입 간의 변환을 책임집니다.
    mapper_registry.map_imperatively(
        SearchTask,
        search_tasks_table,
        properties={
            "keyword_text": search_tasks_table.c.keyword,
            "posts_to_find_json": search_tasks_table.c.blog_posts_to_find,
            "found_posts_json": search_tasks_table.c.result_found_posts,
            "screenshot_path_str": search_tasks_table.c.result_screenshot_path,
        },
    )

    # SearchJob 매핑 (SearchTask와의 관계 포함)
    mapper_registry.map_imperatively(
        SearchJob,
        search_jobs_table,
        properties={
            "tasks": relationship(
                SearchTask, backref="job", cascade="all, delete-orphan"
            ),
        },
    )
