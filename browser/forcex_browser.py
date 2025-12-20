import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtCore import QUrl


class ForceX(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window config
        self.setWindowTitle("ForceX Secure Browser")
        self.setGeometry(100, 100, 1200, 800)

        # Web view
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        # Block downloads
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.block_download)

        # 🔒 Load only allowed page (Canva for now)
        self.view.load(QUrl("https://www.canva.com"))

    def block_download(self, download):
        print("🚫 Download blocked by ForceX")
        download.cancel()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ForceX()
    window.show()
    sys.exit(app.exec())
