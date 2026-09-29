from flask import request
from flask_login import current_user
from .extensions import db
from .models import AccessLog
from .tokens import hash_ip

def log_event(event, share_id=None, result="ok", detail=None):
    uid=current_user.id if current_user.is_authenticated else None
    db.session.add(AccessLog(share_id=share_id,user_id=uid,event=event,result=result,detail=(detail or "")[:255],ip_hash=hash_ip(request.remote_addr)))
    db.session.commit()
