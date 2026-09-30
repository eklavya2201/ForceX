import hmac
import ipaddress
from io import BytesIO
import universal_drm
from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, send_file, url_for
from sqlalchemy import update
from .extensions import db, limiter
from .models import Share, ViewSession, AccessLog, utcnow
from .tokens import hash_token, check_passcode, consume_share, create_view_session, finalize
from .audit import log_event
from .storage import blob, local_path, signed_url

bp=Blueprint("receive",__name__)
def gone(): return render_template("receiver/gone.html"),404

renderer=universal_drm.Renderer()

@bp.before_request
def desktop_only():
    # Shares marked "app" are only served to the ForceX desktop client, which blocks screen capture and printing.
    args=request.view_args or {}
    if "token" in args: share=Share.query.filter_by(token_hash=hash_token(args["token"])).first()
    elif "share_id" in args: share=db.session.get(Share,args["share_id"])
    else: return None
    if not share or share.protection!="app": return None
    sent=request.headers.get("X-ForceX-Client","")
    if not hmac.compare_digest(sent.encode(),current_app.config["CLIENT_KEY"].encode()):
        log_event("CLIENT_REJECTED",share_id=share.id,result="denied")
        return render_template("receiver/desktop_only.html"),403

def viewer_watermark(share,vs):
    # Burned into every page, so any screenshot or photo identifies the share and the viewer's network.
    try:
        ip=ipaddress.ip_address(request.remote_addr or "")
        where=str(ipaddress.ip_network(f"{ip}/{24 if ip.version==4 else 48}",strict=False).network_address)+("/24" if ip.version==4 else "/48")
    except ValueError: where="unknown network"
    return f"{share.label or 'ForceX'} · #{share.id[:8]} · {where} · opened {vs.created_at:%Y-%m-%d %H:%M} UTC"

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
    f=share.files[0]; kind=universal_drm.kind(f.mime)
    if f.mime not in current_app.config["INLINE_MIMES"] or not kind: abort(404)
    try: pages=renderer.page_count(local_path(current_app,f),f.mime) if kind=="pages" else 0
    except Exception: current_app.logger.exception("Cannot render share %s",share.id); abort(404)
    return render_template("receiver/viewer.html",share=share,kind=kind,pages=pages,mime=f.mime,watermark=viewer_watermark(share,vs),ttl=max(0,int((vs.expires_at-utcnow()).total_seconds())))

@bp.get("/v/<share_id>/page/<int:index>")
@limiter.limit("300 per minute")
def view_page(share_id,index):
    share,vs=require_view_session(share_id)
    if share.mode!="view": abort(404)
    f=share.files[0]
    if f.mime not in current_app.config["INLINE_MIMES"] or universal_drm.kind(f.mime)!="pages": abort(404)
    try: data=renderer.render_page(local_path(current_app,f),f.mime,index,viewer_watermark(share,vs))
    except IndexError: abort(404)
    return send_file(BytesIO(data),mimetype="image/jpeg",max_age=0,etag=False)

@bp.get("/v/<share_id>/status")
def view_status(share_id):
    share=db.session.get(Share,share_id); raw=request.cookies.get(f"fx_view_{share_id}")
    if share and share.status=="revoked": return jsonify(active=False,reason="revoked")
    vs=ViewSession.query.filter_by(share_id=share_id,session_hash=hash_token(raw)).first() if share and raw else None
    if not vs or share.status!="opened" or vs.expires_at<=utcnow(): return jsonify(active=False,reason="expired")
    return jsonify(active=True,seconds_left=int((vs.expires_at-utcnow()).total_seconds()))

@bp.get("/v/<share_id>/file")
def view_file(share_id):
    # Only video is streamed as a file; documents and images are served as watermarked pages.
    share,vs=require_view_session(share_id)
    if share.mode!="view": abort(404)
    f=share.files[0]
    if f.mime not in current_app.config["INLINE_MIMES"] or universal_drm.kind(f.mime)!="video": abort(404)
    if blob():
        # Function responses are capped at 4.5 MB on Vercel, so video plays from a signed Blob URL that lasts the session.
        return redirect(signed_url(f,max(60,int((vs.expires_at-utcnow()).total_seconds()))))
    resp=send_file(local_path(current_app,f),mimetype=f.mime,conditional=True,etag=False,max_age=0,as_attachment=False)
    resp.headers["Content-Disposition"]="inline"; return resp

@bp.get("/v/<share_id>/download")
def download(share_id):
    share,vs=require_view_session(share_id)
    if share.mode!="download": abort(404)
    won=db.session.execute(update(ViewSession).where(ViewSession.id==vs.id,ViewSession.download_started.is_(False)).values(download_started=True)).rowcount; db.session.commit()
    if won!=1: abort(410)
    f=share.files[0]
    if blob():
        # The browser fetches the file from Blob with a 5-minute signed URL; the sweep deletes it 10 minutes later.
        finalize(share,"consumed",delete=False); log_event("DOWNLOAD_STARTED",share_id=share.id)
        return redirect(signed_url(f,300)+"&download=1")
    resp=send_file(local_path(current_app,f),mimetype="application/octet-stream",as_attachment=True,download_name=f.display_name,conditional=False)
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
