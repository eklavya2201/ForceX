import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from .extensions import db

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def new_id():
    return uuid.uuid4().hex

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Share(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=new_id)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    mode = db.Column(db.String(10), nullable=False)
    # "browser": any browser, via the UniversalDRM viewer. "app": only the ForceX desktop app, which blocks screen capture.
    protection = db.Column(db.String(10), nullable=False, default="browser", server_default="browser")
    status = db.Column(db.String(10), nullable=False, default="active", index=True)
    label = db.Column(db.String(120))
    passcode_hash = db.Column(db.String(255))
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    opened_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    file_count = db.Column(db.Integer, nullable=False, default=1)
    total_size = db.Column(db.BigInteger, nullable=False, default=0)
    manifest_json = db.Column(db.Text)
    files = db.relationship("StoredFile", backref="share", cascade="all, delete-orphan")

class StoredFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(db.String(32), db.ForeignKey("share.id"), nullable=False, index=True)
    storage_key = db.Column(db.String(32), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(100), nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    is_archive = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime)

class ViewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(db.String(32), db.ForeignKey("share.id"), nullable=False, index=True)
    session_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    download_started = db.Column(db.Boolean, nullable=False, default=False)
    ip_hash = db.Column(db.String(64))
    ua_hash = db.Column(db.String(64))

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    share_id = db.Column(db.String(32), index=True)
    user_id = db.Column(db.Integer)
    event = db.Column(db.String(40), nullable=False)
    result = db.Column(db.String(20), nullable=False)
    ip_hash = db.Column(db.String(64))
    detail = db.Column(db.String(255))
