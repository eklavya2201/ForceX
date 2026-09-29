# ForceX Share

ForceX creates one-time links for files. Senders register and sign in; receivers use the link without an account. A receiver must click Open, so link preview bots do not consume the share. Download links work once. View links use a short-lived, cookie-bound session and an inline MIME allowlist. Content is deleted when the session ends or the share expires or is revoked.

A rendered file can still be saved or captured. Watermarks and disabled browser controls are deterrents, not screenshot protection.

## Setup

Python 3.12+ is recommended. Install dependencies and create a local `.env` from `.env.example`. Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"` and set it as `FORCEX_SECRET_KEY`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace the sample secret before starting. Run with `python run.py`; Waitress listens on `127.0.0.1:5000`. The database and blobs are local and ignored by git. `FORCEX_COOKIE_SECURE=1` should be used behind HTTPS.

Registration is open by default for initial setup. Set `FORCEX_ALLOW_REGISTRATION=0` in `.env` after creating sender accounts if public registration is not wanted.

## Share behavior

- Single allowlisted image, PDF, video, or plain text can use view mode.
- Other formats, folders, and multiple files use one-time download mode; collections are zipped.
- An interrupted download still consumes the link.
- Active shares expire in 1 hour, 24 hours, or 7 days. Five wrong passcodes revoke a share.
- The sender dashboard lists metadata and supports revocation. The secret link is shown only at creation.

`browser/` remains the existing PySide6 client and is not part of this web MVP.
