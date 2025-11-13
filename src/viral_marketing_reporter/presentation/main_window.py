import asyncio
import os
import time
import uuid

from loguru import logger
from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from viral_marketing_reporter.application.commands import CreateSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import GetJobResultQueryHandler
from viral_marketing_reporter.application.queries import GetJobResultQuery
from viral_marketing_reporter.domain.events import JobCompleted, TaskCompleted
from viral_marketing_reporter.domain.message_bus import MessageBus
from viral_marketing_reporter.domain.model import Platform
from viral_marketing_reporter.presentation.results_dialog import ResultsDialog
from viral_marketing_reporter.presentation.widgets import PastingTableWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        message_bus: MessageBus,
        query_handler: GetJobResultQueryHandler,
        shutdown_event: asyncio.Event,
    ):
        super().__init__()
        self.message_bus = message_bus
        self.query_handler = query_handler
        self.shutdown_event = shutdown_event

        self.current_job_id: uuid.UUID | None = None
        self.total_tasks: int = 0
        self.completed_tasks: int = 0
        self.search_start_time: float | None = None
        self.results_dialog: ResultsDialog | None = None
        self.current_platform: Platform | None = None  # 현재 실행 중인 플랫폼

        self.setWindowTitle("Viral Marketing Reporter")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet(
            """
            QMainWindow { background-color: #f8f9fa; }
            QLabel { font-size: 14px; }
            QPushButton {
                background-color: #007bff; color: white; border-radius: 5px;
                padding: 10px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
            QTableWidget {
                border: 1px solid #dee2e6; gridline-color: #dee2e6; font-size: 14px;
            }
            QHeaderView::section {
                background-color: #e9ecef; padding: 4px; border: 1px solid #dee2e6;
                font-size: 14px; font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #bdc3c7; border-radius: 5px; text-align: center;
                font-size: 14px;
            }
            QProgressBar::chunk { background-color: #2ecc71; }
            """
        )

        # --- Layouts ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("Viral Marketing Reporter")
        title_font = title_label.font()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Platform Selection Buttons
        platform_button_layout = QHBoxLayout()
        platform_button_layout.setSpacing(10)

        self.naver_blog_button = QPushButton("네이버 블로그 검색 시작")
        self.naver_blog_button.clicked.connect(lambda: self.run_search(Platform.NAVER_BLOG))
        platform_button_layout.addWidget(self.naver_blog_button)

        self.instagram_button = QPushButton("Instagram 검색 시작")
        self.instagram_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f09433, stop:0.25 #e6683c,
                    stop:0.5 #dc2743, stop:0.75 #cc2366,
                    stop:1 #bc1888);
                color: white; border-radius: 5px;
                padding: 10px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #d17a2a, stop:0.25 #c75933,
                    stop:0.5 #bd1e3a, stop:0.75 #ad1d57,
                    stop:1 #9d0f6f);
            }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
            """
        )
        self.instagram_button.clicked.connect(lambda: self.run_search(Platform.INSTAGRAM))
        platform_button_layout.addWidget(self.instagram_button)

        main_layout.addLayout(platform_button_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        input_label = QLabel(
            "검색할 키워드와 URL을 입력하세요 (Excel에서 복사-붙여넣기 가능)"
        )
        main_layout.addWidget(input_label)

        self.input_table = PastingTableWidget(10, 2)
        self.input_table.setHorizontalHeaderLabels(["키워드", "확인할 URL"])
        self.input_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        # 더블클릭 또는 선택된 셀에서 키를 누르면 편집 모드로 진입합니다.
        # 이를 통해 한글 입력 시 자모 분리 문제를 방지합니다.
        self.input_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        main_layout.addWidget(self.input_table)

        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        self.clear_button = QPushButton("전체 초기화")
        self.clear_button.setStyleSheet(
            "QPushButton { background-color: #6c757d; max-width: 120px; }"
            "QPushButton:hover { background-color: #5a6268; }"
        )
        self.clear_button.clicked.connect(self.clear_input_table)
        button_layout.addWidget(self.clear_button)
        main_layout.addLayout(button_layout)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event.

        Immediately terminates the process to avoid Qt thread cleanup issues.
        This prevents the "QThread: Destroyed while thread is still running" error
        that occurs when Qt tries to clean up qasync worker threads.
        """
        logger.info("Close event received. Terminating process...")
        # Accept the event
        event.accept()
        # Immediately exit the process without cleanup
        # This avoids Qt trying to destroy threads that are still running
        os._exit(0)

    @Slot()
    def clear_input_table(self):
        self.input_table.clearContents()
        self.input_table.setRowCount(10)

    @asyncSlot()
    async def run_search(self, platform: Platform):
        logger.info(f"'Run Search' button clicked for platform: {platform.value}")
        self.search_start_time = time.monotonic()
        self.current_platform = platform

        # 현재 편집 중인 셀의 내용을 커밋합니다.
        # Enter 키 이벤트를 전송하여 편집을 완료하고 내용을 커밋합니다.
        if self.input_table.state() == QAbstractItemView.State.EditingState:
            from PySide6.QtCore import QEvent
            from PySide6.QtGui import QKeyEvent

            # Enter 키 이벤트 생성 및 전송
            key_event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier
            )
            QApplication.sendEvent(self.input_table, key_event)
            QApplication.processEvents()

        keywords, urls = [], []
        for row in range(self.input_table.rowCount()):
            k_item = self.input_table.item(row, 0)
            if k_item and k_item.text():
                keywords.append(k_item.text().strip())
            u_item = self.input_table.item(row, 1)
            if u_item and u_item.text():
                urls.append(u_item.text().strip())

        if not keywords or not urls:
            logger.warning("No valid keywords or URLs found.")
            return

        task_dtos = [
            TaskDTO(index=i + 1, keyword=k, urls=urls, platform=platform)
            for i, k in enumerate(keywords)
        ]

        self.total_tasks = len(task_dtos)
        self.completed_tasks = 0
        self.progress_bar.setMaximum(self.total_tasks)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"0 / {self.total_tasks} 완료")
        self.progress_bar.setVisible(True)

        self.current_job_id = uuid.uuid4()
        command = CreateSearchCommand(job_id=self.current_job_id, tasks=task_dtos)

        # 플랫폼에 따라 버튼 상태 업데이트
        if platform == Platform.NAVER_BLOG:
            self.naver_blog_button.setText("검색 중...")
            self.naver_blog_button.setEnabled(False)
            self.instagram_button.setEnabled(False)
        elif platform == Platform.INSTAGRAM:
            self.instagram_button.setText("검색 중...")
            self.instagram_button.setEnabled(False)
            self.naver_blog_button.setEnabled(False)

        logger.debug(f"UI state updated to 'searching' for {platform.value}.")

        logger.info(
            f"Creating search job {self.current_job_id} with {self.total_tasks} tasks for {platform.value}."
        )
        await self.message_bus.handle(command)

    @asyncSlot()
    async def handle_task_completed(self, event: TaskCompleted):
        if event.job_id == self.current_job_id:
            self.completed_tasks += 1
            self.progress_bar.setValue(self.completed_tasks)
            self.progress_bar.setFormat(
                f"{self.completed_tasks} / {self.total_tasks} 완료"
            )
            logger.debug(f"Progress: {self.completed_tasks}/{self.total_tasks}")

    @asyncSlot()
    async def handle_job_completed(self, event: JobCompleted):
        logger.info(f"Handling JobCompleted event for job {event.job_id}.")
        if event.job_id != self.current_job_id:
            logger.warning(f"Received event for an old job {event.job_id}. Ignoring.")
            return

        elapsed_seconds = (
            time.monotonic() - self.search_start_time
            if self.search_start_time
            else None
        )

        self.progress_bar.setVisible(False)

        # 플랫폼에 따라 버튼 복원
        if self.current_platform == Platform.NAVER_BLOG:
            self.naver_blog_button.setText("네이버 블로그 검색 시작")
            self.naver_blog_button.setEnabled(True)
            self.instagram_button.setEnabled(True)
        elif self.current_platform == Platform.INSTAGRAM:
            self.instagram_button.setText("Instagram 검색 시작")
            self.instagram_button.setEnabled(True)
            self.naver_blog_button.setEnabled(True)

        result_dto = await self.query_handler.handle(
            GetJobResultQuery(job_id=event.job_id)
        )
        if not result_dto:
            logger.error(f"Could not retrieve results for job {event.job_id}.")
            return

        logger.debug(f"Populating UI with results for {len(result_dto.tasks)} tasks.")
        self.results_dialog = ResultsDialog(
            result_dto,
            self,
            elapsed_seconds=elapsed_seconds,
            total_tasks=self.total_tasks,
        )
        self.results_dialog.exec()
        logger.info(f"Search job {event.job_id} completed and results shown.")
