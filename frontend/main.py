import sys

from PySide6.QtWidgets import QApplication

from windows.main_window import MainWindow
from jarvis_controller import JarvisController


def main():
    app = QApplication(sys.argv)

    window = MainWindow()

    # Connect the main window to the Jarvis controller.
    controller = JarvisController(window)
    window.jarvis_controller = controller

    # Show the interface first.
    window.show()

    # Start Jarvis.
    controller.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()