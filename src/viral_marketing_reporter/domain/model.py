import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import override

# --- Value Objects ---


class Platform(Enum):
    NAVER_BLOG = "naver_blog"


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


@dataclass(eq=False)
class SearchTask:
    """하나의 키워드에 대한 검색 작업을 나타내는 Entity"""

    keyword: Keyword
    blog_posts_to_find: list[Post]
    platform: Platform
    status: TaskStatus = TaskStatus.PENDING
    result: SearchResult | None = None
    task_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def update_result(self, result: SearchResult):
        """태스크의 결과를 기록하고 상태를 변경합니다."""
        self.status = TaskStatus.FOUND if result.found_posts else TaskStatus.NOT_FOUND
        self.result = result

    def mark_as_error(self):
        """태스크를 에러 상태로 변경합니다."""
        self.status = TaskStatus.ERROR

    @override
    def __eq__(self, other: object):
        if not isinstance(other, SearchTask):
            return NotImplemented
        return self.task_id == other.task_id

    @override
    def __hash__(self):
        return hash(self.task_id)


@dataclass(eq=False)
class SearchJob:
    """여러 SearchTask를 포함하는 Aggregate Root."""

    tasks: list[SearchTask]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    job_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def start(self):
        """작업을 시작합니다."""
        if self.status != JobStatus.PENDING:
            raise ValueError("이미 시작되었거나 완료된 작업입니다.")
        self.status = JobStatus.RUNNING

    def update_task_result(self, task_id: uuid.UUID, result: SearchResult):
        """완료된 태스크의 결과를 업데이트합니다."""
        task = self._find_task_by_id(task_id)
        if task:
            task.update_result(result)
            self._check_if_completed()

    def update_task_error(self, task_id: uuid.UUID):
        """에러가 발생한 태스크의 상태를 업데이트합니다."""
        task = self._find_task_by_id(task_id)
        if task:
            task.mark_as_error()
            self._check_if_completed()

    def _find_task_by_id(self, task_id: uuid.UUID) -> SearchTask | None:
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def _check_if_completed(self):
        """모든 태스크가 끝났는지 확인하고 작업 전체 상태를 업데이트합니다."""
        if all(t.status != TaskStatus.PENDING for t in self.tasks):
            self.status = JobStatus.COMPLETED

    @override
    def __eq__(self, other: object):
        if not isinstance(other, SearchJob):
            return NotImplemented
        return self.job_id == other.job_id

    @override
    def __hash__(self):
        return hash(self.job_id)
