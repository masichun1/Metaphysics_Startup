"""Entry point for the cat desktop pet."""
import os
import sys

from PySide6.QtWidgets import QApplication

from pet.window import PetWindow


def resource_path(rel):
    """Resolve a path that works both from source and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = PetWindow(
        resource_path(os.path.join("assets", "cat_open.png")),
        resource_path(os.path.join("assets", "cat_closed.png")),
        height=300,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
