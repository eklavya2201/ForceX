package com.example.forcex

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Toast
import androidx.activity.ComponentActivity
import org.json.JSONObject
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * ForceX secure WebView activity.
 *
 * Security features:
 * - FLAG_SECURE: window appears black in screenshots, screen recordings,
 *   casting and the recent-apps thumbnail. Applied BEFORE setContentView.
 * - ForceXWebViewClient: injects X-ForceX-* headers on all GET requests via
 *   shouldInterceptRequest; blocks navigation to any host other than the
 *   configured ForceX server.
 * - ForceXWebChromeClient: blocks file choosers, popups, camera/mic/geo.
 * - Download listener: cancels all downloads and shows a toast.
 * - Long-click disabled: prevents the text-selection / save-image popup.
 * - Focus-loss blanking: hides the WebView on pause / window-focus-lost and
 *   restores it on resume / window-focus-gained.
 * - Address bar: receivers paste the share link they were sent.
 */
class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var addressBar: EditText

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // ── FLAG_SECURE must be set BEFORE setContentView ──────────────────
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )

        // ── Build the layout programmatically ─────────────────────────────
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }

        addressBar = EditText(this).apply {
            hint = "Paste a ForceX share link and press ↵"
            setSingleLine(true)
            setOnEditorActionListener { _, _, _ ->
                navigateToAddress(text.toString().trim())
                true
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }
        root.addView(addressBar)

        val webContainer = FrameLayout(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        }

        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }
        webContainer.addView(webView)
        root.addView(webContainer)
        setContentView(root)

        // ── WebView settings ───────────────────────────────────────────────
        webView.settings.apply {
            javaScriptEnabled = true          // required by the UniversalDRM viewer
            domStorageEnabled = true          // needed for session storage used by the viewer
            databaseEnabled = false
            allowFileAccess = false
            allowContentAccess = false
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
            mediaPlaybackRequiresUserGesture = false
            // Never load mixed content
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }

        // Disable long-press (would show "Save image", "Copy link", etc.)
        webView.isLongClickable = false
        webView.setOnLongClickListener { true }
        webView.isHapticFeedbackEnabled = false

        // ── Clients ────────────────────────────────────────────────────────
        webView.webViewClient = ForceXWebViewClient(
            serverHost = extractHost(Config.FORCEX_URL),
            forcexUrl = Config.FORCEX_URL,
            clientKey = Config.CLIENT_KEY,
            appVersion = Config.APP_VERSION,
            onUrlChanged = { url -> addressBar.setText(url) },
            onPageFinished = { view -> installProtectedOpenHandler(view) }
        )
        webView.webChromeClient = ForceXWebChromeClient()

        // ── Block downloads ────────────────────────────────────────────────
        webView.setDownloadListener { _, _, _, _, _ ->
            Toast.makeText(this, "Downloads are not permitted in ForceX.", Toast.LENGTH_SHORT).show()
        }

        // ── Cookie manager ─────────────────────────────────────────────────
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false)

        // ── Initial URL ────────────────────────────────────────────────────
        val startUrl = intent?.data?.toString()?.takeIf { it.isNotBlank() } ?: Config.FORCEX_URL
        loadUrl(startUrl)
    }

    // ── Lifecycle: hide content on pause / focus loss ─────────────────────

    override fun onPause() {
        super.onPause()
        webView.visibility = View.INVISIBLE
    }

    override fun onStop() {
        super.onStop()
        webView.visibility = View.INVISIBLE
    }

    override fun onResume() {
        super.onResume()
        webView.visibility = View.VISIBLE
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        webView.visibility = if (hasFocus) View.VISIBLE else View.INVISIBLE
    }

    // ── Back navigation ────────────────────────────────────────────────────

    @Deprecated("Using deprecated onBackPressed for API < 33 compatibility")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    private fun loadUrl(url: String) {
        val host = extractHost(url)
        val serverHost = extractHost(Config.FORCEX_URL)
        if (host == serverHost) {
            webView.loadUrl(url)
            addressBar.setText(url)
        } else {
            Toast.makeText(this, "Only links from $serverHost can be opened.", Toast.LENGTH_LONG).show()
        }
    }

    private fun navigateToAddress(raw: String) {
        val url = if (raw.startsWith("http://") || raw.startsWith("https://")) raw
                  else "https://$raw"
        loadUrl(url)
    }

        private fun installProtectedOpenHandler(view: WebView) {
                val clientKey = JSONObject.quote(Config.CLIENT_KEY)
                val appVersion = JSONObject.quote(Config.APP_VERSION)
                view.evaluateJavascript(
                        """
                        (() => {
                            const form = document.querySelector('form[action*="/open"]');
                            if (!form || form.dataset.forcexAndroidPost === 'true') return;
                            form.dataset.forcexAndroidPost = 'true';
                            form.addEventListener('submit', async event => {
                                event.preventDefault();
                                const body = new URLSearchParams();
                                for (const [key, value] of new FormData(form).entries()) {
                                    if (typeof value === 'string') body.append(key, value);
                                }
                                try {
                                    const response = await fetch(form.action, {
                                        method: 'POST',
                                        body,
                                        credentials: 'same-origin',
                                        headers: {
                                            'X-ForceX-Client': $clientKey,
                                            'X-ForceX-Platform': 'android',
                                            'X-ForceX-App-Version': $appVersion
                                        }
                                    });
                                    if (response.redirected || response.status !== 403) {
                                        window.location.assign(response.url);
                                        return;
                                    }
                                    const html = await response.text();
                                    const result = new DOMParser().parseFromString(html, 'text/html');
                                    const message = result.querySelector('.flash.error')?.textContent.trim();
                                    let error = document.querySelector('#forcex-open-error');
                                    if (!error) {
                                        error = document.createElement('div');
                                        error.id = 'forcex-open-error';
                                        error.className = 'flash error';
                                        form.before(error);
                                    }
                                    error.textContent = message || 'Unable to open this share.';
                                    const passcode = form.querySelector('input[type="password"]');
                                    if (passcode) { passcode.value = ''; passcode.focus(); }
                                } catch (_) {
                                    window.location.assign(form.action);
                                }
                            });
                        })();
                        """.trimIndent(),
                        null,
                )
        }

    companion object {
        fun extractHost(url: String): String =
            runCatching { java.net.URL(url).host }.getOrDefault("")
    }
}
