import uuid
from dataclasses import dataclass
from datetime import datetime


class Event:
    """모든 도메인 이벤트의 기본 클래스 (마커 인터페이스 역할)"""

    pass


@dataclass(frozen=True)
class SearchJobCreated(Event):
    """SearchJob이 생성되었을 때 발생하는 이벤트"""

    job_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True)
class SearchJobStarted(Event):
    """SearchJob이 실행 상태로 변경되었을 때 발생하는 이벤트"""

    job_id: uuid.UUID


@dataclass(frozen=True)
class TaskCompleted(Event):
    """개별 Task가 완료되었을 때 발생하는 이벤트"""

    task_id: uuid.UUID
    job_id: uuid.UUID
    status: str  # FOUND, NOT_FOUND, ERROR


@dataclass(frozen=True)
class JobCompleted(Event):
    """SearchJob의 모든 태스크가 완료되었을 때 발생하는 이벤트"""

    job_id: uuid.UUID