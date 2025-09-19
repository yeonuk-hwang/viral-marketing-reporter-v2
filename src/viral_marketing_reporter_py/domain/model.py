import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# --- Value Objects ---


@dataclass(frozen=True)
class Keyword:
    """검색 키워드를 나타내는 Value Object"""

    text: str


@dataclass(frozen=True)
class Post:
    """게시물 URL을 나타내는 Value Object"""

    url: str


@dataclass(frozen=True)
class Screenshot:
    """스크린샷 파일 경로를 나타내는 Value Object"""

    file_path: str


@dataclass(frozen=True)
class SearchResult:
    """개별 검색 작업의 결과를 담는 Value Object"""

    found_posts: list[Post]
    screenshot: Screenshot | None


# --- Enums for Status ---


class TaskStatus(Enum):
    PENDING = "대기"
    FOUND = "포함"
    NOT_FOUND = "미포함"
    ERROR = "에러"


class JobStatus(Enum):
    PENDING = "대기"
    RUNNING = "실행 중"
    COMPLETED = "완료"
    FAILED = "실패"


# --- Entities & Aggregate Root ---


@dataclass
class SearchTask:
    """하나의 키워드에 대한 검색 작업을 나타내는 Entity"""

    keyword: Keyword
    blog_posts_to_find: list[Post]
    status: TaskStatus = TaskStatus.PENDING
    result: SearchResult | None = None
    task_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class SearchJob:
    """
    여러 SearchTask를 포함하는 Aggregate Root.
    데이터 일관성의 단위입니다.
    """

    tasks: list[SearchTask]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    job_id: uuid.UUID = field(default_factory=uuid.uuid4)
