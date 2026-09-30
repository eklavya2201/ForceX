import os, shutil, time
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from .extensions import db
from .models import Share, StoredFile, ViewSession, AccessLog, PendingUpload, utcnow
from .storage import blob, delete_share_blobs
from .blobstore import BlobError
from .tokens import finalize

def purge_tmp(app,older_than_minutes=60,folder="tmp"):
    root=os.path.join(app.config["STORAGE_DIR"],folder)
    if not os.path.isdir(root): return
    cutoff=time.time()-older_than_minutes*60
    for name in os.listdir(root):
        path=os.path.join(root,name)
        try:
            if os.path.getmtime(path)<cutoff:
                if os.path.isdir(path): shutil.rmtree(path,ignore_errors=True)
                else: os.remove(path)
        except OSError: pass

def sweep(app):
    with app.app_context():
        now=utcnow()
        for s in Share.query.filter(Share.status=="active",Share.expires_at<=now).all(): finalize(s,"expired")
        for s in Share.query.filter_by(status="opened").all():
            if ViewSession.query.filter(ViewSession.share_id==s.id,ViewSession.expires_at>now).count()==0: finalize(s,"consumed")
        for f in StoredFile.query.join(Share).filter(StoredFile.deleted_at.is_(None),Share.status.in_(("consumed","expired","revoked"))).all():
            # A finished Blob download was handed a signed URL; leave the file until that URL has surely been fetched.
            if f.blob_path and f.share.mode=="download" and f.share.status=="consumed" and f.share.ended_at and f.share.ended_at>now-timedelta(minutes=10): continue
            delete_share_blobs(f.share)
        stale=PendingUpload.query.filter(PendingUpload.created_at<now-timedelta(hours=2)).all()
        if stale:
            client=blob()
            try:
                if client: client.delete([p.pathname for p in stale])
                for p in stale: db.session.delete(p)
            except BlobError: app.logger.exception("Could not delete unclaimed uploads")
        purge_tmp(app); purge_tmp(app,folder="cache",older_than_minutes=30); ViewSession.query.filter(ViewSession.expires_at<now-timedelta(days=1)).delete(); AccessLog.query.filter(AccessLog.ts<now-timedelta(days=30)).delete(); db.session.commit()

def start_scheduler(app):
    sched=BackgroundScheduler(daemon=True); sched.add_job(sweep,"interval",minutes=1,args=[app],max_instances=1,coalesce=True); sched.start(); return sched
