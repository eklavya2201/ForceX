import ctypes
import os
import sys
from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow, QMessageBox, QToolBar
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtCore import Qt, QUrl

load_dotenv()
FORCEX_URL = QUrl(os.getenv("FORCEX_URL", "http://127.0.0.1:5000"))
CLIENT_KEY = os.getenv("FORCEX_CLIENT_KEY", "")

# Windows 10 2004+: the window renders as black in screenshots, Snipping Tool,
# screen recorders and screen sharing. It cannot stop a camera pointed at the screen.
WDA_EXCLUDEFROMCAPTURE = 0x11


def exclude_from_capture(window):
    if sys.platform != "win32":
        return False
    return bool(ctypes.windll.user32.SetWindowDisplayAffinity(int(window.winId()), WDA_EXCLUDEFROMCAPTURE))


def is_forcex(url):
    return url.host() == FORCEX_URL.host() and url.port() == FORCEX_URL.port()


class ClientKeyInterceptor(QWebEngineUrlRequestInterceptor):
    # The server only serves shared content to requests carrying this header.
    def interceptRequest(self, info):
        if is_forcex(info.requestUrl()):
            info.setHttpHeader(b"X-ForceX-Client", CLIENT_KEY.encode())


class LockedPage(QWebEnginePage):
    # Only the ForceX server may be opened; everything else is refused.
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() in ("data", "blob") or is_forcex(url):
            return True
        print(f"🚫 Navigation blocked by ForceX: {url.toString()}")
        return False

    def createWindow(self, window_type):
        return None


class ForceX(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window config
        self.setWindowTitle("ForceX Secure Browser")
        self.setGeometry(100, 100, 1200, 800)

        # Web view
        self.view = QWebEngineView(self)
        self.view.setPage(LockedPage(self.view))
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self.setCentralWidget(self.view)

        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, False)
        settings.setAttribute(QWebEngineSettings.ScreenCaptureEnabled, False)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)

        # Link bar: receivers paste the share link they were sent
        self.address = QLineEdit(self)
        self.address.setPlaceholderText("Paste a ForceX share link and press Enter")
        self.address.returnPressed.connect(self.open_address)
        bar = QToolBar(self)
        bar.setMovable(False)
        bar.addWidget(self.address)
        self.addToolBar(bar)
        self.view.urlChanged.connect(lambda url: self.address.setText(url.toString()))

        # Block downloads
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.block_download)
        self.interceptor = ClientKeyInterceptor(self)
        profile.setUrlRequestInterceptor(self.interceptor)

        # Block printing: QtWebEngine only prints when these signals are handled,
        # so logging instead of printing covers Ctrl+P, window.print() and the PDF viewer.
        page = self.view.page()
        page.printRequested.connect(lambda: print("🚫 Print blocked by ForceX"))
        if hasattr(page, "printRequestedByFrame"):
            page.printRequestedByFrame.connect(lambda frame: print("🚫 Print blocked by ForceX"))

        start = QUrl(sys.argv[1]) if len(sys.argv) > 1 else FORCEX_URL
        self.view.load(start if is_forcex(start) else FORCEX_URL)

    def open_address(self):
        url = QUrl.fromUserInput(self.address.text().strip())
        if is_forcex(url):
            self.view.load(url)
        else:
            QMessageBox.warning(self, "ForceX", f"Only links from {FORCEX_URL.host()} can be opened.")

    def block_download(self, download):
        print("🚫 Download blocked by ForceX")
        download.cancel()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if not CLIENT_KEY:
        QMessageBox.critical(None, "ForceX", "FORCEX_CLIENT_KEY is not set. Ask the sender for the ForceX client settings.")
        sys.exit(1)
    window = ForceX()
    window.show()
    if not exclude_from_capture(window):
        QMessageBox.critical(window, "ForceX", "Screen-capture protection is unavailable on this system. ForceX will close.")
        sys.exit(1)
    sys.exit(app.exec())
