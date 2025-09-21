import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from viral_marketing_reporter.application.queries import JobResultDTO
from viral_marketing_reporter.domain.model import TaskStatus


class ResultsDialog(QDialog):
    """검색 결과를 모달 대화상자로 표시하는 위젯"""

    def __init__(self, result_dto: JobResultDTO, parent=None):
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

        self.button_box = QDialogButtonBox()
        self.open_folder_button = QPushButton("스크린샷 폴더 열기")
        self.open_folder_button.clicked.connect(self.open_screenshot_folder)
        # 스크린샷 폴더가 없으면 버튼 비활성화
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
                status_item.setToolTip(error_msg) # 툴팁으로 전체 에러 메시지 표시
                status_item.setForeground(Qt.GlobalColor.red)

            screenshot_item = QTableWidgetItem(task.screenshot_path or "N/A")
            if task.screenshot_path:
                # 첫 스크린샷 경로에서 부모 폴더를 저장
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
        """스크린샷 열을 클릭했을 때 파일을 엽니다."""
        if column == 2:  # 스크린샷 열
            item = self.results_table.item(row, column)
            if item and item.text() != "N/A":
                file_path = Path(item.text())
                if file_path.exists():
                    webbrowser.open(file_path.as_uri())

    @Slot()
    def open_screenshot_folder(self):
        """스크린샷 폴더 열기 버튼을 클릭했을 때 폴더를 엽니다."""
        if self.screenshot_folder and self.screenshot_folder.exists():
            webbrowser.open(self.screenshot_folder.as_uri())