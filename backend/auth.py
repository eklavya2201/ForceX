import re
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, current_user
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
        elif User.query.filter_by(email=email).first(): flash("Unable to create account with those details.","error")
        else:
            user=User(email=email,password_hash=ph.hash(password)); db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for("shares.dashboard"))
    return render_template("auth/register.html")

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
