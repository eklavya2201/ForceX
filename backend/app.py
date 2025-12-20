from flask import Flask, request, abort, render_template
import jwt, time

app = Flask(__name__)
SECRET_KEY = "FORCEX_SECRET_KEY"

def generate_token(user):
    payload = {
        "user": user,
        "exp": time.time() + 300  # 5 minutes
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None

@app.route("/")
def home():
    token = generate_token("Eklavya")
    return f"""
    <h2>ForceX Test Page</h2>
    <a href="/secure/view?token={token}">Open Secure Content</a>
    """

@app.route("/secure/view")
def secure_view():
    token = request.args.get("token")
    if not token or not verify_token(token):
        abort(403)

    user = verify_token(token)["user"]
    return render_template("viewer.html", user=user)

# 🔴 THIS PART IS CRITICAL
if __name__ == "__main__":
    print("🔥 ForceX backend starting...")
    app.run(host="127.0.0.1", port=5000, debug=True)
@app.route("/secure/video/<video_id>")
def secure_video(video_id):
    # 🔐 token validation here

    return render_template(
        "secure_video.html",
        video_url=f"/stream/{video_id}.mp4",
        user="Eklavya"
    )

@app.route("/stream/<filename>")
def stream_video(filename):
    # ❗ ensure authentication here
    return send_from_directory("videos", filename)
import os
import subprocess
from flask import send_from_directory

BASE_DIR = os.path.dirname(__file__)
UPLOADS = os.path.join(BASE_DIR, "uploads")
TEMP = os.path.join(BASE_DIR, "temp")
VIDEOS = os.path.join(BASE_DIR, "videos")

os.makedirs(TEMP, exist_ok=True)
os.makedirs(VIDEOS, exist_ok=True)


@app.route("/secure/ppt/<name>")
def ppt_to_video(name):
    ppt_path = os.path.join(UPLOADS, f"{name}.pptx")
    pdf_path = os.path.join(TEMP, f"{name}.pdf")
    video_path = os.path.join(VIDEOS, f"{name}.mp4")

    # 1️⃣ PPT → PDF
    subprocess.run([
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", TEMP,
        ppt_path
    ], check=True)

    # 2️⃣ PDF → Video
    subprocess.run([
        "ffmpeg",
        "-y",
        "-i", pdf_path,
        "-vf", "scale=1280:-2",
        "-r", "1",
        video_path
    ], check=True)

    return f"""
    <h3>Video ready</h3>
    <a href="/secure/video/{name}">Play Video</a>
    """


@app.route("/secure/video/<name>")
def play_video(name):
    return f"""
    <video controls autoplay style="width:100%;height:100vh;">
        <source src="/stream/{name}.mp4" type="video/mp4">
    </video>
    """


@app.route("/stream/<filename>")
def stream(filename):
    return send_from_directory(VIDEOS, filename)
