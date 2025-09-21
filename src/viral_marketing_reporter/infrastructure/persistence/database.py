
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from viral_marketing_reporter.infrastructure.persistence.orm import metadata

# 전역 변수로 엔진과 세션 팩토리를 관리합니다.
# 실제 애플리케이션에서는 설정 파일 등에서 DB 경로를 관리하는 것이 좋습니다.
_engine = None
_session_factory = None

def get_engine(db_path: str = "sqlite:///viral_reporter.db", echo: bool = False):
    """SQLAlchemy 엔진을 생성하고 반환합니다."""
    global _engine
    if _engine is None:
        _engine = create_engine(db_path, echo=echo)
    return _engine

def get_session_factory(engine=None):
    """세션 팩토리를 생성하고 반환합니다."""
    global _session_factory
    if _session_factory is None:
        if engine is None:
            engine = get_engine()
        _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _session_factory

def create_tables(engine=None):
    """메타데이터에 정의된 모든 테이블을 생성합니다."""
    if engine is None:
        engine = get_engine()
    metadata.create_all(engine)

def drop_tables(engine=None):
    """메타데이터에 정의된 모든 테이블을 삭제합니다."""
    if engine is None:
        engine = get_engine()
    metadata.drop_all(engine)
