import asyncio
import uuid

from loguru import logger
from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from viral_marketing_reporter.application.commands import CreateSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import GetJobResultQueryHandler
from viral_marketing_reporter.application.queries import GetJobResultQuery
from viral_marketing_reporter.domain.events import JobCompleted
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
        self.current_job_id: uuid.UUID | None = None
        self.shutdown_event = shutdown_event
        self.results_dialog: ResultsDialog | None = None

        self.setWindowTitle("Viral Marketing Reporter")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f8f9fa;
            }
            QLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTableWidget {
                border: 1px solid #dee2e6;
                gridline-color: #dee2e6;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 4px;
                border: 1px solid #dee2e6;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )

        # --- Layouts ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("Viral Marketing Reporter")
        title_font = title_label.font()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Platform Button (Search Trigger)
        self.naver_blog_button = QPushButton("네이버 블로그 검색 시작")
        self.naver_blog_button.clicked.connect(self.run_search)
        main_layout.addWidget(self.naver_blog_button)

        # Input Area
        input_label = QLabel("검색할 키워드와 URL을 입력하세요 (Excel에서 복사-붙여넣기 가능)")
        main_layout.addWidget(input_label)

        self.input_table = PastingTableWidget(10, 2)
        self.input_table.setHorizontalHeaderLabels(["키워드", "확인할 URL"])
        self.input_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        # 더블클릭 시 편집 가능하도록 설정
        self.input_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
        )
        main_layout.addWidget(self.input_table)

        # Clear Button
        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        self.clear_button = QPushButton("전체 초기화")
        self.clear_button.setStyleSheet(
            """
            QPushButton {
                background-color: #6c757d;
                max-width: 120px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            """
        )
        self.clear_button.clicked.connect(self.clear_input_table)
        button_layout.addWidget(self.clear_button)
        main_layout.addLayout(button_layout)

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("Close event received. Initiating shutdown.")
        self.shutdown_event.set()
        event.accept()

    @Slot()
    def clear_input_table(self):
        self.input_table.clearContents()
        self.input_table.setRowCount(10) # 기본 행 수 유지

    @asyncSlot()
    async def run_search(self):
        logger.info("'Run Search' button clicked.")

        keywords, urls = [], []
        for row in range(self.input_table.rowCount()):
            keyword_item = self.input_table.item(row, 0)
            if keyword_item and keyword_item.text():
                keywords.append(keyword_item.text().strip())

            url_item = self.input_table.item(row, 1)
            if url_item and url_item.text():
                urls.append(url_item.text().strip())

        keywords, urls = sorted(list(set(keywords))), sorted(list(set(urls)))

        if not keywords or not urls:
            logger.warning("No valid keywords or URLs found in the input table.")
            return

        task_dtos = [
            TaskDTO(keyword=keyword, urls=urls, platform=Platform.NAVER_BLOG)
            for keyword in keywords
        ]

        self.current_job_id = uuid.uuid4()
        command = CreateSearchCommand(job_id=self.current_job_id, tasks=task_dtos)

        self.naver_blog_button.setText("검색 중...")
        self.naver_blog_button.setEnabled(False)
        logger.debug("UI state updated to 'searching'.")

        logger.info(
            f"Creating search job {self.current_job_id} with {len(task_dtos)} tasks."
        )
        await self.message_bus.handle(command)

    @asyncSlot()
    async def handle_job_completed(self, event: JobCompleted):
        logger.info(f"Handling JobCompleted event for job {event.job_id}.")
        if event.job_id != self.current_job_id:
            logger.warning(f"Received event for an old job {event.job_id}. Ignoring.")
            return

        result_dto = await self.query_handler.handle(
            GetJobResultQuery(job_id=event.job_id)
        )
        
        self.naver_blog_button.setText("네이버 블로그 검색 시작")
        self.naver_blog_button.setEnabled(True)

        if not result_dto:
            logger.error(f"Could not retrieve results for job {event.job_id}.")
            return

        logger.debug(f"Populating UI with results for {len(result_dto.tasks)} tasks.")
        self.results_dialog = ResultsDialog(result_dto, self)
        self.results_dialog.exec()
        logger.info(f"Search job {event.job_id} completed and results shown.")
