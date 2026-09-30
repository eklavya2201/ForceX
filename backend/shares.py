import json
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from .extensions import db
from .models import Share, StoredFile, utcnow
from .tokens import ph, new_token, hash_token, finalize
from .storage import save_upload, enforce_mode
from .audit import log_event

bp=Blueprint("shares",__name__)
@bp.get("/dashboard")
@login_required
def dashboard():
    shares=Share.query.filter_by(sender_id=current_user.id).order_by(Share.created_at.desc()).all()
    for s in shares: s.display_status="expired" if s.status=="active" and s.expires_at<=utcnow() else s.status
    return render_template("sender/dashboard.html",shares=shares)

@bp.get("/new")
@login_required
def new(): return render_template("sender/new.html")

@bp.post("/shares")
@login_required
def create():
    files=request.files.getlist("files"); paths=request.form.getlist("paths")
    try: info=save_upload(current_app,files,paths)
    except (ValueError,OSError): flash("Invalid upload.","error"); return redirect(url_for("shares.new"))
    mode,note=enforce_mode(request.form.get("mode","download"),info,current_app)
    expiry=current_app.config["EXPIRY_CHOICES"].get(request.form.get("expiry"),current_app.config["EXPIRY_CHOICES"]["24h"])
    passcode=request.form.get("passcode","").strip(); token=new_token()
    protection="app" if mode=="view" and request.form.get("protection")=="app" else "browser"
    share=Share(sender_id=current_user.id,token_hash=hash_token(token),mode=mode,protection=protection,label=request.form.get("label","")[:120] or None,passcode_hash=ph.hash(passcode) if passcode else None,expires_at=utcnow()+expiry,file_count=len(info["manifest"]),total_size=sum(item["size"] for item in info["manifest"]),manifest_json=json.dumps(info["manifest"]))
    share.files.append(StoredFile(storage_key=info["storage_key"],display_name=info["display_name"],mime=info["mime"],size=info["size"],sha256=info["sha256"],is_archive=info["is_archive"]))
    db.session.add(share); db.session.commit(); log_event("SHARE_CREATED",share_id=share.id)
    return render_template("sender/created.html",link=url_for("receive.landing",token=token,_external=True),share=share,note=note)

@bp.post("/shares/<share_id>/revoke")
@login_required
def revoke(share_id):
    share=Share.query.filter_by(id=share_id,sender_id=current_user.id).first_or_404()
    if share.status in ("active","opened"):
        finalize(share,"revoked"); log_event("SHARE_REVOKED",share_id=share.id)
    return redirect(url_for("shares.dashboard"))
