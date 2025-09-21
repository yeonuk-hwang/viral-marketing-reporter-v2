
from dataclasses import dataclass
from datetime import datetime


class Event:
    """모든 도메인 이벤트의 기본 클래스 (마커 인터페이스 역할)"""

    pass


@dataclass(frozen=True)
class SearchJobCreated(Event):
    """SearchJob이 생성되었을 때 발생하는 이벤트"""

    job_id: str
    created_at: datetime


@dataclass(frozen=True)
class TaskCompleted(Event):
    """개별 Task가 완료되었을 때 발생하는 이벤트"""

    task_id: str
    job_id: str
    status: str  # FOUND, NOT_FOUND, ERROR
