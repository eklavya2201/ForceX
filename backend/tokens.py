import hashlib, hmac, secrets
from datetime import timedelta
from flask import current_app, request
from sqlalchemy import update
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from .extensions import db
from .models import Share, ViewSession, utcnow
from .storage import delete_share_blobs

ph = PasswordHasher()
def new_token(): return secrets.token_urlsafe(32)
def hash_token(value): return hashlib.sha256(value.encode()).hexdigest()
def hash_ip(value): return hmac.new(current_app.config["SECRET_KEY"].encode(), (value or "").encode(), hashlib.sha256).hexdigest()

def consume_share(token):
    now=utcnow(); h=hash_token(token)
    result=db.session.execute(update(Share).where(Share.token_hash==h, Share.status=="active", Share.expires_at>now).values(status="opened", opened_at=now))
    db.session.commit()
    return Share.query.filter_by(token_hash=h).one_or_none() if result.rowcount == 1 else None

def check_passcode(share, provided):
    if not share.passcode_hash: return True
    try:
        ph.verify(share.passcode_hash, provided or "")
        return True
    except (VerifyMismatchError, VerificationError):
        db.session.execute(update(Share).where(Share.id==share.id, Share.status=="active").values(failed_attempts=Share.failed_attempts+1)); db.session.commit(); db.session.refresh(share)
        if share.failed_attempts >= current_app.config["MAX_PASSCODE_ATTEMPTS"]: finalize(share,"revoked")
        return False

def create_view_session(share):
    raw=secrets.token_urlsafe(32); ttl=current_app.config["VIEW_TTL"] if share.mode=="view" else current_app.config["DOWNLOAD_TTL"]
    db.session.add(ViewSession(share_id=share.id,session_hash=hash_token(raw),expires_at=utcnow()+ttl,ip_hash=hash_ip(request.remote_addr),ua_hash=hash_token(request.headers.get("User-Agent",""))))
    db.session.commit(); return raw,ttl

def finalize(share,new_status):
    if share.status not in ("consumed","expired","revoked"):
        share.status=new_status; share.ended_at=utcnow(); db.session.commit()
    delete_share_blobs(share)
