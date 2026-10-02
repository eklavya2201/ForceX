from flask import request
from flask_login import current_user
from .extensions import db
from .models import AccessLog
from .tokens import hash_ip


def _detect_client_info():
    """Extract client type, platform, app version and device from request headers."""
    platform_header = request.headers.get("X-ForceX-Platform", "").lower().strip()
    app_version = request.headers.get("X-ForceX-App-Version", "").strip()[:30] or None
    forcex_client = request.headers.get("X-ForceX-Client", "")
    ua = request.headers.get("User-Agent", "")

    if platform_header == "android" or (forcex_client and "Android" in ua):
        client_type = "android_app"
        platform = "android"
    elif platform_header == "windows" or (forcex_client and "Windows" in ua):
        client_type = "windows_app"
        platform = "windows"
    elif forcex_client:
        client_type = "app"
        platform = platform_header or None
    else:
        client_type = "browser"
        platform = None
        # Derive platform from User-Agent for browser access
        for name in ("Windows", "Android", "Macintosh", "iPhone", "iPad", "Linux"):
            if name in ua:
                platform = name.lower()
                break

    # Build a short device summary
    device_parts = []
    if platform:
        device_parts.append(platform)
    if app_version:
        device_parts.append(f"v{app_version}")
    elif ua:
        # Grab the first product token from the UA
        token = ua.split(" ")[0] if ua else ""
        if token:
            device_parts.append(token[:60])
    device = " · ".join(device_parts)[:120] or None

    return client_type, app_version, platform, device


def log_event(event, share_id=None, result="ok", detail=None):
    uid = current_user.id if current_user.is_authenticated else None
    client_type, app_version, platform, device = _detect_client_info()
    db.session.add(AccessLog(
        share_id=share_id,
        user_id=uid,
        event=event,
        result=result,
        detail=(detail or "")[:255],
        ip_hash=hash_ip(request.remote_addr),
        client_type=client_type,
        app_version=app_version,
        platform=platform,
        device=device,
    ))
    db.session.commit()
