package com.example.forcex

import android.Manifest
import android.net.Uri
import android.webkit.ConsoleMessage
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView

/**
 * ForceXWebChromeClient
 *
 * Blocks all features that could allow content to leave the app:
 * - File choosers (onShowFileChooser): returns false / cancels.
 * - New windows / popups (onCreateWindow): returns false.
 * - Camera, microphone, geolocation (onPermissionRequest, onGeolocationPermissionsShowPrompt):
 *   denies without prompting the user.
 * - Console messages: swallowed in production (debug builds log them).
 */
class ForceXWebChromeClient : WebChromeClient() {

    // ── File chooser ───────────────────────────────────────────────────────

    override fun onShowFileChooser(
        webView: WebView,
        filePathCallback: ValueCallback<Array<Uri>>,
        fileChooserParams: FileChooserParams,
    ): Boolean {
        // Cancel the callback immediately — the viewer never needs file access
        filePathCallback.onReceiveValue(null)
        return false
    }

    // ── Popups / new windows ───────────────────────────────────────────────

    override fun onCreateWindow(
        view: WebView,
        isDialog: Boolean,
        isUserGesture: Boolean,
        resultMsg: android.os.Message?,
    ): Boolean = false   // Block all new-window requests

    // ── Device permissions ─────────────────────────────────────────────────

    override fun onPermissionRequest(request: PermissionRequest) {
        // Deny camera, microphone, MIDI and any other requested resource
        request.deny()
    }

    override fun onGeolocationPermissionsShowPrompt(
        origin: String,
        callback: GeolocationPermissions.Callback,
    ) {
        // Deny geolocation without showing a prompt
        callback.invoke(origin, false, false)
    }

    // ── Console messages ───────────────────────────────────────────────────

    override fun onConsoleMessage(consoleMessage: ConsoleMessage): Boolean {
        // Swallow console messages so they don't leak viewer state in production
        return true
    }
}
