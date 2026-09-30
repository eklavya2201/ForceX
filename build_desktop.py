"""Build dist/ForceX.exe with the server address and client key built in.

    python build_desktop.py --url https://forcex-xxxx.onrender.com --key <FORCEX_CLIENT_KEY>

Both default to FORCEX_URL / FORCEX_CLIENT_KEY from the environment or .env.
The key ends up inside the .exe, so only hand the .exe to people you share with.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
BAKED = ROOT / "browser" / "_baked.py"


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.getenv("FORCEX_URL", "http://127.0.0.1:5000"))
    parser.add_argument("--key", default=os.getenv("FORCEX_CLIENT_KEY"))
    args = parser.parse_args()
    if not args.key:
        sys.exit("No client key: pass --key or set FORCEX_CLIENT_KEY in .env")

    BAKED.write_text(f"FORCEX_URL = {args.url.rstrip('/')!r}\nFORCEX_CLIENT_KEY = {args.key!r}\n", encoding="utf-8")
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "ForceX", "--paths", str(ROOT),
            "--hidden-import", "_baked",
            str(ROOT / "browser" / "forcex_browser.py"),
        ], cwd=ROOT, check=True)
    finally:
        # Keep the key out of the working tree once it is inside the .exe.
        BAKED.unlink(missing_ok=True)
    print(f"\nBuilt {ROOT / 'dist' / 'ForceX.exe'} for {args.url}")


if __name__ == "__main__":
    main()
