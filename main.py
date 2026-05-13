import os
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Set the application's base directory so it can find assets regardless of where it's run from
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Load stylesheet
    style_path = os.path.join(base_dir, "assets", "style.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError as e:
        print(f"Warning: Could not load stylesheet from {style_path}: {e}", file=sys.stderr)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
