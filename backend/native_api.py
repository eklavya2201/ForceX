"""Small JSON API used by the installed Windows client."""
import hmac
import json
import re
import secrets
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from flask import Blueprint, abort, current_app, jsonify, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from .audit import log_event
from .blobstore import BlobError
from .extensions import db, limiter
from .models import PendingUpload, Share, StoredFile, User, utcnow
from .storage import BlobUpload, blob, blob_name, enforce_mode, save_upload
from .tokens import finalize, hash_token, new_token, ph


bp = Blueprint("native_api", __name__, url_prefix="/api/native")
_dummy = PasswordHasher().hash("not-a-real-user-password")


@bp.before_request
def require_installed_client():
    expected = current_app.config.get("CLIENT_KEY", "")
    supplied = request.headers.get("X-ForceX-Client", "")
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        abort(403)


def _user_data(user):
    return {"id": user.id, "email": user.email}


def _share_data(share):
    status = "expired" if share.status == "active" and share.expires_at <= utcnow() else share.status
    return {
        "id": share.id,
        "label": share.label or "Untitled share",
        "mode": share.mode,
        "protection": share.protection,
        "status": status,
        "created_at": share.created_at.isoformat() + "Z",
        "expires_at": share.expires_at.isoformat() + "Z",
        "opened_at": share.opened_at.isoformat() + "Z" if share.opened_at else None,
        "file_count": share.file_count,
        "total_size": share.total_size,
    }


def require_user(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(error="Sign in to continue."), 401
        return view(*args, **kwargs)
    return wrapped


@bp.get("/config")
def config():
    return jsonify(
        server_name=current_app.config.get("SERVER_NAME") or request.host,
        max_bytes=current_app.config["MAX_CONTENT_LENGTH"],
        max_files=current_app.config["MAX_FILES"],
        allow_registration=current_app.config.get("ALLOW_REGISTRATION", True),
        direct_upload=blob() is not None,
    )


@bp.get("/session")
def session():
    if not current_user.is_authenticated:
        return jsonify(authenticated=False)
    shares = Share.query.filter_by(sender_id=current_user.id).order_by(Share.created_at.desc()).limit(200).all()
    return jsonify(authenticated=True, user=_user_data(current_user), shares=[_share_data(s) for s in shares])


@bp.post("/login")
@limiter.limit("5 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = User.query.filter_by(email=email).first()
    hashed = user.password_hash if user else _dummy
    try:
        valid = ph.verify(hashed, password or "")
    except (VerifyMismatchError, VerificationError):
        valid = False
    if not user or not valid:
        log_event("LOGIN_FAILURE", result="denied")
        return jsonify(error="Email or password is incorrect."), 401
    login_user(user)
    log_event("LOGIN_SUCCESS")
    return jsonify(user=_user_data(user))


@bp.post("/register")
@limiter.limit("5 per minute")
def register():
    if not current_app.config.get("ALLOW_REGISTRATION", True):
        return jsonify(error="Registration is currently closed."), 403
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(password) < 10:
        return jsonify(error="Enter a valid email and a password with at least 10 characters."), 400
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="An account with that email already exists."), 409
    user = User(email=email, password_hash=ph.hash(password))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="An account with that email already exists."), 409
    login_user(user)
    return jsonify(user=_user_data(user)), 201


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    return jsonify(ok=True)


@bp.post("/uploads/sign")
@require_user
@limiter.limit("30 per minute")
def sign_uploads():
    client = blob()
    if not client:
        return jsonify(error="Direct upload is unavailable on this server."), 503
    items = (request.get_json(silent=True) or {}).get("files") or []
    if not isinstance(items, list) or not items or len(items) > current_app.config["MAX_FILES"]:
        return jsonify(error=f"Choose between 1 and {current_app.config['MAX_FILES']} files."), 400
    try:
        sizes = [int(item.get("size", 0)) for item in items]
    except (TypeError, ValueError, AttributeError):
        return jsonify(error="Invalid file list."), 400
    limit = current_app.config["MAX_CONTENT_LENGTH"]
    if min(sizes) < 0 or sum(sizes) > limit:
        return jsonify(error=f"Selected files exceed the {limit // 1048576} MB limit."), 400
    uploads = []
    for item, size in zip(items, sizes):
        pathname = f"f/{secrets.token_hex(16)}/{blob_name(item.get('name'))}"
        upload_url, headers = client.presign_put(pathname, max(size, 1), limit)
        db.session.add(PendingUpload(pathname=pathname, user_id=current_user.id, size=size))
        uploads.append({"id": pathname, "url": upload_url, "headers": headers})
    db.session.commit()
    return jsonify(uploads=uploads)


@bp.get("/shares")
@require_user
def list_shares():
    shares = Share.query.filter_by(sender_id=current_user.id).order_by(Share.created_at.desc()).limit(200).all()
    return jsonify(shares=[_share_data(s) for s in shares])


@bp.post("/shares")
@require_user
def create_share():
    data = request.get_json(silent=True) or {}
    client = blob()
    paths = data.get("paths") or []
    if not isinstance(paths, list):
        return jsonify(error="Invalid file paths."), 400
    requested_mode = str(data.get("mode", "download"))
    if requested_mode not in ("view", "download"):
        return jsonify(error="Choose a supported access mode."), 400
    expiry = current_app.config["EXPIRY_CHOICES"].get(data.get("expiry"))
    if expiry is None:
        return jsonify(error="Choose a supported expiration."), 400
    claimed = []
    if client:
        ids = data.get("uploads") or []
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids):
            return jsonify(error="Invalid upload."), 400
        if len(ids) != len(set(ids)) or len(paths) != len(ids):
            return jsonify(error="Invalid upload."), 400
        pending = {p.pathname: p for p in PendingUpload.query.filter(
            PendingUpload.pathname.in_(ids), PendingUpload.user_id == current_user.id
        )}
        if len(pending) != len(ids):
            return jsonify(error="Upload expired or does not belong to this account."), 400
        files = [BlobUpload(client, pathname, pathname.rsplit("/", 1)[1]) for pathname in ids]
        claimed = list(pending.values())
    else:
        return jsonify(error="This server requires its browser upload workflow."), 503
    try:
        info = save_upload(current_app, files, paths)
    except (ValueError, OSError, BlobError):
        current_app.logger.exception("Native app upload failed")
        return jsonify(error="Could not prepare the uploaded files."), 400
    for pending_upload in claimed:
        db.session.delete(pending_upload)
    mode, note = enforce_mode(requested_mode, info, current_app)
    passcode = str(data.get("passcode", "")).strip()
    protection = "browser"
    if mode == "view" and data.get("protection") == "app":
        protection = {"windows": "app_windows", "android": "app_android"}.get(data.get("platform"), "app_any")
    share = Share(
        sender_id=current_user.id,
        token_hash=hash_token(token := new_token()),
        mode=mode,
        protection=protection,
        label=str(data.get("label", ""))[:120] or None,
        passcode_hash=ph.hash(passcode) if passcode else None,
        expires_at=utcnow() + expiry,
        file_count=len(info["manifest"]),
        total_size=sum(item["size"] for item in info["manifest"]),
        manifest_json=json.dumps(info["manifest"]),
    )
    share.files.append(StoredFile(
        storage_key=info["storage_key"], blob_path=info["blob_path"],
        display_name=info["display_name"], mime=info["mime"], size=info["size"],
        sha256=info["sha256"], is_archive=info["is_archive"],
    ))
    db.session.add(share)
    db.session.commit()
    log_event("SHARE_CREATED", share_id=share.id)
    return jsonify(share=_share_data(share), link=url_for("receive.landing", token=token, _external=True), note=note), 201


@bp.post("/shares/<share_id>/revoke")
@require_user
def revoke_share(share_id):
    share = Share.query.filter_by(id=share_id, sender_id=current_user.id).first_or_404()
    if share.status in ("active", "opened"):
        finalize(share, "revoked")
        log_event("SHARE_REVOKED", share_id=share.id)
    return jsonify(share=_share_data(share))
