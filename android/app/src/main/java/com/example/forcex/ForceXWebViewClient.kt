package com.example.forcex

import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * ForceXWebViewClient
 *
 * Responsibilities:
 * 1. Injects the three ForceX authentication headers (X-ForceX-Client,
 *    X-ForceX-Platform, X-ForceX-App-Version) on every GET request to the
 *    ForceX host via shouldInterceptRequest.
 *
 *    POST requests (e.g. /open form submission) cannot be re-issued via
 *    shouldInterceptRequest without losing the body. Instead, POST forms
 *    submit through the WebView's normal fetch path, which carries the
 *    session cookie. The server's gate hook checks the cookie OR the
 *    X-ForceX-Client header; for POST requests the server gate is designed
 *    to accept a pre-validated session (the open action succeeds only after
 *    the landing GET was allowed through, which means the GET carried the
 *    header). This is consistent with the plan note in §11.5.
 *
 * 2. Blocks navigation to any host other than the configured ForceX server.
 *    data: and blob: URLs are allowed (used internally by the canvas viewer).
 *
 * 3. Syncs cookies between the WebView's CookieManager and the HttpURLConnection
 *    so that session cookies set by the server reach subsequent requests.
 */
class ForceXWebViewClient(
    private val serverHost: String,
    private val forcexUrl: String,
    private val clientKey: String,
    private val appVersion: String,
    private val onUrlChanged: ((String) -> Unit)? = null,
    private val onPageFinished: ((WebView) -> Unit)? = null,
) : WebViewClient() {

    // ── Navigation lock ────────────────────────────────────────────────────

    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
        val host = request.url.host ?: ""
        val scheme = request.url.scheme ?: ""
        if (scheme == "data" || scheme == "blob") return false
        if (host == serverHost) {
            onUrlChanged?.invoke(request.url.toString())
            return false  // Let WebView handle it
        }
        // Block navigation to any other host silently
        return true
    }

    override fun onPageFinished(view: WebView, url: String) {
        super.onPageFinished(view, url)
        onUrlChanged?.invoke(url)
        onPageFinished?.invoke(view)
    }

    // ── Header injection for GET requests ─────────────────────────────────

    override fun shouldInterceptRequest(
        view: WebView,
        request: WebResourceRequest,
    ): WebResourceResponse? {
        val urlStr = request.url.toString()

        // Only intercept GET requests to the ForceX host
        if (request.url.host != serverHost || request.method != "GET") {
            return super.shouldInterceptRequest(view, request)
        }

        return try {
            val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 15_000
                readTimeout = 30_000
                instanceFollowRedirects = true

                // Copy original request headers from WebView
                for ((key, value) in request.requestHeaders) {
                    setRequestProperty(key, value)
                }

                // Inject ForceX authentication headers
                setRequestProperty("X-ForceX-Client", clientKey)
                setRequestProperty("X-ForceX-Platform", "android")
                setRequestProperty("X-ForceX-App-Version", appVersion)

                // Forward cookies from WebView's CookieManager
                val cookies = CookieManager.getInstance().getCookie(urlStr)
                if (!cookies.isNullOrBlank()) {
                    setRequestProperty("Cookie", cookies)
                }
            }

            // Sync Set-Cookie headers back into the WebView's CookieManager
            val setCookies = conn.headerFields["Set-Cookie"]
            if (!setCookies.isNullOrEmpty()) {
                val cm = CookieManager.getInstance()
                for (cookie in setCookies) {
                    cm.setCookie(urlStr, cookie)
                }
                cm.flush()
            }

            // Build response headers map (null keys come from the status line)
            val respHeaders = conn.headerFields
                .filterKeys { it != null }
                .mapValues { (_, v) -> v.joinToString(",") }

            val mime = (conn.contentType ?: "text/html").substringBefore(";").trim()
            val encoding = resolveEncoding(conn.contentType, conn.contentEncoding)

            val inputStream: InputStream =
                if (conn.responseCode >= 400) conn.errorStream ?: conn.inputStream
                else conn.inputStream

            WebResourceResponse(
                mime,
                encoding,
                conn.responseCode,
                conn.responseMessage ?: "OK",
                respHeaders,
                inputStream,
            )
        } catch (e: Exception) {
            e.printStackTrace()
            super.shouldInterceptRequest(view, request)
        }
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    private fun resolveEncoding(contentType: String?, contentEncoding: String?): String {
        if (!contentEncoding.isNullOrBlank()) return contentEncoding
        if (!contentType.isNullOrBlank() && contentType.contains("charset=", ignoreCase = true)) {
            return contentType
                .substringAfter("charset=", "")
                .substringBefore(";")
                .trim()
                .ifBlank { "utf-8" }
        }
        return "utf-8"
    }
}
