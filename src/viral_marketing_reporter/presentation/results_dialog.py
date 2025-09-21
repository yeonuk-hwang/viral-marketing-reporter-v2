import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from viral_marketing_reporter.application.queries import JobResultDTO
from viral_marketing_reporter.domain.model import TaskStatus


class ResultsDialog(QDialog):
    """검색 결과를 모달 대화상자로 표시하는 위젯"""

    def __init__(
        self,
        result_dto: JobResultDTO,
        parent=None,
        elapsed_seconds: float | None = None,
        total_tasks: int = 0,
    ):
        super().__init__(parent)
        self.result_dto = result_dto
        self.screenshot_folder: Path | None = None
        self.setWindowTitle("검색 결과")
        self.setMinimumSize(800, 400)

        layout = QVBoxLayout(self)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(
            ["키워드", "상위 노출 포함 여부", "스크린샷"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.cellClicked.connect(self.open_screenshot)

        self.populate_results()

        layout.addWidget(self.results_table)

        # 총 소요시간 표시
        if elapsed_seconds is not None and total_tasks > 0:
            actual_time_label = QLabel(
                f"총 {total_tasks}개 키워드 검색 완료 ({elapsed_seconds:.2f}초 소요)"
            )
            actual_time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(actual_time_label)

        self.button_box = QDialogButtonBox()
        self.open_folder_button = QPushButton("스크린샷 폴더 열기")
        self.open_folder_button.clicked.connect(self.open_screenshot_folder)
        self.open_folder_button.setEnabled(self.screenshot_folder is not None)

        self.button_box.addButton(
            self.open_folder_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.button_box.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.accepted.connect(self.accept)
        layout.addWidget(self.button_box)

    def populate_results(self):
        """결과 DTO를 사용하여 테이블을 채웁니다."""
        self.results_table.setRowCount(len(self.result_dto.tasks))
        for row, task in enumerate(self.result_dto.tasks):
            keyword_item = QTableWidgetItem(task.keyword)
            status_item = QTableWidgetItem()

            if task.status == TaskStatus.FOUND.value:
                status_item.setText("포함")
                status_item.setForeground(Qt.GlobalColor.blue)
            elif task.status == TaskStatus.NOT_FOUND.value:
                status_item.setText("미포함")
                status_item.setForeground(Qt.GlobalColor.red)
            elif task.status == TaskStatus.ERROR.value:
                error_msg = task.error_message or "알 수 없는 오류"
                status_item.setText(f"에러 발생")
                status_item.setToolTip(error_msg)
                status_item.setForeground(Qt.GlobalColor.red)

            screenshot_item = QTableWidgetItem(task.screenshot_path or "N/A")
            if task.screenshot_path:
                if self.screenshot_folder is None:
                    self.screenshot_folder = Path(task.screenshot_path).parent

                font = screenshot_item.font()
                font.setUnderline(True)
                screenshot_item.setFont(font)
                screenshot_item.setForeground(Qt.GlobalColor.blue)

            self.results_table.setItem(row, 0, keyword_item)
            self.results_table.setItem(row, 1, status_item)
            self.results_table.setItem(row, 2, screenshot_item)

    @Slot(int, int)
    def open_screenshot(self, row: int, column: int):
        if column == 2:
            item = self.results_table.item(row, column)
            if item and item.text() != "N/A":
                file_path = Path(item.text())
                if file_path.exists():
                    webbrowser.open(file_path.as_uri())

    @Slot()
    def open_screenshot_folder(self):
        if self.screenshot_folder and self.screenshot_folder.exists():
            webbrowser.open(self.screenshot_folder.as_uri())