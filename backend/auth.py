import re
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, current_user
from sqlalchemy.exc import IntegrityError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from .extensions import db, limiter
from .models import User
from .audit import log_event

bp=Blueprint("auth",__name__)
ph=PasswordHasher()
_dummy=ph.hash("not-a-real-user-password")

@bp.route("/register",methods=["GET","POST"])
def register():
    if not current_app.config.get("ALLOW_REGISTRATION",True): return render_template("auth/register.html",closed=True)
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email) or len(password)<10:
            flash("Enter a valid email and a password with at least 10 characters.","error")
        else:
            existing=User.query.filter_by(email=email).first()
            if not existing:
                try:
                    user=User(email=email,password_hash=ph.hash(password)); db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for("shares.dashboard"))
                except IntegrityError:
                    # Another request registered the same email a moment earlier (usually a double-clicked submit).
                    db.session.rollback(); existing=User.query.filter_by(email=email).first()
            if existing and _password_matches(existing,password):
                login_user(existing); return redirect(url_for("shares.dashboard"))
            flash("Unable to create account with those details.","error")
    return render_template("auth/register.html")

def _password_matches(user,password):
    try: return ph.verify(user.password_hash,password)
    except (VerifyMismatchError,VerificationError): return False

@bp.route("/login",methods=["GET","POST"])
@limiter.limit("5 per minute",methods=["POST"])
def login():
    if request.method=="POST":
        user=User.query.filter_by(email=request.form.get("email","").strip().lower()).first(); hashed=user.password_hash if user else _dummy
        try: valid=ph.verify(hashed,request.form.get("password","") or "")
        except (VerifyMismatchError,VerificationError): valid=False
        if user and valid:
            login_user(user); log_event("LOGIN_SUCCESS"); return redirect(url_for("shares.dashboard"))
        log_event("LOGIN_FAILURE",result="denied"); flash("Invalid credentials.","error")
    return render_template("auth/login.html")

@bp.post("/logout")
def logout(): logout_user(); return redirect(url_for("auth.login"))
