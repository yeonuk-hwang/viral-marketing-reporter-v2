from dataclasses import dataclass
import uuid

# 1. Queries
class Query:
    """Marker class for queries."""
    pass

@dataclass(frozen=True)
class GetJobResultQuery(Query):
    job_id: uuid.UUID

# 2. Result DTOs (Data Transfer Objects)
@dataclass(frozen=True)
class TaskResultDTO:
    keyword: str
    status: str
    found_post_urls: list[str]
    screenshot_path: str | None
    error_message: str | None

@dataclass(frozen=True)
class JobResultDTO:
    job_id: uuid.UUID
    status: str
    tasks: list[TaskResultDTO]
