import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QLabel, QVBoxLayout, QHBoxLayout

from jarvis.core.agent import JarvisAgent


@dataclass
class Conversation:
    user: str
    assistant: str


class GlassPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 30, 30)
        p.fillPath(path, QColor(120, 145, 175, 48))
        p.setPen(QPen(QColor(220, 235, 250, 95), 1.2))
        p.drawPath(path)


class ConversationCard(GlassPanel):
    def __init__(self, convo, visibility, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 22, 32, 22)
        layout.setSpacing(10)

        user = QLabel(convo.user)
        user.setAlignment(Qt.AlignRight)
        user.setWordWrap(True)
        answer = QLabel(convo.assistant)
        answer.setWordWrap(True)

        a = int(235 * visibility)
        user.setStyleSheet(f"color: rgba(245,249,255,{a}); font-size: 21px; font-weight: 500;")
        answer.setStyleSheet(f"color: rgba(245,249,255,{a}); font-size: 21px;")
        bg = int(58 * visibility)
        border = int(70 * visibility)
        self.setStyleSheet(
            f"ConversationCard {{ background: rgba(100,125,155,{bg}); "
            f"border: 1px solid rgba(220,235,250,{border}); border-radius: 30px; }}"
        )
        layout.addWidget(user)
        layout.addWidget(answer)


class SearchBar(GlassPanel):
    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(118)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(38, 18, 34, 18)
        layout.setSpacing(20)

        dot = QLabel("●")
        dot.setStyleSheet("color: rgba(125,190,255,220); font-size: 18px;")
        icon = QLabel("⌕")
        icon.setStyleSheet("color: rgba(245,249,255,235); font-size: 48px;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis anything...")
        self.input.setFrame(False)
        self.input.setFont(QFont("Segoe UI Light", 29))
        self.input.setStyleSheet("""
            QLineEdit { color: rgba(245,249,255,235); background: transparent; border: none; }
            QLineEdit::placeholder { color: rgba(235,242,252,150); }
        """)
        self.input.returnPressed.connect(self._submit)
        arrow = QLabel("→")
        arrow.setStyleSheet("color: rgba(245,249,255,215); font-size: 52px;")

        layout.addWidget(dot)
        layout.addWidget(icon)
        layout.addWidget(self.input, 1)
        layout.addWidget(arrow)

    def _submit(self):
        text = self.input.text().strip()
        if text:
            self.submitted.emit(text)
            self.input.clear()


class JarvisWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.agent = JarvisAgent()
        self.overlay = False
        self.conversations = []

        self.setWindowTitle("Jarvis")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)

        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1800, screen.width() - 120), 640)
        self.move(screen.x() + (screen.width() - self.width()) // 2, screen.y() + 90)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        self.history = QVBoxLayout()
        self.history.setSpacing(12)
        self.history_container = QWidget()
        self.history_container.setAttribute(Qt.WA_TranslucentBackground, True)
        self.history_container.setLayout(self.history)

        self.search = SearchBar()
        self.search.submitted.connect(self.submit)
        root.addWidget(self.history_container, 1)
        root.addWidget(self.search)

        self.toggle_shortcut = QShortcut(QKeySequence("Ctrl+Alt+J"), self)
        self.toggle_shortcut.activated.connect(self.toggle_overlay)

        self.set_desktop_mode()
        self.show()

    def set_desktop_mode(self):
        self.overlay = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool |
                            Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnBottomHint)
        self.show()
        self.search.input.clearFocus()

    def set_overlay_mode(self):
        self.overlay = True
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.input.setFocus()

    def toggle_overlay(self):
        self.set_overlay_mode() if not self.overlay else self.set_desktop_mode()

    def submit(self, text):
        self.conversations.append(Conversation(text, "Thinking…"))
        self.conversations = self.conversations[-5:]
        self.rebuild_history()
        QApplication.processEvents()
        try:
            self.conversations[-1].assistant = self.agent.run(text)
        except Exception as exc:
            self.conversations[-1].assistant = f"Jarvis error: {exc}"
        self.rebuild_history()

    def rebuild_history(self):
        while self.history.count():
            item = self.history.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Newest = 100%, then 85%, 70%, 55%, 40%.
        for index, convo in enumerate(reversed(self.conversations)):
            card = ConversationCard(convo, 1.0 - index * 0.15)
            self.history.addWidget(card)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisWindow()
    app._jarvis_window = window
    sys.exit(app.exec())
