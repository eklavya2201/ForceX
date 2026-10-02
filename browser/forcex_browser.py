import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
import webview

# Settings come from the environment, then forcex.env beside the .exe (or .env when run from source),
# then the values build_desktop.py bakes into the .exe.
try:
    from browser import _baked
except ImportError:
    try:
        import _baked
    except ImportError:
        _baked = None

if getattr(sys, "frozen", False):
    load_dotenv(os.path.join(os.path.dirname(sys.executable), "forcex.env"))
else:
    load_dotenv()
FORCEX_URL = os.getenv("FORCEX_URL", getattr(_baked, "FORCEX_URL", "http://127.0.0.1:5000")).rstrip("/")
CLIENT_KEY = os.getenv("FORCEX_CLIENT_KEY", getattr(_baked, "FORCEX_CLIENT_KEY", ""))
print(f"DEBUG Startup: URL={FORCEX_URL}, KEY_LEN={len(CLIENT_KEY)}")

WDA_EXCLUDEFROMCAPTURE = 0x11
_webview_handlers = []


def _origin(url):
    try:
        parsed = urlsplit(str(url))
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        return parsed.scheme.lower(), parsed.hostname.lower(), port
    except ValueError:
        return None


def is_forcex(url):
    return _origin(url) is not None and _origin(url) == _origin(FORCEX_URL)


def _browser_shell_url(start_url):
    parsed = urlsplit(FORCEX_URL)
    return urlunsplit((parsed.scheme, parsed.netloc, "/client", urlencode({"url": start_url}), ""))


def _configure_webview2(control):
    core = control.CoreWebView2
    if core is None:
        return

    settings = core.Settings
    settings.AreBrowserAcceleratorKeysEnabled = False
    settings.AreDefaultContextMenusEnabled = False
    settings.AreDevToolsEnabled = False
    settings.IsStatusBarEnabled = False
    settings.IsZoomControlEnabled = False

    def set_client_headers(sender, args):
        request = args.Request
        if is_forcex(str(request.Uri)):
            request.Headers.SetHeader("X-ForceX-Client", CLIENT_KEY)
            request.Headers.SetHeader("X-ForceX-Platform", "windows")
            request.Headers.SetHeader("X-ForceX-App-Version", "0.1.0")

    def block_external_navigation(sender, args):
        url = str(args.Uri)
        if url.lower().startswith(("about:blank", "data:", "blob:")) or is_forcex(url):
            return
        print(f"BLOCKED external navigation: {url}")
        args.Cancel = True

    core.WebResourceRequested += set_client_headers
    core.NavigationStarting += block_external_navigation
    _webview_handlers.extend((set_client_headers, block_external_navigation))


def _prepare_webview(window):
    control = window.native.webview

    def on_initialized(sender, args):
        _configure_webview2(control)

    if control.CoreWebView2 is None:
        control.CoreWebView2InitializationCompleted += on_initialized
        _webview_handlers.append(on_initialized)
    else:
        _configure_webview2(control)


def _exclude_from_capture(window):
    if os.getenv("FORCEX_DISABLE_CAPTURE_PROTECTION", "").strip().lower() in {"1", "true", "yes"}:
        print("WARNING: screen-capture protection is disabled for testing")
        return

    hwnd = window.native.Handle.ToInt32()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    set_affinity = user32.SetWindowDisplayAffinity
    set_affinity.argtypes = (wintypes.HWND, wintypes.DWORD)
    set_affinity.restype = wintypes.BOOL
    if not set_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
        error = ctypes.get_last_error()
        print(f"SetWindowDisplayAffinity failed: hwnd={hwnd}, windows_error={error}", flush=True)
        ctypes.windll.user32.MessageBoxW(
            hwnd,
            f"ForceX cannot enable screen-capture protection (Windows error {error}).",
            "ForceX browser unavailable",
            0x10,
        )
        os._exit(1)


def run_browser():
    if os.name != "nt":
        raise SystemExit("The ForceX secure browser requires Windows and Microsoft Edge WebView2.")
    if not CLIENT_KEY:
        ctypes.windll.user32.MessageBoxW(
            None,
            "FORCEX_CLIENT_KEY is not set. Ask the sender for the ForceX client settings.",
            "ForceX",
            0x10,
        )
        raise SystemExit(1)

    start_url = sys.argv[1] if len(sys.argv) > 1 else FORCEX_URL
    if not is_forcex(start_url):
        print(f"Blocked non-ForceX startup URL: {start_url}")
        start_url = FORCEX_URL

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    webview.settings["SHOW_DEFAULT_MENUS"] = False

    profile_path = Path(os.getenv("LOCALAPPDATA", Path.home())) / "ForceX" / "WebView2"
    profile_path.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(
        "ForceX Secure Browser",
        _browser_shell_url(start_url),
        width=1200,
        height=800,
        text_select=True,
        zoomable=False,
    )
    window.events.before_show += _exclude_from_capture
    window.events.before_show += _prepare_webview
    webview.start(gui="edgechromium", debug=False, private_mode=True, storage_path=str(profile_path))


if __name__ == "__main__":
    run_browser()
