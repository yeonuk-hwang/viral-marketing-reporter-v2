import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QApplication, QMessageBox
from qasync import QEventLoop

from viral_marketing_reporter import bootstrap
from viral_marketing_reporter.domain.events import JobCompleted, TaskCompleted
from viral_marketing_reporter.infrastructure.context import ApplicationContext
from viral_marketing_reporter.infrastructure.message_bus import FunctionHandler
from viral_marketing_reporter.presentation.main_window import MainWindow

# --- 로깅 설정 ---
# (기존 로깅 설정과 동일)
logger.remove()
if sys.stderr:
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | <yellow>{extra}</yellow>",
    )
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
    """전역 예외 처리기"""
    logger.exception("An unexpected error occurred")
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setText("예상치 못한 오류 발생")
    msg_box.setInformativeText(
        f"자세한 내용은 로그 파일을 확인해주세요: {log_file_path}"
    )
    msg_box.setWindowTitle("오류")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()
    QApplication.quit()


async def run_app(app: QApplication):
    """애플리케이션을 설정하고 실행합니다."""
    logger.info("Application starting...")

    context = ApplicationContext()
    await context.__aenter__()

    # 종료 신호를 처리하는 핸들러 설정
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received.")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    # 애플리케이션 초기화
    application = None
    window = None
    try:
        # Bootstrap으로 모든 컴포넌트 초기화
        application = bootstrap.bootstrap(context)

        # UI 설정
        window = MainWindow(
            message_bus=application.bus,
            query_handler=application.query_handler,
            shutdown_event=shutdown_event,
        )
        application.bus.subscribe_to_event(
            JobCompleted, FunctionHandler(window.handle_job_completed)
        )
        application.bus.subscribe_to_event(
            TaskCompleted, FunctionHandler(window.handle_task_completed)
        )
        window.show()

        # 윈도우가 닫히거나 종료 신호를 받으면 종료
        # Note: X 버튼을 누르면 closeEvent에서 os._exit(0)가 호출되어
        # 이 코드에 도달하지 않고 프로세스가 즉시 종료됩니다.
        await shutdown_event.wait()

    finally:
        # 이 블록은 Ctrl+C 등 다른 종료 시그널에서만 실행됩니다
        logger.info("Closing application resources...")

        # Factory cleanup (인증 서비스 등)
        if application and application.factory:
            try:
                await application.factory.cleanup()
            except Exception as e:
                logger.warning(f"Factory cleanup error: {e}")

        # Application context cleanup
        try:
            await context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Context cleanup error: {e}")

        logger.info("Resources closed. Application shutting down.")
        app.quit()


def main():
    """메인 애플리케이션 진입점"""
    sys.excepthook = global_exception_handler
    try:
        app = QApplication(sys.argv)
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_app(app))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application interrupted. Exiting.")
    except Exception:
        logger.exception("Critical error during application startup")
        sys.exit(1)


if __name__ == "__main__":
    main()
