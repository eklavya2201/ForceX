# ForceX Share

> Private, one-time file sharing with watermarked browser viewing and screenshot-protected native clients.

ForceX Share is a self-hosted Flask application that lets authenticated senders upload files and generate short-lived links for receivers. Shares are consumed once, expire automatically, and can be revoked at any time. Content viewed in a browser is rendered as watermarked page images by [UniversalDRM](https://github.com/neelmali182/UniversalDRM) — the original file never leaves the server. Native clients for Windows and Android add OS-level screenshot exclusion on top of that.

> **Status:** MVP/prototype. Review the [security notes](#security) and [pre-deployment checklist](#pre-deployment-checklist) before exposing this to the internet.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Security](#security)
- [Client Apps](#client-apps)
- [Deployment](#deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

| Capability | Details |
|---|---|
| One-time share links | Each link opens once; consumption is atomic to prevent race conditions |
| Access modes | View-once (browser renders watermarked page images) or download-once |
| Passcode protection | Optional per-share passcode with lockout after 5 failed attempts |
| Configurable expiry | 1 hour, 24 hours, or 7 days |
| Sender revocation | Active shares can be revoked from the dashboard at any time |
| Watermarking | Share label, share ID, viewer network, and open timestamp burned into every rendered page |
| Screenshot blocking | Windows (`WDA_EXCLUDEFROMCAPTURE`) and Android (`FLAG_SECURE`) in native clients |
| App-only protection | Per-share option that restricts access to the native client only |
| Audit logging | Every access and security event is recorded with client type, platform, and device |
| Automatic cleanup | Expired and consumed shares and their files are removed by the background scheduler |

---

## How It Works

```text
Sender ──► Upload files ──► Create share ──► Copy link
                                                 │
Receiver ◄── Open link ◄── Optional passcode ◄──┘
    │
    ├── View  ──► page images rendered server-side, watermarked ──► session expires
    │
    └── Download  ──► one-time short-lived download session
```

The share landing page does not consume a share. Consumption happens only after the receiver submits the explicit open action. Raw share tokens are never written to the database — only their SHA-256 hashes are stored.

---

## Requirements

- Python 3.12 or newer
- PowerShell (Windows setup and native client build)
- Git (to clone the repository)
- Edge WebView2 Runtime (Windows client only — included in Windows 11; downloadable for Windows 10)

---

## Quick Start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Generate two independent secret keys and place them in `.env`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Run the command twice. Set the first output as `FORCEX_SECRET_KEY` and the second as `FORCEX_CLIENT_KEY`. Then start the server:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), register a sender account, and create your first share.

### Reusing an Existing Environment

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Always use `.venv\Scripts\python.exe -m pip` rather than a bare `pip` to ensure packages land in the correct interpreter.

---

## Configuration

Copy `.env.example` to `.env` and never commit `.env` to source control.

| Variable | Default | Description |
|---|---|---|
| `FORCEX_SECRET_KEY` | *(required)* | Flask session secret. Use a unique random 64-character hex value. |
| `FORCEX_CLIENT_KEY` | *(required)* | Shared with native clients. Receiver routes reject requests that do not carry it. |
| `FORCEX_DB` | `sqlite:///forcex.db` | SQLAlchemy database URL. |
| `FORCEX_STORAGE` | `<project>/storage` | Private upload directory, outside the web root. |
| `FORCEX_MAX_UPLOAD_MB` | `500` | Maximum upload size in megabytes. |
| `FORCEX_VIEW_TTL_MIN` | `10` | Receiver view-session lifetime in minutes. |
| `FORCEX_DOWNLOAD_TTL_MIN` | `5` | Receiver download-session lifetime in minutes. |
| `FORCEX_COOKIE_SECURE` | `0` | Set to `1` when serving over HTTPS. |
| `FORCEX_ALLOW_REGISTRATION` | `1` | Set to `0` to lock new sender registrations after initial setup. |
| `FORCEX_BEHIND_PROXY` | `0` | Set to `1` behind nginx, Render, or similar reverse proxies. |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Address Waitress listens on. Use `0.0.0.0` to accept external connections. |
| `FORCEX_SCHEDULER` | `1` | Set to `0` on hosts without background threads (e.g. PythonAnywhere). |
| `BLOB_READ_WRITE_TOKEN` | *(unset)* | When set, files are stored in Vercel Blob; browsers upload directly to signed URLs. |
| `DATABASE_URL` | *(unset)* | Postgres URL from Neon. Used automatically when `FORCEX_DB` is not set. |
| `FORCEX_DESKTOP_DOWNLOAD_URL` | latest GitHub release | URL for the "Download ForceX" button shown to receivers. |
| `FORCEX_ANDROID_DOWNLOAD_URL` | latest GitHub release | URL for the Android APK download link. |

Example local configuration:

```env
FORCEX_SECRET_KEY=replace-with-a-random-64-character-hex-value
FORCEX_CLIENT_KEY=replace-with-a-different-random-64-character-hex-value
FORCEX_DB=sqlite:///forcex.db
FORCEX_STORAGE=storage
FORCEX_MAX_UPLOAD_MB=500
FORCEX_VIEW_TTL_MIN=10
FORCEX_DOWNLOAD_TTL_MIN=5
FORCEX_COOKIE_SECURE=0
FORCEX_ALLOW_REGISTRATION=1
```

---

## Architecture

```
ForceX/
├── backend/
│   ├── __init__.py       Application factory, security headers
│   ├── config.py         Environment-backed configuration
│   ├── extensions.py     SQLAlchemy, Flask-Login, CSRF, rate limiter
│   ├── models.py         User, Share, StoredFile, ViewSession, AccessLog, PendingUpload
│   ├── auth.py           Sender registration, login, logout
│   ├── shares.py         Share creation, dashboard, revocation
│   ├── receive.py        Receiver landing, preview, and download routes
│   ├── tokens.py         Token hashing, atomic consumption, receiver sessions
│   ├── storage.py        Upload handling, folder archives, Vercel Blob integration
│   ├── cleanup.py        Expiry sweeps and scheduled background cleanup
│   └── audit.py          Access and security event logging
├── templates/            Jinja2 templates
├── static/               CSS and JavaScript assets
├── browser/              PySide6 + Edge WebView2 desktop client
├── android/              Android client (Gradle)
├── tests/                Automated test suite
├── run.py                Waitress entry point (local and controlled deployments)
├── wsgi.py               WSGI entry point (PythonAnywhere, Render)
└── build_desktop.py      PyInstaller build script for dist/ForceX.exe
```

The application is created by `backend.create_app()`. Database tables are created and the cleanup sweep runs at startup; the APScheduler instance continues periodic cleanup while the process is live.

### Route Surface

| Area | Routes |
|---|---|
| Authentication | `/register`, `/login`, `/logout` |
| Sender | `/dashboard`, `/new`, `/shares`, `/shares/<id>/revoke` |
| Receiver landing | `/s/<token>`, `/s/<token>/open` |
| Receiver session | `/v/<id>`, `/v/<id>/file`, `/v/<id>/download`, `/v/<id>/end` |

Receiver file routes require a valid, short-lived share-scoped session. Files are served through application routes — never as static assets.

---

## Security

**Token handling.** Raw share tokens are not stored anywhere. Consumption is performed atomically inside a database transaction to prevent concurrent reuse of the same link.

**Browser viewing.** PDFs, images, and text files are rendered server-side into JPEG page images by [UniversalDRM](https://github.com/neelmali182/UniversalDRM). The share label, share ID, viewer network, and open timestamp are burned into every pixel. The browser viewer blocks copying, saving, and printing. If a receiver photographs the screen, the watermark traces the leak.

**App-only protection.** Shares configured as *ForceX app only* require the `X-ForceX-Client` header carrying `FORCEX_CLIENT_KEY`. Ordinary browsers receive a landing page with a download link instead of access to content.

**Application controls enabled by default:**

- Argon2id password hashing
- CSRF protection on all state-changing forms
- Rate limiting on authentication routes
- `HttpOnly`, `SameSite=Lax` session cookies (`Secure` when `FORCEX_COOKIE_SECURE=1`)
- `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` response headers
- Uploads stored outside `static/` using server-generated storage keys

**Honest limitations.** The client key is embedded in the desktop app binary, so a determined user can extract it and fetch content with a script. Nothing prevents photographing a screen — the watermark is a forensic trace, not a technical barrier. ForceX provides application-layer controls, not cryptographic DRM.

### Pre-Deployment Checklist

1. Serve behind HTTPS and set `FORCEX_COOKIE_SECURE=1`.
2. Keep `.env`, the database, `logs/`, and `storage/` out of source control and backups that are not access-controlled.
3. Use persistent, access-controlled storage. Back up the database on a schedule that matches your retention policy.
4. Place a reverse proxy (nginx, Caddy) with appropriate request-size limits in front of Waitress.
5. Set `FORCEX_ALLOW_REGISTRATION=0` after creating the required sender accounts.
6. Review rate limits, expiry values, logging retention, and upload size limits for your threat model.
7. Do not expose Flask's development server directly to the internet.

---

## Client Apps

Shares with **Any browser** protection open in any browser through the UniversalDRM viewer. Shares with **ForceX app only** protection require a native client.

Both native clients:

- Hide their windows from screenshots, screen recording, Snipping Tool, and screen share (Windows 10 2004+ / Android 7.0+)
- Block printing and right-click context menus
- Only navigate to pages served from `FORCEX_URL`

### Windows

The Windows client is a PySide6 application using the Microsoft Edge WebView2 control. It reads `FORCEX_URL` (default `http://127.0.0.1:5000`) and `FORCEX_CLIENT_KEY` from the environment or a `.env` file.

**Run from source:**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m browser.forcex_browser
```

Paste a share link into the address bar at the top, or pass it as a command-line argument.

**Build a distributable EXE:**

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build_desktop.py --url https://your-forcex-site --key <FORCEX_CLIENT_KEY>
```

The output is an `onedir` bundle at `dist\ForceX\`. Distribute the entire folder — `ForceX.exe` alone is not sufficient. A `forcex.env` file placed next to `ForceX.exe` overrides the built-in server address and client key.

> For local screenshot testing only, set `FORCEX_DISABLE_CAPTURE_PROTECTION=1` before launching. Keep this unset in all other environments.

### Android

The Android client source is in `android/`. Pass `FORCEX_URL` and `FORCEX_CLIENT_KEY` at Gradle build time:

```bash
export FORCEX_URL="https://your-forcex-site"
export FORCEX_CLIENT_KEY="<FORCEX_CLIENT_KEY>"
cd android
./gradlew assembleRelease
```

### GitHub Actions

The repository includes workflows that build the Windows EXE and Android APK automatically when a tag matching `v*` is pushed. Built artifacts are uploaded to the corresponding GitHub release.

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for step-by-step guides covering:

- **Vercel** — serverless hosting with Neon Postgres and private Vercel Blob storage
- **PythonAnywhere** — set `FORCEX_SCHEDULER=0` and use `wsgi.py` as the entry point
- **Render** — paid hosting with a persistent disk for file storage

When `BLOB_READ_WRITE_TOKEN` is set, sender browsers upload files directly to signed Vercel Blob URLs and receivers stream downloads from signed links — the application server is not in the data path. `DATABASE_URL` (Neon Postgres) is used automatically when `FORCEX_DB` is not set, which is the standard Vercel setup.

---

## Development

**Run the server locally:**

```powershell
.\.venv\Scripts\python.exe run.py
```

**Run the test suite:**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite in `tests/` covers registration, login, share creation, receiver opening, view and download behavior, expiry, and revocation. Run it before deploying any change.

**Inspect the application without starting the server:**

```powershell
.\.venv\Scripts\python.exe -c "from backend import create_app; app = create_app(start_scheduler=False); print(app.url_map)"
```

---

## Troubleshooting

**`FORCEX_SECRET_KEY must be set before starting ForceX`**

Create `.env` from the example and set a non-empty key:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

**Packages install to the wrong Python**

Always use the virtual-environment interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

**Port 5000 is already in use**

Stop the conflicting process, or set `PORT=<other port>` in `.env` before starting.

**Shares or uploads disappear after a restart**

Verify `FORCEX_STORAGE` points to persistent storage and that `FORCEX_DB` (or `DATABASE_URL`) is not a temporary path. The cleanup scheduler intentionally removes expired and consumed share data.

---

## License

No license has been declared yet. Add one before public distribution.
