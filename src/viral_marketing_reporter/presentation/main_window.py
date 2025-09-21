import asyncio
import uuid
from collections import defaultdict

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from viral_marketing_reporter.application.commands import CreateSearchCommand, TaskDTO
from viral_marketing_reporter.application.handlers import GetJobResultQueryHandler
from viral_marketing_reporter.application.queries import GetJobResultQuery
from viral_marketing_reporter.domain.events import JobCompleted
from viral_marketing_reporter.domain.message_bus import MessageBus
from viral_marketing_reporter.domain.model import Platform, TaskStatus
from viral_marketing_reporter.presentation.widgets import PastingTableWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        message_bus: MessageBus,
        query_handler: GetJobResultQueryHandler,
    ):
        super().__init__()
        self.message_bus = message_bus
        self.query_handler = query_handler
        self.current_job_id: uuid.UUID | None = None
        self.closing = asyncio.Event()

        self.setWindowTitle("Viral Marketing Reporter")
        self.setGeometry(100, 100, 1200, 800)

        main_layout = QVBoxLayout()
        platform_layout = QHBoxLayout()
        self.naver_blog_button = QPushButton("네이버 블로그")
        self.naver_blog_button.setCheckable(True)
        self.naver_blog_button.setChecked(True)
        platform_layout.addWidget(QLabel("플랫폼 선택:"))
        platform_layout.addWidget(self.naver_blog_button)
        platform_layout.addStretch()
        main_layout.addLayout(platform_layout)

        main_layout.addWidget(QLabel("검색할 키워드와 URL을 입력하세요 (Excel에서 복사-붙여넣기 가능)"))
        self.input_table = PastingTableWidget(10, 2)
        self.input_table.setHorizontalHeaderLabels(["키워드", "확인할 URL"])
        self.input_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        main_layout.addWidget(self.input_table)

        self.run_button = QPushButton("검색 실행")
        self.run_button.clicked.connect(self.run_search)
        main_layout.addWidget(self.run_button)

        main_layout.addWidget(QLabel("검색 결과"))
        self.output_table = QTableWidget(0, 4)
        self.output_table.setHorizontalHeaderLabels(
            ["키워드", "순위 내 포함", "노출된 포스트 URL", "스크린샷"]
        )
        self.output_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        main_layout.addWidget(self.output_table)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def closeEvent(self, event: QCloseEvent) -> None:
        """창 닫기 이벤트를 가로채어 안전한 종료를 준비합니다."""
        self.closing.set()
        event.ignore()  # 즉시 닫히는 것을 막음

    @asyncSlot()
    async def run_search(self):
        """UI에서 입력받은 정보로 CreateSearchCommand를 생성하고 메시지 버스에 전달합니다."""
        task_dtos = []
        for row in range(self.input_table.rowCount()):
            keyword_item = self.input_table.item(row, 0)
            url_item = self.input_table.item(row, 1)
            if keyword_item and keyword_item.text() and url_item and url_item.text():
                keyword = keyword_item.text().strip()
                url = url_item.text().strip()
                # 각 행을 개별 TaskDTO로 만듭니다.
                task_dtos.append(
                    TaskDTO(keyword=keyword, urls=[url], platform=Platform.NAVER_BLOG)
                )

        if not task_dtos:
            print("No data to search.")
            return

        self.output_table.setRowCount(0)
        self.current_job_id = uuid.uuid4()
        command = CreateSearchCommand(job_id=self.current_job_id, tasks=task_dtos)

        await self.message_bus.handle(command)

        self.run_button.setText("검색 중...")
        self.run_button.setEnabled(False)

    @asyncSlot()
    async def handle_job_completed(self, event: JobCompleted):
        """JobCompleted 이벤트를 처리하여 쿼리로 최종 결과를 가져와 UI에 표시합니다."""
        if event.job_id != self.current_job_id:
            return

        result_dto = await self.query_handler.handle(
            GetJobResultQuery(job_id=event.job_id)
        )
        if not result_dto:
            self.run_button.setText("검색 실행")
            self.run_button.setEnabled(True)
            return

        self.output_table.setRowCount(0)
        for task_result in result_dto.tasks:
            if task_result.status == TaskStatus.FOUND.value:
                for found_url in task_result.found_post_urls:
                    row_position = self.output_table.rowCount()
                    self.output_table.insertRow(row_position)
                    self.output_table.setItem(
                        row_position, 0, QTableWidgetItem(task_result.keyword)
                    )
                    self.output_table.setItem(row_position, 1, QTableWidgetItem("Y"))
                    self.output_table.setItem(
                        row_position, 2, QTableWidgetItem(found_url)
                    )
                    self.output_table.setItem(
                        row_position, 3, QTableWidgetItem(task_result.screenshot_path)
                    )
            else:
                row_position = self.output_table.rowCount()
                self.output_table.insertRow(row_position)
                self.output_table.setItem(
                    row_position, 0, QTableWidgetItem(task_result.keyword)
                )
                self.output_table.setItem(row_position, 1, QTableWidgetItem("N"))
                status_message = (
                    f"ERROR: {task_result.error_message}"
                    if task_result.status == TaskStatus.ERROR.value
                    else "-"
                )
                self.output_table.setItem(
                    row_position, 2, QTableWidgetItem(status_message)
                )
                self.output_table.setItem(row_position, 3, QTableWidgetItem("-"))

        self.run_button.setText("검색 실행")
        self.run_button.setEnabled(True)
        print("Search completed and UI updated!")