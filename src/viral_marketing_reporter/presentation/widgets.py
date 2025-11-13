from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem


class PastingTableWidget(QTableWidget):
    """엑셀과 같은 외부 소스에서 붙여넣기 기능을 지원하는 테이블 위젯"""

    def keyPressEvent(self, event: QKeyEvent):
        # 붙여넣기 단축키가 아닌 경우, 기본 동작을 먼저 수행합니다.
        # 이를 통해 한글 입력 시 IME가 정상적으로 작동하도록 합니다.
        if not event.matches(QKeySequence.StandardKey.Paste):
            super().keyPressEvent(event)
            return

        # 붙여넣기 처리
        clipboard = QApplication.clipboard()
        text = clipboard.text()

        rows = text.strip().split("\n")
        if not rows:
            return

        # 붙여넣기를 시작할 셀을 가져옵니다.
        start_row = self.currentRow()
        start_col = self.currentColumn()

        for i, row_text in enumerate(rows):
            # 탭으로 열을 구분합니다.
            columns = row_text.split("\t")
            current_row = start_row + i

            # 행이 부족하면 새로 추가합니다.
            if current_row >= self.rowCount():
                self.insertRow(current_row)

            for j, cell_text in enumerate(columns):
                current_col = start_col + j
                if current_col < self.columnCount():
                    self.setItem(
                        current_row,
                        current_col,
                        QTableWidgetItem(cell_text)
                    )

