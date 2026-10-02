import json, secrets
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from .extensions import db, limiter
from .models import PendingUpload, Share, StoredFile, utcnow
from .tokens import ph, new_token, hash_token, finalize
from .storage import BlobUpload, blob, blob_name, save_upload, enforce_mode
from .blobstore import BlobError
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
def new(): return render_template("sender/new.html",direct_upload=blob() is not None,max_bytes=current_app.config["MAX_CONTENT_LENGTH"],max_files=current_app.config["MAX_FILES"])

@bp.post("/uploads/sign")
@login_required
@limiter.limit("30 per minute")
def sign_uploads():
    # With Blob storage the browser uploads each file straight to Blob; this hands out one URL per file,
    # each valid for a single pathname and at most the declared size.
    client=blob()
    if not client: abort(404)
    items=(request.get_json(silent=True) or {}).get("files") or []
    try: sizes=[int(item.get("size",0)) for item in items]
    except (TypeError,ValueError,AttributeError): return jsonify(error="Invalid file list."),400
    limit=current_app.config["MAX_CONTENT_LENGTH"]
    if not items or len(items)>current_app.config["MAX_FILES"]: return jsonify(error=f"Choose between 1 and {current_app.config['MAX_FILES']} files."),400
    if min(sizes)<0 or sum(sizes)>limit: return jsonify(error=f"Selected files exceed the {limit//1048576} MB limit."),400
    uploads=[]
    for item,size in zip(items,sizes):
        pathname=f"f/{secrets.token_hex(16)}/{blob_name(item.get('name'))}"
        url,headers=client.presign_put(pathname,max(size,1),limit)
        db.session.add(PendingUpload(pathname=pathname,user_id=current_user.id,size=size))
        uploads.append({"id":pathname,"url":url,"headers":headers})
    db.session.commit()
    return jsonify(uploads=uploads)

@bp.post("/shares")
@login_required
def create():
    paths=request.form.getlist("paths"); claimed=[]
    client=blob()
    if client:
        ids=request.form.getlist("uploads")
        pending={p.pathname:p for p in PendingUpload.query.filter(PendingUpload.pathname.in_(ids),PendingUpload.user_id==current_user.id)} if ids else {}
        if not ids or len(pending)!=len(set(ids)) or len(ids)!=len(set(ids)): flash("Invalid upload.","error"); return redirect(url_for("shares.new"))
        files=[BlobUpload(client,pathname,pathname.rsplit("/",1)[1]) for pathname in ids]; claimed=list(pending.values())
    else: files=request.files.getlist("files")
    try: info=save_upload(current_app,files,paths)
    except (ValueError,OSError,BlobError): current_app.logger.exception("Upload failed"); flash("Invalid upload.","error"); return redirect(url_for("shares.new"))
    for p in claimed: db.session.delete(p)
    mode,note=enforce_mode(request.form.get("mode","download"),info,current_app)
    expiry=current_app.config["EXPIRY_CHOICES"].get(request.form.get("expiry"),current_app.config["EXPIRY_CHOICES"]["24h"])
    passcode=request.form.get("passcode","").strip(); token=new_token()
    if mode == "view" and request.form.get("protection") == "app":
        plat = request.form.get("platform", "")          # windows / android / any
        protection = {"windows": "app_windows", "android": "app_android"}.get(plat, "app_any")
    else:
        protection = "browser"   # download-once always gives the real file
    share=Share(sender_id=current_user.id,token_hash=hash_token(token),mode=mode,protection=protection,label=request.form.get("label","")[:120] or None,passcode_hash=ph.hash(passcode) if passcode else None,expires_at=utcnow()+expiry,file_count=len(info["manifest"]),total_size=sum(item["size"] for item in info["manifest"]),manifest_json=json.dumps(info["manifest"]))
    share.files.append(StoredFile(storage_key=info["storage_key"],blob_path=info["blob_path"],display_name=info["display_name"],mime=info["mime"],size=info["size"],sha256=info["sha256"],is_archive=info["is_archive"]))
    db.session.add(share); db.session.commit(); log_event("SHARE_CREATED",share_id=share.id)
    return render_template("sender/created.html",link=url_for("receive.landing",token=token,_external=True),share=share,note=note)

@bp.post("/shares/<share_id>/revoke")
@login_required
def revoke(share_id):
    share=Share.query.filter_by(id=share_id,sender_id=current_user.id).first_or_404()
    if share.status in ("active","opened"):
        finalize(share,"revoked"); log_event("SHARE_REVOKED",share_id=share.id)
    return redirect(url_for("shares.dashboard"))
