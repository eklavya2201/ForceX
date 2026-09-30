import time
from flask import Flask, request, render_template
from flask_login import current_user
from .extensions import db, login_manager, csrf, limiter
from .models import User

def create_app(config_object=None,start_scheduler=True):
    app=Flask(__name__,template_folder="../templates",static_folder="../static")
    app.config.from_object(config_object or "backend.config.Config")
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("FORCEX_SECRET_KEY must be set before starting ForceX")
    if not app.config.get("CLIENT_KEY"):
        raise RuntimeError("FORCEX_CLIENT_KEY must be set before starting ForceX")
    if app.config.get("BEHIND_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1)
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app); limiter.init_app(app)
    login_manager.login_view="auth.login"
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User,int(user_id))
    from .auth import bp as auth_bp
    from .shares import bp as shares_bp
    from .receive import bp as receive_bp
    app.register_blueprint(auth_bp); app.register_blueprint(shares_bp); app.register_blueprint(receive_bp)
    @app.get("/")
    def home():
        from flask import redirect,url_for
        return redirect(url_for("shares.dashboard" if current_user.is_authenticated else "auth.login"))
    @app.get("/cron/sweep")
    def cron_sweep():
        # Vercel Cron calls this with "Authorization: Bearer <CRON_SECRET>".
        import hmac
        from flask import abort
        secret=app.config.get("CRON_SECRET")
        if not secret or not hmac.compare_digest(request.headers.get("Authorization",""),f"Bearer {secret}"): abort(404)
        from .cleanup import sweep
        sweep(app); return {"ok":True}
    @app.get("/drm/<path:name>")
    def drm_asset(name):
        import universal_drm
        from flask import send_from_directory
        return send_from_directory(universal_drm.static_dir(),name,max_age=3600)
    @app.errorhandler(404)
    def not_found(_error):
        return render_template("receiver/gone.html"), 404
    @app.after_request
    def secure_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options","nosniff"); resp.headers.setdefault("Referrer-Policy","no-referrer"); resp.headers.setdefault("X-Frame-Options","SAMEORIGIN"); resp.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        # With Blob storage, browsers upload to the Blob API and play video from signed Blob URLs.
        blob_media=" https://*.private.blob.vercel-storage.com" if app.config["STORAGE_BACKEND"]=="blob" else ""
        blob_api=" https://vercel.com" if app.config["STORAGE_BACKEND"]=="blob" else ""
        resp.headers.setdefault("Content-Security-Policy",f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'{blob_media}; connect-src 'self'{blob_api}; frame-src 'self'; object-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
        if request.path.startswith(("/s/","/v/")): resp.headers["Cache-Control"]="no-store, max-age=0"; resp.headers["Pragma"]="no-cache"
        return resp
    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect, text
        # create_all does not add columns to existing tables
        for table,column,ddl in (("share","protection","VARCHAR(10) NOT NULL DEFAULT 'browser'"),("stored_file","blob_path","VARCHAR(300)")):
            if column not in {c["name"] for c in inspect(db.engine).get_columns(table)}:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")); db.session.commit()
        from .cleanup import sweep
        sweep(app)
    if start_scheduler:
        from .cleanup import start_scheduler
        app.extensions["forcex_scheduler"]=start_scheduler(app)
    else:
        # Hosts without background threads (PythonAnywhere) sweep from incoming requests instead, at most once a minute.
        last_sweep=[time.monotonic()]
        @app.before_request
        def sweep_on_request():
            if time.monotonic()-last_sweep[0]>=60:
                last_sweep[0]=time.monotonic()
                from .cleanup import sweep
                sweep(app)
    return app
