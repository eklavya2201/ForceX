import os, shutil
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from .extensions import db
from .models import Share, StoredFile, ViewSession, AccessLog, utcnow
from .storage import delete_share_blobs
from .tokens import finalize

def purge_tmp(app,older_than_minutes=60):
    root=os.path.join(app.config["STORAGE_DIR"],"tmp")
    if not os.path.isdir(root): return
    cutoff=utcnow().timestamp()-older_than_minutes*60
    for name in os.listdir(root):
        path=os.path.join(root,name)
        try:
            if os.path.getmtime(path)<cutoff: shutil.rmtree(path,ignore_errors=True)
        except OSError: pass

def sweep(app):
    with app.app_context():
        now=utcnow()
        for s in Share.query.filter(Share.status=="active",Share.expires_at<=now).all(): finalize(s,"expired")
        for s in Share.query.filter_by(status="opened").all():
            if ViewSession.query.filter(ViewSession.share_id==s.id,ViewSession.expires_at>now).count()==0: finalize(s,"consumed")
        for f in StoredFile.query.join(Share).filter(StoredFile.deleted_at.is_(None),Share.status.in_(("consumed","expired","revoked"))).all(): delete_share_blobs(f.share)
        purge_tmp(app); ViewSession.query.filter(ViewSession.expires_at<now-timedelta(days=1)).delete(); AccessLog.query.filter(AccessLog.ts<now-timedelta(days=30)).delete(); db.session.commit()

def start_scheduler(app):
    sched=BackgroundScheduler(daemon=True); sched.add_job(sweep,"interval",minutes=1,args=[app],max_instances=1,coalesce=True); sched.start(); return sched
