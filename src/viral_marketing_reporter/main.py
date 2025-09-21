import asyncio
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QApplication, QMessageBox
from qasync import QEventLoop

from viral_marketing_reporter import bootstrap
from viral_marketing_reporter.application.handlers import GetJobResultQueryHandler
from viral_marketing_reporter.domain.events import JobCompleted
from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.infrastructure.context import ApplicationContext
from viral_marketing_reporter.infrastructure.message_bus import (
    FunctionHandler,
    InMemoryMessageBus,
)
from viral_marketing_reporter.infrastructure.platforms.factory import (
    PlatformServiceFactory,
)
from viral_marketing_reporter.infrastructure.platforms.naver_blog.service import (
    PlaywrightNaverBlogService,
)
from viral_marketing_reporter.infrastructure.uow import InMemoryUnitOfWork
from viral_marketing_reporter.presentation.main_window import MainWindow

# --- 로깅 설정 ---
# 기본 로거 제거
logger.remove()

# 콘솔 로거 (INFO 레벨)
logger.add(
    sys.stderr,
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | <yellow>{extra}</yellow>",
)

# 파일 로거 (DEBUG 레벨) - JSON 형식으로 직렬화
log_file_path = Path.home() / "Downloads" / "viral-reporter" / "debug.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)
logger.add(
    log_file_path,
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    backtrace=True,
    diagnose=True,
    serialize=True,
)


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """전역 예외 처리기: 예상치 못한 오류를 처리하고 사용자에게 알립니다."""
    logger.exception("An unexpected error occurred")
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setText("예상치 못한 오류 발생")
    msg_box.setInformativeText(
        "애플리케이션에 예상치 못한 오류가 발생했습니다.\n"
        f"자세한 내용은 로그 파일을 확인해주세요: {log_file_path}"
    )
    msg_box.setWindowTitle("오류")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()
    QApplication.quit()


async def run_app():
    """애플리케이션을 설정하고 실행합니다."""
    logger.info("Application starting...")
    app = QApplication.instance() or QApplication(sys.argv)

    context = ApplicationContext()
    await context.__aenter__()

    try:
        bus = InMemoryMessageBus()
        uow = InMemoryUnitOfWork(bus)
        factory = PlatformServiceFactory(context)
        factory.register_service(Platform.NAVER_BLOG, PlaywrightNaverBlogService)
        bootstrap.bootstrap(uow=uow, bus=bus, factory=factory)
        query_handler = GetJobResultQueryHandler(uow=uow)
        window = MainWindow(message_bus=bus, query_handler=query_handler)
        bus.subscribe_to_event(
            JobCompleted, FunctionHandler(window.handle_job_completed)
        )
        window.show()
        await window.closing.wait()

    finally:
        logger.info("Closing application resources...")
        await context.__aexit__(None, None, None)
        logger.info("Resources closed. Application shutting down.")
        app.quit()


if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    try:
        app = QApplication(sys.argv)
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_app())
    except Exception:
        logger.exception("Critical error during application startup")
        sys.exit(1)

