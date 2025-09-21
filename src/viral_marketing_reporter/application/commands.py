import uuid
from dataclasses import dataclass

from viral_marketing_reporter.domain.model import Platform


class Command:
    """모든 커맨드의 기본 클래스 (마커 역할)"""

    pass


@dataclass(frozen=True)
class TaskDTO:
    """UI에서 전달되는 개별 작업 데이터"""

    keyword: str
    urls: list[str]
    platform: Platform


@dataclass(frozen=True)
class CreateSearchCommand(Command):
    """검색 생성을 요청하는 커맨드"""

    job_id: uuid.UUID
    tasks: list[TaskDTO]


@dataclass(frozen=True)
class ExecuteSearchTaskCommand(Command):
    """개별 검색 태스크 실행을 요청하는 커맨드"""

    job_id: uuid.UUID
    task_id: uuid.UUID
