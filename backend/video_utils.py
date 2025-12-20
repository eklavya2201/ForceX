import subprocess
import os

def images_to_video(image_dir, output_video):
    subprocess.run([
        "ffmpeg",
        "-framerate", "1",
        "-i", f"{image_dir}/page_%d.png",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_video
    ], check=True)
