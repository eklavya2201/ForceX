import subprocess
import os

def ppt_to_pdf(ppt_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run([
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        ppt_path
    ], check=True)

    pdf_name = os.path.splitext(os.path.basename(ppt_path))[0] + ".pdf"
    return os.path.join(output_dir, pdf_name)
