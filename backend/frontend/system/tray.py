from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import (
    QAction,
    QIcon,
    QPixmap,
    QPainter,
    QFont,
)
from PySide6.QtWidgets import (
    QMenu,
    QSystemTrayIcon,
)


class JarvisTray(QObject):

    def __init__(self, controller, parent=None):
        super().__init__(parent)

        self.controller = controller

        # --------------------------------------------------
        # Tray icon
        # --------------------------------------------------

        self.tray = QSystemTrayIcon(
            self._create_icon(),
            self
        )

        self.tray.setToolTip(
            "Jarvis"
        )

        # --------------------------------------------------
        # Menu
        # --------------------------------------------------

        self.menu = QMenu()

        self.title_action = QAction(
            "Jarvis",
            self.menu
        )

        self.title_action.setEnabled(
            False
        )

        self.menu.addAction(
            self.title_action
        )

        self.menu.addSeparator()

        # --------------------------------------------------
        # Enabled / Disabled
        # --------------------------------------------------

        self.toggle_action = QAction(
            "● Jarvis Disabled",
            self.menu
        )

        self.toggle_action.triggered.connect(
            self._toggle_jarvis
        )

        self.menu.addAction(
            self.toggle_action
        )

        self.menu.addSeparator()

        # --------------------------------------------------
        # Exit
        # --------------------------------------------------

        self.exit_action = QAction(
            "Exit Jarvis",
            self.menu
        )

        self.exit_action.triggered.connect(
            self._exit_jarvis
        )

        self.menu.addAction(
            self.exit_action
        )

        self.tray.setContextMenu(
            self.menu
        )

        # --------------------------------------------------
        # Controller state
        # --------------------------------------------------

        self.controller.state_changed.connect(
            self._on_state_changed
        )

        self._on_state_changed(
            self.controller.enabled
        )

    # ======================================================
    # ICON
    # ======================================================

    def _create_icon(self):

        pixmap = QPixmap(
            64,
            64
        )

        pixmap.fill(
            Qt.transparent
        )

        painter = QPainter(
            pixmap
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.setPen(
            Qt.white
        )

        painter.setFont(
            QFont(
                "Segoe UI",
                42,
                QFont.Bold
            )
        )

        painter.drawText(
            pixmap.rect(),
            Qt.AlignCenter,
            "J"
        )

        painter.end()

        return QIcon(
            pixmap
        )

    # ======================================================
    # TOGGLE
    # ======================================================

    def _toggle_jarvis(self):

        self.controller.toggle()

    # ======================================================
    # EXIT / MASTER TOGGLE
    # ======================================================

    def _exit_jarvis(self):

        print(
            "[Tray] Master shutdown requested."
        )

        self.controller.stop()

    # ======================================================
    # STATE
    # ======================================================

    def _on_state_changed(self, enabled):

        if enabled:

            self.toggle_action.setText(
                "● Jarvis Enabled"
            )

        else:

            self.toggle_action.setText(
                "● Jarvis Disabled"
            )

    # ======================================================
    # SHOW
    # ======================================================

    def show(self):

        self.tray.show()

    # ======================================================
    # HIDE
    # ======================================================

    def hide(self):

        self.tray.hide()