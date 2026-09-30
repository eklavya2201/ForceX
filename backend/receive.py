import hmac
from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, send_file, url_for
from sqlalchemy import update
from .extensions import db, limiter
from .models import Share, ViewSession, AccessLog, utcnow
from .tokens import hash_token, check_passcode, consume_share, create_view_session, finalize
from .audit import log_event
from .storage import _blob_path

bp=Blueprint("receive",__name__)
def gone(): return render_template("receiver/gone.html"),404

@bp.before_request
def desktop_only():
    # Shared content is only served to the ForceX desktop client, which blocks screen capture and printing.
    sent=request.headers.get("X-ForceX-Client","")
    if not hmac.compare_digest(sent.encode(),current_app.config["CLIENT_KEY"].encode()):
        log_event("CLIENT_REJECTED",result="denied")
        return render_template("receiver/desktop_only.html"),403

@bp.get("/s/<token>")
@limiter.limit("20 per minute")
def landing(token):
    share=Share.query.filter_by(token_hash=hash_token(token)).first()
    if not share or share.status!="active" or share.expires_at<=utcnow(): return gone()
    return render_template("receiver/landing.html",token=token,needs_passcode=bool(share.passcode_hash),mode=share.mode)

@bp.post("/s/<token>/open")
@limiter.limit("10 per minute")
def open_share(token):
    share=Share.query.filter_by(token_hash=hash_token(token)).first()
    if not share or share.status!="active" or share.expires_at<=utcnow(): return gone()
    if not check_passcode(share,request.form.get("passcode","")):
        log_event("PASSCODE_FAILED",share_id=share.id,result="denied")
        if share.status=="revoked": return gone()
        return render_template("receiver/landing.html",token=token,needs_passcode=True,mode=share.mode,error="Incorrect passcode."),403
    winner=consume_share(token)
    if winner is None: log_event("OPEN_DENIED",result="denied"); return gone()
    raw,ttl=create_view_session(winner); log_event("SHARE_OPENED",share_id=winner.id)
    dest="receive.viewer" if winner.mode=="view" else "receive.download_page"
    resp=redirect(url_for(dest,share_id=winner.id)); resp.set_cookie(f"fx_view_{winner.id}",raw,max_age=int(ttl.total_seconds()),httponly=True,secure=current_app.config["COOKIE_SECURE"],samesite="Lax",path=f"/v/{winner.id}"); return resp

def require_view_session(share_id):
    share=db.session.get(Share,share_id); raw=request.cookies.get(f"fx_view_{share_id}")
    if not share or not raw: abort(404)
    vs=ViewSession.query.filter_by(share_id=share_id,session_hash=hash_token(raw)).first()
    if not vs or share.status!="opened": abort(404)
    if vs.expires_at<=utcnow(): finalize(share,"consumed"); abort(404)
    return share,vs

@bp.get("/v/<share_id>")
def viewer(share_id):
    share,vs=require_view_session(share_id)
    if share.mode!="view": abort(404)
    return render_template("receiver/viewer.html",share=share,ttl=max(0,int((vs.expires_at-utcnow()).total_seconds())))

@bp.get("/v/<share_id>/file")
def view_file(share_id):
    share,vs=require_view_session(share_id)
    if share.mode!="view": abort(404)
    f=share.files[0]
    if f.mime not in current_app.config["INLINE_MIMES"]: abort(404)
    resp=send_file(_blob_path(current_app,f.storage_key),mimetype=f.mime,conditional=True,etag=False,max_age=0,as_attachment=False)
    resp.headers["Content-Disposition"]="inline"; return resp

@bp.get("/v/<share_id>/download")
def download(share_id):
    share,vs=require_view_session(share_id)
    if share.mode!="download": abort(404)
    won=db.session.execute(update(ViewSession).where(ViewSession.id==vs.id,ViewSession.download_started.is_(False)).values(download_started=True)).rowcount; db.session.commit()
    if won!=1: abort(410)
    f=share.files[0]; resp=send_file(_blob_path(current_app,f.storage_key),mimetype="application/octet-stream",as_attachment=True,download_name=f.display_name,conditional=False)
    sid=share.id; app=current_app._get_current_object(); resp.call_on_close(lambda: _finish_download(app,sid)); log_event("DOWNLOAD_STARTED",share_id=sid); return resp

@bp.get("/v/<share_id>/download-page")
def download_page(share_id):
    share,vs=require_view_session(share_id)
    if share.mode!="download": abort(404)
    return render_template("receiver/download.html",share=share)

def _finish_download(app,share_id):
    with app.app_context():
        share=db.session.get(Share,share_id)
        if share:
            finalize(share,"consumed")
            db.session.add(AccessLog(share_id=share_id,event="DOWNLOAD_DONE",result="ok",detail="")); db.session.commit()

@bp.post("/v/<share_id>/end")
def end(share_id):
    share,vs=require_view_session(share_id); finalize(share,"consumed"); log_event("SHARE_CONSUMED",share_id=share_id)
    resp=redirect(url_for("receive.gone_page")); resp.delete_cookie(f"fx_view_{share.id}",path=f"/v/{share.id}"); return resp

@bp.get("/gone")
def gone_page(): return gone()
