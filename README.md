# ForceX Share

Private, one-time file sharing built with Flask.

ForceX Share lets an authenticated sender upload files and create temporary links for receivers. Shares can require a passcode, expire automatically, and be revoked by the sender. Receiver access is mediated by short-lived sessions rather than permanent public file URLs.

> **Project status:** MVP/prototype. Review the deployment and security notes before exposing this application to the internet.

## Capabilities

- Sender registration, login, logout, and dashboard
- File and folder uploads with server-side storage outside the public web root
- One-time share links with optional passcodes
- View-once and download-once access modes
- Configurable share expiry: 1 hour, 24 hours, or 7 days
- Short-lived receiver sessions
- Sender-side revocation
- Automatic expiry and cleanup of temporary data
- MIME allowlisting for inline previews
- Security and access event logging
- CSRF protection, rate limiting, security headers, and Argon2 password hashing
- Optional PySide6 desktop client in `browser/`

## User Flow

```text
Sender -> Upload files -> Create share -> Copy temporary link
                                              |
Receiver <- Open link <- Optional passcode <-+
    |
    +-> View once or download once
    |
    +-> Session expires, share is consumed, or sender revokes access
```

The landing page does not consume a share. Consumption occurs only after the receiver submits the explicit open action. Token hashes, not raw share tokens, are stored in the database.

## Requirements

- Windows or another supported Python environment
- Python 3.12 or newer
- PowerShell on Windows
- Git, if cloning the repository

## Quick Start: Windows

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Generate a secret key and place it in `.env`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Replace the value of `FORCEX_SECRET_KEY` with the generated 64-character value. Then start the application:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), register a sender account, and create a share.

Stop the server with `Ctrl+C`.

### Using an Existing Virtual Environment

If the environment is already created, the minimum launch sequence is:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Use `python -m pip` rather than a separate `pip` executable to ensure packages are installed into the interpreter that runs ForceX.

## Configuration

ForceX loads configuration from `.env`. Start from `.env.example` and never commit `.env`.

| Variable | Default | Description |
|---|---:|---|
| `FORCEX_SECRET_KEY` | None | Required application secret. Use a unique random value. |
| `FORCEX_DB` | `sqlite:///forcex.db` | SQLAlchemy database URL. |
| `FORCEX_STORAGE` | `<project>/storage` | Private storage directory for uploaded blobs. |
| `FORCEX_MAX_UPLOAD_MB` | `500` | Maximum request upload size in megabytes. |
| `FORCEX_VIEW_TTL_MIN` | `10` | Receiver view-session lifetime in minutes. |
| `FORCEX_DOWNLOAD_TTL_MIN` | `5` | Receiver download-session lifetime in minutes. |
| `FORCEX_COOKIE_SECURE` | `0` | Set to `1` when serving over HTTPS. |
| `FORCEX_ALLOW_REGISTRATION` | `1` | Set to `0` to disable new sender registrations. |

Example local configuration:

```env
FORCEX_SECRET_KEY=replace-with-a-random-64-character-hex-value
FORCEX_DB=sqlite:///forcex.db
FORCEX_STORAGE=storage
FORCEX_MAX_UPLOAD_MB=500
FORCEX_VIEW_TTL_MIN=10
FORCEX_DOWNLOAD_TTL_MIN=5
FORCEX_COOKIE_SECURE=0
FORCEX_ALLOW_REGISTRATION=1
```

For production, use a managed or externally hosted database where appropriate, persistent private storage, HTTPS, and `FORCEX_COOKIE_SECURE=1`.

## Application Architecture

```text
ForceX/
|-- backend/
|   |-- __init__.py       Flask application factory and security headers
|   |-- config.py         Environment-backed configuration
|   |-- extensions.py     SQLAlchemy, login, CSRF, and rate limiting
|   |-- models.py         Users, shares, files, sessions, and audit records
|   |-- auth.py           Registration and authentication routes
|   |-- shares.py         Share creation, dashboard, and revocation
|   |-- receive.py        Receiver landing, preview, and download routes
|   |-- tokens.py         Token hashing, consumption, and receiver sessions
|   |-- storage.py        Upload handling, archives, and cleanup
|   |-- cleanup.py        Expiry and scheduled cleanup
|   |-- audit.py          Access and security event logging
|-- templates/            Jinja templates
|-- static/               CSS and JavaScript assets
|-- browser/              Optional PySide6 desktop client
|-- legacy/               Preserved prototype utilities
|-- run.py                Waitress application entry point
|-- requirements.txt      Python dependencies
|-- .env.example          Safe configuration template
```

The application is created by `backend.create_app()`. `run.py` serves it with Waitress on `127.0.0.1:5000`. Database tables are created during application initialization and the cleanup sweep runs at startup; the scheduler continues periodic cleanup while the process is running.

## Route Surface

| Area | Routes |
|---|---|
| Authentication | `/register`, `/login`, `/logout` |
| Sender | `/dashboard`, `/new`, `/shares`, `/shares/<share_id>/revoke` |
| Receiver | `/s/<token>`, `/s/<token>/open` |
| Receiver session | `/v/<share_id>`, `/v/<share_id>/file`, `/v/<share_id>/download`, `/v/<share_id>/end` |

Receiver file routes require a valid share-scoped session. Files are served from private storage through application routes rather than as static assets.

## Security Considerations

ForceX provides application-level controls, including:

- Raw share tokens are not stored in the database.
- Share consumption is performed atomically to prevent concurrent reuse.
- Receiver sessions are short-lived and scoped to a share.
- Uploads are stored outside `static/` and use server-generated storage keys.
- Passwords are hashed with Argon2.
- CSRF protection, rate limiting, and security response headers are enabled.
- Expired, revoked, and completed shares are cleaned up by the application.

These controls do not provide DRM. A browser-based viewer cannot reliably prevent screenshots, screen recording, or copying of content that has been displayed to a receiver. Watermarks and browser restrictions are deterrents only.

Before deployment:

1. Run behind HTTPS and set `FORCEX_COOKIE_SECURE=1`.
2. Keep `.env`, the database, logs, and `storage/` outside source control.
3. Use persistent, access-controlled storage and back up the database according to your retention policy.
4. Put a reverse proxy and appropriate request-size limits in front of Waitress.
5. Set `FORCEX_ALLOW_REGISTRATION=0` after creating the required sender accounts.
6. Review rate limits, expiry values, logging, and upload policies for your threat model.

Do not expose Flask's development server directly to the public internet. The provided `run.py` uses Waitress for local and controlled deployments, but production hardening is still required.

## Development

Run the application locally:

```powershell
.\.venv\Scripts\python.exe run.py
```

Create an app instance without starting the server, for example for a shell or integration test:

```powershell
.\.venv\Scripts\python.exe -c "from backend import create_app; app = create_app(start_scheduler=False); print(app.url_map)"
```

The repository currently does not include an automated test suite. At minimum, verify registration, login, share creation, receiver opening, preview/download behavior, expiry, and revocation before deployment.

## Optional Desktop Client

The PySide6 client in `browser/forcex_browser.py` is a separate prototype client and currently opens Canva with downloads blocked. It is not required to run the Flask web application.

```powershell
.\.venv\Scripts\python.exe -m browser.forcex_browser
```

## Troubleshooting

### `FORCEX_SECRET_KEY must be set before starting ForceX`

Create `.env` from `.env.example` and set a non-empty `FORCEX_SECRET_KEY`:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

### Package installation goes to the wrong Python installation

Use the virtual-environment interpreter for both installation and execution:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

### Port 5000 is already in use

Stop the process using the port or change the host/port in `run.py` before starting the application.

### Uploads or shares disappear after restart

Check that `FORCEX_STORAGE` points to persistent storage and that the database URL is not using a temporary location. The cleanup scheduler intentionally removes expired or finalized share data.

## License

This project is currently an MVP/prototype and does not yet declare a license. Add the intended license before public distribution.
